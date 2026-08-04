"""
REST API Module for Kimi-PIMCP
HTTP API for accessing indexer, retriever, and other services.
"""

import os
import sys
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import asdict
from contextlib import asynccontextmanager
import logging

# Try to import FastAPI
try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available. Install with: pip install fastapi uvicorn")
    sys.exit(1)

import uvicorn

# Import our modules
try:
    from indexer import ProjectIndexer, get_indexer, clear_all_indexers
    from retriever import ContextRetriever, get_retriever, clear_retriever
    from compressor import CavemanCompressor, get_compressor, clear_compressor
    from skills.router import SkillRouter, get_router
    from file_watcher import ProjectFileWatcher
    from dependency_graph import DependencyGraph
    from git_integration import GitIntegration
except ImportError:
    from .indexer import ProjectIndexer, get_indexer, clear_all_indexers
    from .retriever import ContextRetriever, get_retriever, clear_retriever
    from .compressor import CavemanCompressor, get_compressor, clear_compressor
    from .skills.router import SkillRouter, get_router
    from .file_watcher import ProjectFileWatcher
    from .dependency_graph import DependencyGraph
    from .git_integration import GitIntegration

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Pydantic models for request/response
class IndexRequest(BaseModel):
    project_path: str = Field(..., description="Path to the project to index")
    force_reindex: bool = Field(False, description="Force full reindex")


class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results")
    filter_ext: Optional[List[str]] = Field(None, description="Filter by file extensions")
    use_mmr: bool = Field(True, description="Use MMR for diversity")


class CompressRequest(BaseModel):
    text: str = Field(..., description="Text to compress")
    level: str = Field("auto", description="Compression level: auto/lite/full/ultra/wenyan")


class SkillRequest(BaseModel):
    query: str = Field(..., description="Query to classify")


class ProjectInfo(BaseModel):
    project_path: str
    is_indexed: bool
    file_count: int
    chunk_count: int


# Global state
class APIState:
    """Global API state."""
    def __init__(self):
        self.indexer: Optional[ProjectIndexer] = None
        self.retriever: Optional[ContextRetriever] = None
        self.compressor: Optional[CavemanCompressor] = None
        self.router: Optional[SkillRouter] = None
        self.file_watcher: Optional[ProjectFileWatcher] = None
        self.dependency_graph: Optional[DependencyGraph] = None
        self.git: Optional[GitIntegration] = None
        self.current_project: Optional[str] = None


state = APIState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting Kimi-PIMCP REST API...")
    state.indexer = get_indexer()
    state.retriever = get_retriever()
    state.compressor = get_compressor()
    state.router = get_router()
    yield
    # Shutdown
    logger.info("Shutting down Kimi-PIMCP REST API...")
    if state.file_watcher:
        state.file_watcher.stop()
    clear_all_indexers()
    clear_retriever()
    clear_compressor()


# Create FastAPI app
app = FastAPI(
    title="Kimi-PIMCP API",
    description="REST API for Kimi Project Intelligence MCP",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "current_project": state.current_project
    }


# Index endpoints
@app.post("/index")
async def index_project(request: IndexRequest, background_tasks: BackgroundTasks):
    """Index a project."""
    try:
        stats = state.indexer.index_project(
            request.project_path,
            force_reindex=request.force_reindex
        )
        
        # Load index in retriever
        state.retriever.load_index(request.project_path)
        state.current_project = request.project_path
        
        # Setup file watcher
        if state.file_watcher:
            state.file_watcher.stop()
        
        def on_file_change(event):
            logger.info(f"File changed: {event.filepath}")
            # Trigger incremental reindex
            try:
                state.indexer.index_project(request.project_path)
                state.retriever.load_index(request.project_project)
            except Exception as e:
                logger.error(f"Error reindexing: {e}")
        
        state.file_watcher = ProjectFileWatcher(
            request.project_path,
            on_file_change,
            debounce_seconds=2.0
        )
        state.file_watcher.start()
        
        # Build dependency graph
        state.dependency_graph = DependencyGraph(request.project_path)
        state.dependency_graph.build()
        
        # Setup git integration
        state.git = GitIntegration(request.project_path)
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error indexing project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/index/status")
async def index_status():
    """Get indexing status."""
    return {
        "current_project": state.current_project,
        "is_indexed": state.indexer and state.indexer.vector_store is not None,
        "stats": state.indexer.get_stats() if state.indexer else {}
    }


# Query endpoints
@app.post("/query")
async def query_context(request: QueryRequest):
    """Query the indexed project."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="No project indexed. Call /index first.")
    
    try:
        results = state.retriever.query_with_context(
            query=request.query,
            top_k=request.top_k,
            filter_ext=request.filter_ext,
            use_mmr=request.use_mmr
        )
        
        return {
            "query": request.query,
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error querying: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Compression endpoints
@app.post("/compress")
async def compress_text(request: CompressRequest):
    """Compress text using caveman heuristics."""
    try:
        compressed, stats = state.compressor.compress(request.text, request.level)
        
        return {
            "original_text": request.text[:500] + "..." if len(request.text) > 500 else request.text,
            "compressed_text": compressed[:500] + "..." if len(compressed) > 500 else compressed,
            "stats": {
                "original_tokens": stats.original_tokens,
                "compressed_tokens": stats.compressed_tokens,
                "compression_ratio": stats.compression_ratio,
                "level": stats.level.value,
                "processing_time_ms": stats.processing_time_ms
            }
        }
    except Exception as e:
        logger.error(f"Error compressing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Skill endpoints
@app.post("/skills/select")
async def select_skill(request: SkillRequest):
    """Select the best skill for a query."""
    try:
        # Get retrieved files if project is indexed
        retrieved_files = []
        if state.current_project:
            try:
                results = state.retriever.query(request.query, top_k=3)
                retrieved_files = [
                    {
                        "filepath": r.chunk.filepath,
                        "chunk_type": r.chunk.chunk_type,
                        "similarity_score": r.similarity_score
                    }
                    for r in results
                ]
            except Exception:
                pass
        
        result = state.router.execute_skill(
            request.query,
            retrieved_files=retrieved_files,
            project_path=state.current_project or ""
        )
        
        return result
    except Exception as e:
        logger.error(f"Error selecting skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/skills")
async def list_skills():
    """List available skills."""
    return {
        "skills": state.router.list_skills() if state.router else []
    }


# Stats endpoints
@app.get("/stats")
async def get_stats():
    """Get all statistics."""
    return {
        "indexer": state.indexer.get_stats() if state.indexer else {},
        "retriever": state.retriever.get_stats() if state.retriever else {},
        "compressor": state.compressor.get_stats() if state.compressor else {},
        "router": state.router.get_stats() if state.router else {},
        "current_project": state.current_project,
        "git": state.git.get_stats() if state.git else {}
    }


# Dependency graph endpoints
@app.get("/dependencies")
async def get_dependencies(filepath: str):
    """Get dependencies for a file."""
    if not state.dependency_graph:
        raise HTTPException(status_code=400, detail="No dependency graph available")
    
    return {
        "filepath": filepath,
        "dependencies": state.dependency_graph.get_dependencies(filepath),
        "dependents": state.dependency_graph.get_dependents(filepath),
        "related": list(state.dependency_graph.get_related_files(filepath))
    }


@app.get("/dependencies/stats")
async def get_dependency_stats():
    """Get dependency graph statistics."""
    if not state.dependency_graph:
        raise HTTPException(status_code=400, detail="No dependency graph available")
    
    return state.dependency_graph.get_stats()


@app.get("/dependencies/cycles")
async def get_circular_dependencies():
    """Get circular dependencies."""
    if not state.dependency_graph:
        raise HTTPException(status_code=400, detail="No dependency graph available")
    
    cycles = state.dependency_graph.find_circular_dependencies()
    return {
        "cycles_count": len(cycles),
        "cycles": cycles[:10]  # Limit to first 10
    }


# Git endpoints
@app.get("/git/status")
async def git_status():
    """Get Git status."""
    if not state.git or not state.git.is_git_repo():
        return {"is_git_repo": False}
    
    return {
        "is_git_repo": True,
        "stats": state.git.get_stats(),
        "changed_files": len(state.git.get_changed_files_since("HEAD")),
        "untracked_files": len(state.git.get_untracked_files()[:20])
    }


@app.get("/git/changes")
async def git_changes(since: str = "HEAD"):
    """Get changed files since a reference."""
    if not state.git or not state.git.is_git_repo():
        raise HTTPException(status_code=400, detail="Not a Git repository")
    
    changes = state.git.get_changed_files_since(since)
    return {
        "since": since,
        "changes_count": len(changes),
        "changes": [
            {
                "filepath": c.filepath,
                "type": c.change_type.value
            }
            for c in changes[:50]
        ]
    }


# Cache management
@app.post("/cache/clear")
async def clear_cache():
    """Clear all caches."""
    if state.file_watcher:
        state.file_watcher.stop()
    
    clear_all_indexers()
    clear_retriever()
    clear_compressor()
    
    # Reinitialize
    state.indexer = get_indexer()
    state.retriever = get_retriever()
    state.compressor = get_compressor()
    state.current_project = None
    state.dependency_graph = None
    state.git = None
    
    return {"success": True, "message": "All caches cleared"}


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the REST API server."""
    uvicorn.run("rest_api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kimi-PIMCP REST API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    start_server(host=args.host, port=args.port, reload=args.reload)
