"""
MCP Server for Kimi-PIMCP - OPTIMIZED VERSION
Implements Model Context Protocol over stdio (JSON-RPC 2.0).

Improvements:
- Thread-safe operations
- Query history tracking
- Multi-project support
- Better error handling
- Export/Import functionality
"""

import sys
import json
import logging
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from dataclasses import dataclass
from collections import OrderedDict
import threading
import time

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Import our modules
try:
    from indexer import ProjectIndexer, get_indexer, clear_all_indexers, ModelCache
    from retriever import ContextRetriever, get_retriever, clear_retriever
    from compressor import CavemanCompressor, get_compressor, clear_compressor
    from skills.router import SkillRouter, get_router
    from file_watcher import ProjectFileWatcher, FileChangeEvent, FileChangeType
    from dependency_graph import DependencyGraph
    from git_integration import GitIntegration, IncrementalIndexer
    from code_summarizer import CodeSummarizer, SimilarCodeDetector
    from traceability import TraceabilityAnalyzer, get_traceability
    from activity_monitor import ActivityMonitor, record_mcp_request, record_mcp_response, record_mcp_error, record_tool_call
except ImportError:
    from .indexer import ProjectIndexer, get_indexer, clear_all_indexers, ModelCache
    from .retriever import ContextRetriever, get_retriever, clear_retriever
    from .compressor import CavemanCompressor, get_compressor, clear_compressor
    from .skills.router import SkillRouter, get_router
    from .file_watcher import ProjectFileWatcher, FileChangeEvent, FileChangeType
    from .dependency_graph import DependencyGraph
    from .git_integration import GitIntegration, IncrementalIndexer
    from .code_summarizer import CodeSummarizer, SimilarCodeDetector
    from .traceability import TraceabilityAnalyzer, get_traceability
    from .activity_monitor import ActivityMonitor, record_mcp_request, record_mcp_response, record_mcp_error, record_tool_call


class MCPError(Exception):
    """MCP protocol error."""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# JSON-RPC error codes
ERROR_PARSE_ERROR = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL_ERROR = -32603
ERROR_SERVER_ERROR = -32000


@dataclass
class QueryHistoryEntry:
    """Entry in query history."""
    query: str
    timestamp: float
    results_count: int
    skill: str


class MCPServer:
    """
    Model Context Protocol server - OPTIMIZED VERSION.
    
    Communicates via stdin/stdout using JSON-RPC 2.0.
    Logs to stderr.
    """
    
    def __init__(self):
        """Initialize the MCP server."""
        self.running = False
        self.request_id = 0
        
        # Components
        self.indexer: Optional[ProjectIndexer] = None
        self.retriever: Optional[ContextRetriever] = None
        self.compressor: Optional[CavemanCompressor] = None
        self.router: Optional[SkillRouter] = None
        self.file_watcher: Optional[ProjectFileWatcher] = None
        self.dependency_graph: Optional[DependencyGraph] = None
        self.git: Optional[GitIntegration] = None
        self.summarizer: Optional[CodeSummarizer] = None
        self.similarity_detector: Optional[SimilarCodeDetector] = None
        self.traceability: Optional[TraceabilityAnalyzer] = None
        
        # Multi-project support
        self.projects: Dict[str, Dict] = {}  # project_path -> project info
        self.current_project: Optional[str] = None
        
        # Query history
        self.query_history: OrderedDict[str, QueryHistoryEntry] = OrderedDict()
        self.max_history = 50
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Register tools
        self.tools: Dict[str, Callable] = {
            'initialize_index': self._tool_initialize_index,
            'query_context': self._tool_query_context,
            'select_skill': self._tool_select_skill,
            'compress_output': self._tool_compress_output,
            'get_stats': self._tool_get_stats,
            'clear_cache': self._tool_clear_cache,
            'get_query_history': self._tool_get_query_history,
            'switch_project': self._tool_switch_project,
            'list_projects': self._tool_list_projects,
            'get_dependencies': self._tool_get_dependencies,
            'find_similar_code': self._tool_find_similar_code,
            'summarize_chunk': self._tool_summarize_chunk,
            'export_index': self._tool_export_index,
            'import_index': self._tool_import_index,
            # Traceability tools
            'generate_daily_report': self._tool_generate_daily_report,
            'generate_weekly_report': self._tool_generate_weekly_report,
            'get_recent_activity': self._tool_get_recent_activity,
            'list_traceability_reports': self._tool_list_traceability_reports,
            'get_traceability_report': self._tool_get_traceability_report,
            'start_traceability_session': self._tool_start_traceability_session,
            'end_traceability_session': self._tool_end_traceability_session,
        }
        
        logger.info("MCP Server initialized (optimized version)")
    
    def _send_response(self, id: Any, result: Any = None, error: Dict = None):
        """Send a JSON-RPC response."""
        response = {'jsonrpc': '2.0', 'id': id}
        
        if error:
            response['error'] = error
        else:
            response['result'] = result
        
        sys.stdout.write(json.dumps(response) + '\n')
        sys.stdout.flush()
    
    def _create_error(self, code: int, message: str, data: Any = None) -> Dict:
        """Create a JSON-RPC error object."""
        error = {'code': code, 'message': message}
        if data is not None:
            error['data'] = data
        return error
    
    def _initialize_components(self):
        """Lazy initialize components."""
        if self.indexer is None:
            self.indexer = get_indexer()
        if self.retriever is None:
            self.retriever = get_retriever(use_cross_encoder=False)
        if self.compressor is None:
            self.compressor = get_compressor()
        if self.router is None:
            self.router = get_router()
        if self.summarizer is None:
            self.summarizer = CodeSummarizer()
        if self.similarity_detector is None:
            self.similarity_detector = SimilarCodeDetector()
        if self.traceability is None and self.current_project:
            self.traceability = get_traceability(self.current_project)
    
    def _add_to_history(self, query: str, results_count: int, skill: str):
        """Add query to history."""
        with self._lock:
            entry = QueryHistoryEntry(
                query=query,
                timestamp=time.time(),
                results_count=results_count,
                skill=skill
            )
            
            # Remove if exists (to move to end)
            if query in self.query_history:
                del self.query_history[query]
            
            # Add to end
            self.query_history[query] = entry
            
            # Trim if needed
            while len(self.query_history) > self.max_history:
                self.query_history.popitem(last=False)
    
    def _on_file_change(self, event: FileChangeEvent):
        """Handle file change events."""
        logger.info(f"File {event.change_type.value}: {event.filepath}")
        
        if self.current_project and event.change_type in (FileChangeType.MODIFIED, FileChangeType.CREATED):
            try:
                # Trigger incremental reindex
                self.indexer.index_project(self.current_project)
                self.retriever.load_index(self.current_project)
                logger.info("Incremental reindex completed")
            except Exception as e:
                logger.error(f"Error during incremental reindex: {e}")
    
    # ============ MCP Protocol Methods ============
    
    def handle_initialize(self, params: Dict) -> Dict:
        """Handle initialize request."""
        protocol_version = params.get('protocolVersion', '2024-11-05')
        client_info = params.get('clientInfo', {})
        
        logger.info(f"Client connected: {client_info.get('name', 'unknown')} "
                   f"v{client_info.get('version', 'unknown')}")
        
        return {
            'protocolVersion': '2024-11-05',
            'capabilities': {
                'tools': {'listChanged': True},
                'logging': {},
            },
            'serverInfo': {
                'name': 'kimi-pimcp',
                'version': '0.2.0'
            }
        }
    
    def handle_tools_list(self, params: Dict = None) -> Dict:
        """Handle tools/list request."""
        tools = [
            {
                'name': 'initialize_index',
                'description': 'Index a project for semantic search',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_path': {'type': 'string', 'description': 'Path to project'},
                        'force_reindex': {'type': 'boolean', 'default': False}
                    },
                    'required': ['project_path']
                }
            },
            {
                'name': 'query_context',
                'description': 'Query indexed project for relevant context',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'top_k': {'type': 'integer', 'default': 5},
                        'filter_ext': {'type': 'array', 'items': {'type': 'string'}},
                        'use_mmr': {'type': 'boolean', 'default': True}
                    },
                    'required': ['query']
                }
            },
            {
                'name': 'select_skill',
                'description': 'Detect user intent and select optimal skill',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'}
                    },
                    'required': ['query']
                }
            },
            {
                'name': 'compress_output',
                'description': 'Compress text using caveman heuristics',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'text': {'type': 'string'},
                        'level': {'type': 'string', 'enum': ['auto', 'lite', 'full', 'ultra', 'wenyan']}
                    },
                    'required': ['text']
                }
            },
            {
                'name': 'get_stats',
                'description': 'Get statistics about indexing and retrieval',
                'inputSchema': {'type': 'object', 'properties': {}}
            },
            {
                'name': 'clear_cache',
                'description': 'Clear all cached indexes',
                'inputSchema': {'type': 'object', 'properties': {}}
            },
            {
                'name': 'get_query_history',
                'description': 'Get recent query history',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'limit': {'type': 'integer', 'default': 10}
                    }
                }
            },
            {
                'name': 'switch_project',
                'description': 'Switch to a different indexed project',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_path': {'type': 'string'}
                    },
                    'required': ['project_path']
                }
            },
            {
                'name': 'list_projects',
                'description': 'List all indexed projects',
                'inputSchema': {'type': 'object', 'properties': {}}
            },
            {
                'name': 'get_dependencies',
                'description': 'Get dependencies for a file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'filepath': {'type': 'string'}
                    },
                    'required': ['filepath']
                }
            },
            {
                'name': 'find_similar_code',
                'description': 'Find similar/duplicate code blocks',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'filepath': {'type': 'string'}
                    },
                    'required': ['filepath']
                }
            },
            {
                'name': 'summarize_chunk',
                'description': 'Summarize a code chunk',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'content': {'type': 'string'},
                        'chunk_type': {'type': 'string'},
                        'language': {'type': 'string'}
                    },
                    'required': ['content']
                }
            },
            {
                'name': 'export_index',
                'description': 'Export index to a file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'output_path': {'type': 'string'}
                    },
                    'required': ['output_path']
                }
            },
            {
                'name': 'import_index',
                'description': 'Import index from a file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'input_path': {'type': 'string'}
                    },
                    'required': ['input_path']
                }
            },
            # Traceability tools
            {
                'name': 'generate_daily_report',
                'description': 'Generate a daily activity report using Git history (no LLM tokens)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'date': {'type': 'string', 'description': 'Date in YYYY-MM-DD format (default: today)'}
                    }
                }
            },
            {
                'name': 'generate_weekly_report',
                'description': 'Generate a weekly activity report using Git history (no LLM tokens)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'week_start': {'type': 'string', 'description': 'Week start date in YYYY-MM-DD format (default: current week)'}
                    }
                }
            },
            {
                'name': 'get_recent_activity',
                'description': 'Get a quick summary of recent Git activity (no LLM tokens)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'days': {'type': 'integer', 'default': 7, 'description': 'Number of days to look back'}
                    }
                }
            },
            {
                'name': 'list_traceability_reports',
                'description': 'List all generated traceability reports',
                'inputSchema': {'type': 'object', 'properties': {}}
            },
            {
                'name': 'get_traceability_report',
                'description': 'Get the content of a specific traceability report',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'report_name': {'type': 'string', 'description': 'Name of the report file'}
                    },
                    'required': ['report_name']
                }
            },
            {
                'name': 'start_traceability_session',
                'description': 'Start a new traceability session to track activity',
                'inputSchema': {'type': 'object', 'properties': {}}
            },
            {
                'name': 'end_traceability_session',
                'description': 'End current traceability session and generate summary',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'generate_summary': {'type': 'boolean', 'default': True}
                    }
                }
            },
        ]
        
        return {'tools': tools}
    
    def handle_tools_call(self, params: Dict) -> Dict:
        """Handle tools/call request."""
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        if tool_name not in self.tools:
            raise MCPError(ERROR_METHOD_NOT_FOUND, f"Tool not found: {tool_name}")
        
        logger.info(f"Calling tool: {tool_name}")
        
        # Record tool call
        record_tool_call(tool_name, arguments)
        
        try:
            result = self.tools[tool_name](**arguments)
            
            # Record successful tool result
            record_tool_call(tool_name, arguments, {'success': True, 'result_preview': str(result)[:100]})
            
            return {
                'content': [{'type': 'text', 'text': json.dumps(result, indent=2)}],
                'isError': False
            }
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            
            # Record tool error
            record_tool_call(tool_name, arguments, {'success': False, 'error': str(e)})
            
            raise MCPError(ERROR_INTERNAL_ERROR, f"Tool execution failed: {str(e)}")
    
    # ============ Tool Implementations ============
    
    def _tool_initialize_index(self, project_path: str, force_reindex: bool = False) -> Dict:
        """Initialize index for a project."""
        self._initialize_components()
        
        # Index project
        stats = self.indexer.index_project(project_path, force_reindex=force_reindex)
        
        # Load in retriever
        self.retriever.load_index(project_path)
        self.current_project = project_path
        
        # Store project info
        self.projects[project_path] = {
            'path': project_path,
            'indexed_at': time.time(),
            'stats': stats
        }
        
        # Setup file watcher
        if self.file_watcher:
            self.file_watcher.stop()
        
        self.file_watcher = ProjectFileWatcher(
            project_path,
            self._on_file_change,
            debounce_seconds=2.0
        )
        self.file_watcher.start()
        
        # Build dependency graph
        self.dependency_graph = DependencyGraph(project_path)
        self.dependency_graph.build()
        
        # Setup git integration
        self.git = GitIntegration(project_path)
        
        return {'success': True, 'stats': stats}
    
    def _tool_query_context(self, query: str, top_k: int = 5,
                           filter_ext: List[str] = None, use_mmr: bool = True) -> Dict:
        """Query the indexed project."""
        if self.current_project is None:
            raise MCPError(ERROR_INVALID_PARAMS, "No project indexed. Call initialize_index first.")
        
        results = self.retriever.query_with_context(
            query, top_k=top_k, filter_ext=filter_ext, use_mmr=use_mmr
        )
        
        # Add to history
        self._add_to_history(query, len(results), 'unknown')
        
        # Track in traceability session if active
        if self.traceability and self.traceability.current_session:
            self.traceability.record_query(query)
            for result in results:
                if 'filepath' in result:
                    self.traceability.record_file_access(result['filepath'])
        
        return {
            'query': query,
            'results_count': len(results),
            'results': results
        }
    
    def _tool_select_skill(self, query: str) -> Dict:
        """Select the best skill for a query."""
        self._initialize_components()
        
        retrieved_files = []
        if self.current_project:
            try:
                results = self.retriever.query(query, top_k=3)
                retrieved_files = [
                    {
                        'filepath': r.chunk.filepath,
                        'chunk_type': r.chunk.chunk_type,
                        'similarity_score': r.similarity_score
                    }
                    for r in results
                ]
            except Exception:
                pass
        
        result = self.router.execute_skill(
            query, retrieved_files=retrieved_files, project_path=self.current_project or ""
        )
        
        return result
    
    def _tool_compress_output(self, text: str, level: str = "auto") -> Dict:
        """Compress text."""
        self._initialize_components()
        
        compressed, stats = self.compressor.compress(text, level)
        
        return {
            'original_text': text[:500] + '...' if len(text) > 500 else text,
            'compressed_text': compressed[:500] + '...' if len(compressed) > 500 else compressed,
            'stats': {
                'original_tokens': stats.original_tokens,
                'compressed_tokens': stats.compressed_tokens,
                'compression_ratio': stats.compression_ratio,
                'level': stats.level.value,
                'processing_time_ms': stats.processing_time_ms
            }
        }
    
    def _tool_get_stats(self) -> Dict:
        """Get statistics."""
        self._initialize_components()
        
        return {
            'indexer': self.indexer.get_stats() if self.indexer else {},
            'retriever': self.retriever.get_stats() if self.retriever else {},
            'compressor': self.compressor.get_stats() if self.compressor else {},
            'router': self.router.get_stats() if self.router else {},
            'current_project': self.current_project,
            'git': self.git.get_stats() if self.git else {},
            'dependency_graph': self.dependency_graph.get_stats() if self.dependency_graph else {},
            'query_history_size': len(self.query_history)
        }
    
    def _tool_clear_cache(self) -> Dict:
        """Clear all cached indexes."""
        import shutil
        
        if self.file_watcher:
            self.file_watcher.stop()
        
        clear_all_indexers()
        clear_retriever()
        clear_compressor()
        ModelCache.clear_cache()
        
        # Reinitialize
        self._initialize_components()
        self.current_project = None
        self.projects.clear()
        self.query_history.clear()
        
        cache_dir = Path.home() / '.kimi_cache' / 'indexes'
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        
        return {'success': True, 'message': 'All caches cleared'}
    
    def _tool_get_query_history(self, limit: int = 10) -> Dict:
        """Get query history."""
        history = list(self.query_history.values())[-limit:]
        return {
            'history': [
                {
                    'query': h.query,
                    'timestamp': h.timestamp,
                    'results_count': h.results_count,
                    'skill': h.skill
                }
                for h in reversed(history)
            ]
        }
    
    def _tool_switch_project(self, project_path: str) -> Dict:
        """Switch to a different project."""
        if project_path not in self.projects:
            raise MCPError(ERROR_INVALID_PARAMS, f"Project not indexed: {project_path}")
        
        self.current_project = project_path
        self.retriever.load_index(project_path)
        
        # Invalidate query cache
        self.retriever.invalidate_cache()
        
        return {'success': True, 'project': project_path}
    
    def _tool_list_projects(self) -> Dict:
        """List all indexed projects."""
        return {
            'projects': [
                {
                    'path': p['path'],
                    'indexed_at': p['indexed_at'],
                    'files_indexed': p['stats'].get('files_indexed', 0),
                    'chunks_created': p['stats'].get('chunks_created', 0)
                }
                for p in self.projects.values()
            ],
            'current_project': self.current_project
        }
    
    def _tool_get_dependencies(self, filepath: str) -> Dict:
        """Get dependencies for a file."""
        if not self.dependency_graph:
            raise MCPError(ERROR_INVALID_PARAMS, "No dependency graph available")
        
        return {
            'filepath': filepath,
            'dependencies': self.dependency_graph.get_dependencies(filepath),
            'dependents': self.dependency_graph.get_dependents(filepath),
            'related': list(self.dependency_graph.get_related_files(filepath, depth=2))
        }
    
    def _tool_find_similar_code(self, filepath: str) -> Dict:
        """Find similar code blocks."""
        if not self.indexer or not self.indexer.vector_store:
            raise MCPError(ERROR_INVALID_PARAMS, "No index available")
        
        # Get all chunks
        chunks = [
            (c.filepath, c.content)
            for c in self.indexer.vector_store.chunks
        ]
        
        # Find duplicates
        duplicates = self.similarity_detector.find_duplicates(chunks)
        
        # Filter for the requested file
        file_duplicates = [
            {
                'file1': d[0],
                'file2': d[1],
                'similarity': d[2]
            }
            for d in duplicates
            if filepath in (d[0], d[1])
        ]
        
        return {
            'filepath': filepath,
            'similar_blocks': file_duplicates[:10]
        }
    
    def _tool_summarize_chunk(self, content: str, chunk_type: str = 'other',
                              language: str = 'unknown') -> Dict:
        """Summarize a code chunk."""
        summary = self.summarizer.summarize_chunk(content, chunk_type, language)
        
        return {
            'summary': summary,
            'content_preview': content[:200] + '...' if len(content) > 200 else content
        }
    
    def _tool_export_index(self, output_path: str) -> Dict:
        """Export index to a file."""
        if not self.current_project:
            raise MCPError(ERROR_INVALID_PARAMS, "No project indexed")
        
        import hashlib
        project_hash = hashlib.md5(self.current_project.encode()).hexdigest()[:16]
        index_path = os.path.join(self.indexer.cache_dir, project_hash)
        
        # Copy files
        import shutil
        shutil.copy(f"{index_path}_chunks.json", f"{output_path}_chunks.json")
        shutil.copy(f"{index_path}_embeddings.npy", f"{output_path}_embeddings.npy")
        
        if os.path.exists(f"{index_path}_faiss.index"):
            shutil.copy(f"{index_path}_faiss.index", f"{output_path}_faiss.index")
        
        return {'success': True, 'exported_to': output_path}
    
    def _tool_import_index(self, input_path: str) -> Dict:
        """Import index from a file."""
        # This would need more implementation
        return {'success': False, 'message': 'Not fully implemented'}
    
    # ============ Traceability Tool Implementations ============
    
    def _ensure_traceability(self):
        """Ensure traceability analyzer is initialized."""
        if self.traceability is None:
            if not self.current_project:
                raise MCPError(ERROR_INVALID_PARAMS, "No project indexed. Call initialize_index first.")
            self.traceability = get_traceability(self.current_project)
    
    def _tool_generate_daily_report(self, date: str = None) -> Dict:
        """Generate a daily activity report."""
        self._ensure_traceability()
        
        report = self.traceability.generate_daily_report(date, save=True)
        
        return {
            'date': report.date,
            'commits_count': len(report.commits),
            'files_changed': len(report.files_changed),
            'additions': report.additions,
            'deletions': report.deletions,
            'summary': report.summary,
            'key_changes': report.key_changes,
            'new_files': report.new_files[:10],
            'modified_files': report.modified_files[:10],
            'deleted_files': report.deleted_files[:10],
            'report_path': str(self.traceability.reports_dir / f"daily_report_{report.date}.md")
        }
    
    def _tool_generate_weekly_report(self, week_start: str = None) -> Dict:
        """Generate a weekly activity report."""
        self._ensure_traceability()
        
        content = self.traceability.generate_weekly_report(week_start, save=True)
        
        # Extract filename from content
        filename = f"weekly_report_{week_start or 'current'}.md"
        
        return {
            'week_start': week_start,
            'report_path': str(self.traceability.reports_dir / filename),
            'preview': content[:500] + '...' if len(content) > 500 else content
        }
    
    def _tool_get_recent_activity(self, days: int = 7) -> Dict:
        """Get a quick summary of recent activity."""
        self._ensure_traceability()
        
        summary = self.traceability.get_traceability_summary(days)
        
        return {
            'days': days,
            'summary': summary,
            'reports_dir': str(self.traceability.reports_dir)
        }
    
    def _tool_list_traceability_reports(self) -> Dict:
        """List all generated traceability reports."""
        self._ensure_traceability()
        
        reports = self.traceability.list_reports()
        
        return {
            'reports': reports,
            'total': len(reports),
            'reports_dir': str(self.traceability.reports_dir)
        }
    
    def _tool_get_traceability_report(self, report_name: str) -> Dict:
        """Get the content of a specific traceability report."""
        self._ensure_traceability()
        
        content = self.traceability.get_report(report_name)
        
        if content is None:
            raise MCPError(ERROR_INVALID_PARAMS, f"Report not found: {report_name}")
        
        return {
            'report_name': report_name,
            'content': content,
            'line_count': len(content.split('\n'))
        }
    
    def _tool_start_traceability_session(self) -> Dict:
        """Start a new traceability session."""
        self._ensure_traceability()
        
        session_id = self.traceability.start_session()
        
        return {
            'session_id': session_id,
            'status': 'started',
            'message': 'Traceability session started. Queries and file accesses will be tracked.'
        }
    
    def _tool_end_traceability_session(self, generate_summary: bool = True) -> Dict:
        """End current traceability session."""
        self._ensure_traceability()
        
        session_id = self.traceability.end_session(generate_summary)
        
        if session_id is None:
            raise MCPError(ERROR_INVALID_PARAMS, "No active traceability session")
        
        return {
            'session_id': session_id,
            'status': 'ended',
            'generate_summary': generate_summary,
            'message': 'Traceability session ended and saved.'
        }
    
    # ============ Main Loop ============
    
    def handle_request(self, request: Dict) -> Optional[Dict]:
        """Handle a single JSON-RPC request."""
        if request.get('jsonrpc') != '2.0':
            return {
                'jsonrpc': '2.0',
                'id': request.get('id'),
                'error': self._create_error(ERROR_INVALID_REQUEST, 'Invalid JSON-RPC version')
            }
        
        method = request.get('method')
        params = request.get('params', {})
        req_id = request.get('id')
        
        # Skip logging for notifications
        skip_logging = method in ('notifications/initialized', 'notifications/cancelled')
        
        # Record request
        if not skip_logging:
            record_mcp_request(method, params)
        
        start_time = time.time()
        
        try:
            if method == 'initialize':
                result = self.handle_initialize(params)
            elif method == 'tools/list':
                result = self.handle_tools_list(params)
            elif method == 'tools/call':
                result = self.handle_tools_call(params)
            elif method == 'notifications/initialized':
                logger.info("Client initialized notification received")
                return None
            elif method == 'notifications/cancelled':
                logger.info("Request cancelled notification received")
                return None
            else:
                raise MCPError(ERROR_METHOD_NOT_FOUND, f"Method not found: {method}")
            
            # Record successful response
            if not skip_logging:
                duration_ms = int((time.time() - start_time) * 1000)
                record_mcp_response(method, result, duration_ms)
            
            if req_id is not None:
                return {'jsonrpc': '2.0', 'id': req_id, 'result': result}
            return None
            
        except MCPError as e:
            # Record error
            if not skip_logging:
                record_mcp_error(method, e.message, params)
            
            if req_id is not None:
                return {'jsonrpc': '2.0', 'id': req_id, 'error': self._create_error(e.code, e.message, e.data)}
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            
            # Record error
            if not skip_logging:
                record_mcp_error(method, str(e), params)
            
            if req_id is not None:
                return {'jsonrpc': '2.0', 'id': req_id, 'error': self._create_error(ERROR_INTERNAL_ERROR, str(e))}
            return None
    
    def run(self):
        """Run the MCP server main loop."""
        self.running = True
        logger.info("MCP Server started, waiting for requests...")
        
        # Record server start
        record_mcp_request('server_start', {'status': 'initializing'})
        record_mcp_response('server_start', {'status': 'ready'}, 0)
        
        while self.running:
            try:
                line = sys.stdin.readline()
                
                if not line:
                    logger.info("EOF reached, shutting down")
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    self._send_response(None, error=self._create_error(ERROR_PARSE_ERROR, str(e)))
                    continue
                
                response = self.handle_request(request)
                
                if response:
                    sys.stdout.write(json.dumps(response) + '\n')
                    sys.stdout.flush()
                    
            except KeyboardInterrupt:
                logger.info("Interrupted, shutting down")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
        
        # Cleanup
        if self.file_watcher:
            self.file_watcher.stop()
        
        self.running = False
        logger.info("MCP Server stopped")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='PIMCP MCP Server')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("PIMCP MCP Server v0.2.0")
    logger.info("=" * 60)
    logger.info("Protocol: JSON-RPC 2.0")
    logger.info("Tools: 21 available")
    logger.info("Activity log: ~/.kimi_cache/activity.json")
    logger.info("-" * 60)
    
    server = MCPServer()
    server.run()


if __name__ == '__main__':
    main()
