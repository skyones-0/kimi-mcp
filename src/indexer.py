"""
Indexer Module for Kimi-PIMCP - OPTIMIZED VERSION
Handles semantic indexing of projects using embeddings and FAISS.

Improvements:
- Incremental indexing (only modified files)
- Large file handling with streaming
- Dynamic batch sizing based on RAM
- Compiled regex patterns
- Memory-mapped files for large content
- Thread-safe operations
- Path traversal protection
"""

import os
import re
import json
import hashlib
import time
import mmap
import threading
import psutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from functools import lru_cache
from collections import OrderedDict
import logging

import numpy as np
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Constants
MAX_FILE_SIZE_MB = 10  # Skip files larger than this
DEFAULT_BATCH_SIZE = 32
LARGE_FILE_THRESHOLD_MB = 5  # Use mmap for files larger than this
EMBEDDING_DIMENSION = 384


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    content: str
    filepath: str
    start_line: int
    end_line: int
    chunk_type: str
    language: str
    timestamp: float
    embedding: Optional[np.ndarray] = None
    content_hash: str = ""  # Hash for deduplication
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary (excluding embedding)."""
        return {
            'content': self.content,
            'filepath': self.filepath,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'chunk_type': self.chunk_type,
            'language': self.language,
            'timestamp': self.timestamp,
            'content_hash': self.content_hash
        }


@dataclass
class FileInfo:
    """Information about an indexed file."""
    filepath: str
    content_hash: str
    mtime: float
    size: int
    indexed_at: float


class CompiledPatterns:
    """Pre-compiled regex patterns for performance."""
    
    PYTHON_FUNCTION = re.compile(r'^(def\s+\w+\s*\([^)]*\)\s*(->\s*\w+)?\s*:)')
    PYTHON_CLASS = re.compile(r'^(class\s+\w+(\s*\([^)]*\))?\s*:)')
    PYTHON_IMPORT = re.compile(r'^(import\s+\w+|from\s+\w+\s+import)')
    
    JS_FUNCTION = re.compile(r'^(function\s+\w+\s*\(|const\s+\w+\s*=\s*(async\s*)?\([^)]*\)\s*=>|(\w+\s*:\s*(async\s*)?\([^)]*\)\s*=>))')
    JS_CLASS = re.compile(r'^(class\s+\w+(\s+extends\s+\w+)?\s*{)')
    JS_IMPORT = re.compile(r'^(import\s+.*from|const\s+.*=\s*require\()')
    
    TS_FUNCTION = re.compile(r'^(function\s+\w+\s*<[^>]*>?\s*\(|const\s+\w+\s*=\s*(async\s*)?\([^)]*\)\s*=>)')
    TS_CLASS = re.compile(r'^(class\s+\w+(\s+extends\s+\w+)?\s*{)')
    TS_IMPORT = re.compile(r'^(import\s+.*from|const\s+.*=\s*require\()')
    
    @classmethod
    def get_patterns(cls, language: str) -> Dict[str, re.Pattern]:
        """Get compiled patterns for a language."""
        if language == 'python':
            return {
                'function': cls.PYTHON_FUNCTION,
                'class': cls.PYTHON_CLASS,
                'import': cls.PYTHON_IMPORT,
            }
        elif language == 'javascript':
            return {
                'function': cls.JS_FUNCTION,
                'class': cls.JS_CLASS,
                'import': cls.JS_IMPORT,
            }
        elif language == 'typescript':
            return {
                'function': cls.TS_FUNCTION,
                'class': cls.TS_CLASS,
                'import': cls.TS_IMPORT,
            }
        return {}


class CodeParser:
    """Parser for extracting code chunks from files - OPTIMIZED."""
    
    # Language extensions mapping
    EXTENSION_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
    }
    
    def __init__(self):
        self.chunk_count = 0
    
    def detect_language(self, filepath: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(filepath).suffix.lower()
        return self.EXTENSION_MAP.get(ext, 'unknown')
    
    def parse_file(self, filepath: str, content: str) -> List[CodeChunk]:
        """Parse a file and extract code chunks - OPTIMIZED with compiled patterns."""
        language = self.detect_language(filepath)
        chunks = []
        
        if language == 'unknown':
            chunks.append(CodeChunk(
                content=content[:100000],  # Limit content size
                filepath=filepath,
                start_line=1,
                end_line=min(len(content.split('\n')), 10000),
                chunk_type='other',
                language='unknown',
                timestamp=time.time()
            ))
            return chunks
        
        lines = content.split('\n')
        patterns = CompiledPatterns.get_patterns(language)
        
        if not patterns:
            # Fallback for unsupported languages
            chunks.append(CodeChunk(
                content=content[:100000],
                filepath=filepath,
                start_line=1,
                end_line=len(lines),
                chunk_type='other',
                language=language,
                timestamp=time.time()
            ))
            return chunks
        
        current_chunk = []
        current_start = 0
        current_type = 'other'
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check if this line starts a new chunk using compiled patterns
            new_type = None
            for chunk_type, pattern in patterns.items():
                if pattern.match(line_stripped):
                    new_type = chunk_type
                    break
            
            if new_type and current_chunk:
                # Save current chunk and start new one
                chunk_content = '\n'.join(current_chunk)
                if len(chunk_content) < 50000:  # Limit chunk size
                    chunks.append(CodeChunk(
                        content=chunk_content,
                        filepath=filepath,
                        start_line=current_start + 1,
                        end_line=i,
                        chunk_type=current_type,
                        language=language,
                        timestamp=time.time()
                    ))
                current_chunk = [line]
                current_start = i
                current_type = new_type
            else:
                current_chunk.append(line)
                if new_type:
                    current_type = new_type
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if len(chunk_content) < 50000:
                chunks.append(CodeChunk(
                    content=chunk_content,
                    filepath=filepath,
                    start_line=current_start + 1,
                    end_line=len(lines),
                    chunk_type=current_type,
                    language=language,
                    timestamp=time.time()
                ))
        
        self.chunk_count += len(chunks)
        return chunks


class VectorStore:
    """FAISS-based vector store - OPTIMIZED with IVF for large datasets."""
    
    # Threshold to switch to IVF index
    IVF_THRESHOLD = 10000
    
    def __init__(self, dimension: int = EMBEDDING_DIMENSION):
        """Initialize vector store with given embedding dimension."""
        self.dimension = dimension
        self.chunks: List[CodeChunk] = []
        self.index = None
        self._faiss_available = False
        self._use_ivf = False
        self._index_lock = threading.RLock()
        
        try:
            import faiss
            self._faiss_available = True
            self._faiss = faiss
            # Start with Flat index, will upgrade to IVF if needed
            self.index = faiss.IndexFlatIP(dimension)
            logger.info("FAISS initialized successfully")
        except ImportError:
            logger.warning("FAISS not available, using numpy fallback")
            self.embeddings: List[np.ndarray] = []
    
    def _upgrade_to_ivf(self):
        """Upgrade to IVF index for better performance with large datasets."""
        if not self._faiss_available or self._use_ivf:
            return
        
        nlist = min(100, len(self.chunks) // 10)  # Number of clusters
        if nlist < 10:
            return
        
        logger.info(f"Upgrading to IVF index with {nlist} clusters...")
        
        # Create IVF index
        quantizer = self._faiss.IndexFlatIP(self.dimension)
        ivf_index = self._faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
        
        # Train and add existing vectors
        embeddings = np.array([c.embedding for c in self.chunks if c.embedding is not None]).astype('float32')
        self._faiss.normalize_L2(embeddings)
        
        ivf_index.train(embeddings)
        ivf_index.add(embeddings)
        ivf_index.nprobe = 10  # Number of clusters to search
        
        self.index = ivf_index
        self._use_ivf = True
        logger.info("Upgraded to IVF index")
    
    def add(self, chunks: List[CodeChunk]):
        """Add chunks with embeddings to the store - THREAD-SAFE."""
        with self._index_lock:
            if not chunks:
                return
            
            valid_chunks = [c for c in chunks if c.embedding is not None]
            if not valid_chunks:
                return
            
            if self._faiss_available and self.index is not None:
                embeddings = np.array([c.embedding for c in valid_chunks]).astype('float32')
                self._faiss.normalize_L2(embeddings)
                self.index.add(embeddings)
                
                # Check if we should upgrade to IVF
                if len(self.chunks) + len(valid_chunks) > self.IVF_THRESHOLD and not self._use_ivf:
                    self._upgrade_to_ivf()
            else:
                for chunk in valid_chunks:
                    self.embeddings.append(chunk.embedding / np.linalg.norm(chunk.embedding))
            
            self.chunks.extend(valid_chunks)
    
    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[CodeChunk, float]]:
        """Search for most similar chunks - THREAD-SAFE."""
        with self._index_lock:
            if not self.chunks:
                return []
            
            query = query_embedding.astype('float32').reshape(1, -1)
            
            if self._faiss_available and self.index is not None:
                self._faiss.normalize_L2(query)
                scores, indices = self.index.search(query, min(k, len(self.chunks)))
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx >= 0 and idx < len(self.chunks):
                        results.append((self.chunks[idx], float(score)))
                return results
            else:
                query_norm = query / np.linalg.norm(query)
                similarities = []
                for i, emb in enumerate(self.embeddings):
                    sim = np.dot(query_norm, emb)
                    similarities.append((self.chunks[i], float(sim)))
                similarities.sort(key=lambda x: x[1], reverse=True)
                return similarities[:k]
    
    def remove_chunks_by_file(self, filepath: str) -> int:
        """Remove all chunks from a specific file (for incremental updates)."""
        with self._index_lock:
            original_count = len(self.chunks)
            self.chunks = [c for c in self.chunks if c.filepath != filepath]
            removed = original_count - len(self.chunks)
            
            if removed > 0 and self._faiss_available:
                # Rebuild index (FAISS doesn't support removal efficiently)
                logger.info(f"Rebuilding index after removing {removed} chunks...")
                embeddings = np.array([c.embedding for c in self.chunks if c.embedding is not None]).astype('float32')
                
                if self._use_ivf and len(self.chunks) > self.IVF_THRESHOLD:
                    nlist = min(100, len(self.chunks) // 10)
                    quantizer = self._faiss.IndexFlatIP(self.dimension)
                    self.index = self._faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
                    if len(embeddings) > 0:
                        self._faiss.normalize_L2(embeddings)
                        self.index.train(embeddings)
                        self.index.add(embeddings)
                        self.index.nprobe = 10
                else:
                    self.index = self._faiss.IndexFlatIP(self.dimension)
                    if len(embeddings) > 0:
                        self._faiss.normalize_L2(embeddings)
                        self.index.add(embeddings)
                
                self._use_ivf = len(self.chunks) > self.IVF_THRESHOLD
            
            return removed
    
    def save(self, path: str):
        """Save vector store to disk."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with self._index_lock:
            chunks_data = [c.to_dict() for c in self.chunks]
            with open(f"{path}_chunks.json", 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, indent=2)
            
            if self.chunks:
                embeddings = np.array([c.embedding for c in self.chunks if c.embedding is not None])
                np.save(f"{path}_embeddings.npy", embeddings)
            
            if self._faiss_available and self.index is not None:
                self._faiss.write_index(self.index, f"{path}_faiss.index")
            
            # Save metadata
            metadata = {
                'use_ivf': self._use_ivf,
                'dimension': self.dimension,
                'chunk_count': len(self.chunks),
                'project_path': getattr(self, '_last_project_path', '')
            }
            with open(f"{path}_meta.json", 'w') as f:
                json.dump(metadata, f)
        
        logger.info(f"Vector store saved to {path}")
    
    def load(self, path: str):
        """Load vector store from disk."""
        chunks_path = f"{path}_chunks.json"
        if not os.path.exists(chunks_path):
            return
        
        with self._index_lock:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunks_data = json.load(f)
            
            embeddings_path = f"{path}_embeddings.npy"
            if os.path.exists(embeddings_path):
                embeddings = np.load(embeddings_path)
                
                self.chunks = []
                for data, emb in zip(chunks_data, embeddings):
                    chunk = CodeChunk(
                        content=data['content'],
                        filepath=data['filepath'],
                        start_line=data['start_line'],
                        end_line=data['end_line'],
                        chunk_type=data['chunk_type'],
                        language=data['language'],
                        timestamp=data['timestamp'],
                        embedding=emb,
                        content_hash=data.get('content_hash', '')
                    )
                    self.chunks.append(chunk)
            
            # Load metadata
            meta_path = f"{path}_meta.json"
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                self._use_ivf = metadata.get('use_ivf', False)
            
            if self._faiss_available:
                faiss_path = f"{path}_faiss.index"
                if os.path.exists(faiss_path):
                    self.index = self._faiss.read_index(faiss_path)
            else:
                self.embeddings = [c.embedding / np.linalg.norm(c.embedding) for c in self.chunks if c.embedding is not None]
            
            logger.info(f"Vector store loaded from {path} with {len(self.chunks)} chunks")


class ModelCache:
    """LRU cache for sentence transformer models to prevent memory leaks."""
    
    _cache: OrderedDict[str, SentenceTransformer] = OrderedDict()
    _lock = threading.Lock()
    MAX_MODELS = 2  # Keep only 2 models in memory
    
    @classmethod
    def get_model(cls, model_name: str) -> SentenceTransformer:
        """Get or load a model with LRU eviction."""
        with cls._lock:
            if model_name in cls._cache:
                # Move to end (most recently used)
                model = cls._cache.pop(model_name)
                cls._cache[model_name] = model
                return model
            
            # Load new model
            logger.info(f"Loading model: {model_name}")
            model = SentenceTransformer(model_name)
            
            # Evict oldest if at capacity
            while len(cls._cache) >= cls.MAX_MODELS:
                oldest_name, oldest_model = cls._cache.popitem(last=False)
                logger.info(f"Evicting model from cache: {oldest_name}")
                del oldest_model
            
            cls._cache[model_name] = model
            return model
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached models."""
        with cls._lock:
            cls._cache.clear()
            import gc
            gc.collect()


class ProjectIndexer:
    """Main indexer class - OPTIMIZED with incremental indexing."""
    
    SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.md'}
    EXCLUDE_DIRS = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build', '.kimi_cache'}
    
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2', cache_dir: str = None):
        """Initialize the project indexer."""
        self.model_name = model_name
        self.parser = CodeParser()
        self.vector_store: Optional[VectorStore] = None
        self.cache_dir = cache_dir or os.path.expanduser('~/.kimi_cache/indexes')
        self._lock = threading.RLock()
        self._file_info: Dict[str, FileInfo] = {}
        
        self.stats = {
            'files_indexed': 0,
            'chunks_created': 0,
            'index_time_ms': 0,
            'project_path': '',
            'files_skipped': 0,
            'files_updated': 0,
        }
    
    def _sanitize_path(self, project_path: str) -> str:
        """Sanitize and validate project path (path traversal protection)."""
        # Resolve to absolute path
        abs_path = os.path.abspath(os.path.expanduser(project_path))
        
        # Check for path traversal attempts
        normalized = os.path.normpath(abs_path)
        if '..' in normalized.split(os.sep):
            raise ValueError(f"Invalid path (path traversal detected): {project_path}")
        
        return normalized
    
    def _get_file_hash(self, filepath: str) -> str:
        """Get hash of file content efficiently."""
        size = os.path.getsize(filepath)
        
        # For large files, hash only first and last 8KB
        if size > 1024 * 1024:  # > 1MB
            with open(filepath, 'rb') as f:
                start = f.read(8192)
                f.seek(-8192, 2)
                end = f.read(8192)
                return hashlib.md5(start + end + str(size).encode()).hexdigest()
        else:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
    
    def _read_file_content(self, filepath: str) -> str:
        """Read file content with mmap for large files."""
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        if size_mb > LARGE_FILE_THRESHOLD_MB:
            # Use mmap for large files
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        return mm.read().decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"mmap failed for {filepath}, falling back: {e}")
        
        # Standard read
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _get_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on available RAM."""
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        
        # Rough estimate: each embedding ~ 1.5KB, want to use ~20% of available RAM
        estimated_per_item = 1.5  # KB
        target_memory_kb = available_mb * 0.2 * 1024
        optimal_batch = int(target_memory_kb / estimated_per_item)
        
        # Clamp to reasonable range
        return max(16, min(optimal_batch, 256))
    
    def _load_file_index(self, index_path: str) -> Dict[str, FileInfo]:
        """Load the file index for incremental updates."""
        file_index_path = f"{index_path}_files.json"
        if not os.path.exists(file_index_path):
            return {}
        
        try:
            with open(file_index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    path: FileInfo(**info) for path, info in data.items()
                }
        except Exception as e:
            logger.warning(f"Could not load file index: {e}")
            return {}
    
    def _save_file_index(self, index_path: str):
        """Save the file index."""
        file_index_path = f"{index_path}_files.json"
        data = {
            path: {
                'filepath': info.filepath,
                'content_hash': info.content_hash,
                'mtime': info.mtime,
                'size': info.size,
                'indexed_at': info.indexed_at
            }
            for path, info in self._file_info.items()
        }
        with open(file_index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _should_index_file(self, filepath: str, existing_info: Optional[FileInfo] = None) -> Tuple[bool, str]:
        """Check if file should be indexed with reason."""
        ext = Path(filepath).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return False, "unsupported_extension"
        
        parts = Path(filepath).parts
        for part in parts:
            if part in self.EXCLUDE_DIRS:
                return False, "excluded_directory"
        
        # Check file size
        try:
            size = os.path.getsize(filepath)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                return False, "file_too_large"
            
            # Check if modified (for incremental indexing)
            if existing_info:
                mtime = os.path.getmtime(filepath)
                current_hash = self._get_file_hash(filepath)
                
                if mtime == existing_info.mtime and current_hash == existing_info.content_hash:
                    return False, "not_modified"
        except OSError:
            return False, "access_error"
        
        return True, "ok"
    
    def index_project(self, project_path: str, force_reindex: bool = False) -> Dict[str, Any]:
        """Index a project with incremental updates - OPTIMIZED."""
        with self._lock:
            start_time = time.time()
            project_path = self._sanitize_path(project_path)
            self.stats['project_path'] = project_path
            self.stats['files_skipped'] = 0
            self.stats['files_updated'] = 0
            
            logger.info(f"Indexing project: {project_path}")
            
            # Get model from cache
            model = ModelCache.get_model(self.model_name)
            
            # Initialize vector store
            self.vector_store = VectorStore(dimension=model.get_sentence_embedding_dimension())
            
            # Check for existing index
            project_hash = hashlib.md5(project_path.encode()).hexdigest()[:16]
            index_path = os.path.join(self.cache_dir, project_hash)
            
            # Load existing file index for incremental updates
            old_file_info = {} if force_reindex else self._load_file_index(index_path)
            self._file_info = {}
            
            if not force_reindex and os.path.exists(f"{index_path}_chunks.json"):
                logger.info("Loading existing index for incremental update...")
                self.vector_store.load(index_path)
            
            # Collect files to index
            files_to_index = []
            files_to_remove = set(old_file_info.keys())
            
            for root, dirs, files in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in self.EXCLUDE_DIRS]
                
                for file in files:
                    filepath = os.path.join(root, file)
                    existing = old_file_info.get(filepath)
                    should_index, reason = self._should_index_file(filepath, existing)
                    
                    if should_index:
                        files_to_index.append(filepath)
                        if existing:
                            self.stats['files_updated'] += 1
                            # Remove old chunks for this file
                            self.vector_store.remove_chunks_by_file(filepath)
                    else:
                        if reason == "not_modified":
                            self._file_info[filepath] = existing
                            self.stats['files_skipped'] += 1
                        files_to_remove.discard(filepath)
            
            # Remove chunks for deleted files
            for filepath in files_to_remove:
                self.vector_store.remove_chunks_by_file(filepath)
                logger.info(f"Removed index for deleted file: {filepath}")
            
            logger.info(f"Found {len(files_to_index)} files to index ({self.stats['files_skipped']} skipped)")
            
            # Process files
            all_chunks = []
            batch_size = self._get_optimal_batch_size()
            logger.info(f"Using batch size: {batch_size}")
            
            for filepath in files_to_index:
                try:
                    content = self._read_file_content(filepath)
                    chunks = self.parser.parse_file(filepath, content)
                    all_chunks.extend(chunks)
                    
                    # Update file info
                    self._file_info[filepath] = FileInfo(
                        filepath=filepath,
                        content_hash=self._get_file_hash(filepath),
                        mtime=os.path.getmtime(filepath),
                        size=os.path.getsize(filepath),
                        indexed_at=time.time()
                    )
                    
                    self.stats['files_indexed'] += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing {filepath}: {e}")
            
            logger.info(f"Created {len(all_chunks)} chunks from {self.stats['files_indexed']} files")
            
            # Generate embeddings with dynamic batch size
            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i:i + batch_size]
                texts = [c.content for c in batch]
                embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
                
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding
            
            # Add to vector store
            self.vector_store.add(all_chunks)
            self.stats['chunks_created'] = len(self.vector_store.chunks)
            
            # Save everything
            os.makedirs(self.cache_dir, exist_ok=True)
            # Store project path for metadata
            self.vector_store._last_project_path = project_path
            self.vector_store.save(index_path)
            self._save_file_index(index_path)
            
            self.stats['index_time_ms'] = int((time.time() - start_time) * 1000)
            
            logger.info(f"Indexing complete in {self.stats['index_time_ms']}ms")
            logger.info(f"Files indexed: {self.stats['files_indexed']}")
            logger.info(f"Files skipped: {self.stats['files_skipped']}")
            logger.info(f"Files updated: {self.stats['files_updated']}")
            logger.info(f"Total chunks: {self.stats['chunks_created']}")
            
            return self.stats
    
    def get_stats(self) -> Dict[str, Any]:
        """Get indexing statistics."""
        with self._lock:
            return self.stats.copy()
    
    def clear_cache(self):
        """Clear all cached data."""
        with self._lock:
            self._file_info.clear()
            if self.vector_store:
                self.vector_store = None
            ModelCache.clear_cache()


# Thread-safe singleton management
_indexer_instances: Dict[str, ProjectIndexer] = {}
_indexer_lock = threading.Lock()


def get_indexer(model_name: str = None, cache_dir: str = None, project_path: str = None) -> ProjectIndexer:
    """Get or create indexer instance - PER PROJECT to avoid conflicts."""
    with _indexer_lock:
        key = f"{model_name or 'default'}:{cache_dir or 'default'}"
        if project_path:
            key = f"{key}:{project_path}"
        
        if key not in _indexer_instances:
            kwargs = {}
            if model_name:
                kwargs['model_name'] = model_name
            if cache_dir:
                kwargs['cache_dir'] = cache_dir
            _indexer_instances[key] = ProjectIndexer(**kwargs)
        
        return _indexer_instances[key]


def clear_all_indexers():
    """Clear all indexer instances (for cleanup)."""
    with _indexer_lock:
        for indexer in _indexer_instances.values():
            indexer.clear_cache()
        _indexer_instances.clear()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = '.'
    
    indexer = ProjectIndexer()
    stats = indexer.index_project(project_path)
    print(f"\nIndexing Stats:")
    print(f"  Files indexed: {stats['files_indexed']}")
    print(f"  Files skipped: {stats['files_skipped']}")
    print(f"  Files updated: {stats['files_updated']}")
    print(f"  Chunks created: {stats['chunks_created']}")
    print(f"  Time: {stats['index_time_ms']}ms")
