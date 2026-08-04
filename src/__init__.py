"""
Kimi Project Intelligence MCP (Kimi-PIMCP) - OPTIMIZED VERSION
A Model Context Protocol server for Kimi-CLI with semantic indexing and intelligent context retrieval.

New features in v0.2.0:
- Incremental indexing
- Query caching with LRU
- File watching for auto-reindex
- Dependency graph analysis
- Git integration
- Code summarization
- Similar code detection
- REST API
- Web UI
"""

__version__ = "0.2.0"
__author__ = "Kimi-PIMCP Team"

# Core modules
from .indexer import (
    ProjectIndexer, get_indexer, clear_all_indexers,
    CodeChunk, FileInfo, VectorStore, ModelCache,
    CompiledPatterns, CodeParser
)

from .retriever import (
    ContextRetriever, get_retriever, clear_retriever,
    RetrievalResult, QueryCache, FuzzySearcher,
    MMREtriever
)

from .compressor import (
    CavemanCompressor, get_compressor, clear_compressor,
    CompressionStats, CompressionLevel,
    TokenCounter, CompressionCache
)

from .skills.router import (
    SkillRouter, get_router, RoutingResult,
    IntentClassifier
)

from .skills.base import (
    BaseSkill, SkillType, SkillConfig, SkillContext,
    DebuggerSkill, ArchitectSkill, ExplainerSkill,
    TesterSkill, CavemanSkill
)

# New modules
from .file_watcher import (
    ProjectFileWatcher, PollingWatcher,
    FileChangeEvent, FileChangeType
)

from .dependency_graph import (
    DependencyGraph, DependencyParser,
    Dependency, FileNode
)

from .git_integration import (
    GitIntegration, IncrementalIndexer,
    GitChange, ChangeType
)

from .code_summarizer import (
    CodeSummarizer, SimilarCodeDetector,
    CodeElement, CodeElementType
)

# Server
from .server import MCPServer

__all__ = [
    # Version
    '__version__',
    '__author__',
    
    # Indexer
    'ProjectIndexer',
    'get_indexer',
    'clear_all_indexers',
    'CodeChunk',
    'FileInfo',
    'VectorStore',
    'ModelCache',
    'CompiledPatterns',
    'CodeParser',
    
    # Retriever
    'ContextRetriever',
    'get_retriever',
    'clear_retriever',
    'RetrievalResult',
    'QueryCache',
    'FuzzySearcher',
    'MMREtriever',
    
    # Compressor
    'CavemanCompressor',
    'get_compressor',
    'clear_compressor',
    'CompressionStats',
    'CompressionLevel',
    'TokenCounter',
    'CompressionCache',
    
    # Router
    'SkillRouter',
    'get_router',
    'RoutingResult',
    'IntentClassifier',
    
    # Skills
    'BaseSkill',
    'SkillType',
    'SkillConfig',
    'SkillContext',
    'DebuggerSkill',
    'ArchitectSkill',
    'ExplainerSkill',
    'TesterSkill',
    'CavemanSkill',
    
    # File Watcher
    'ProjectFileWatcher',
    'PollingWatcher',
    'FileChangeEvent',
    'FileChangeType',
    
    # Dependency Graph
    'DependencyGraph',
    'DependencyParser',
    'Dependency',
    'FileNode',
    
    # Git Integration
    'GitIntegration',
    'IncrementalIndexer',
    'GitChange',
    'ChangeType',
    
    # Code Summarizer
    'CodeSummarizer',
    'SimilarCodeDetector',
    'CodeElement',
    'CodeElementType',
    
    # Server
    'MCPServer',
]
