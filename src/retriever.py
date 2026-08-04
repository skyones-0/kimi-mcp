"""
Retriever Module for Kimi-PIMCP - OPTIMIZED VERSION
Handles semantic retrieval with MMR, re-ranking, and query caching.

Improvements:
- LRU query cache with invalidation
- Fuzzy search hybrid (vector + text)
- Thread-safe operations
- Better memory management
"""

import os
import re
import time
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass
from functools import lru_cache
from collections import OrderedDict
import threading
import logging

import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

# Import our modules
try:
    from indexer import ProjectIndexer, get_indexer, CodeChunk, ModelCache, VectorStore
except ImportError:
    from .indexer import ProjectIndexer, get_indexer, CodeChunk, ModelCache, VectorStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""
    chunk: CodeChunk
    similarity_score: float
    rank: int
    is_reranked: bool = False
    fuzzy_score: float = 0.0  # Added for fuzzy search


class QueryCache:
    """LRU cache for query results with automatic invalidation."""
    
    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self._index_version = 0
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def _make_key(self, query: str, top_k: int, filters: tuple) -> str:
        """Create cache key from query parameters."""
        return hashlib.md5(f"{query}:{top_k}:{filters}:{self._index_version}".encode()).hexdigest()
    
    def get(self, query: str, top_k: int, filters: dict = None) -> Optional[List[RetrievalResult]]:
        """Get cached results if available."""
        with self._lock:
            key = self._make_key(query, top_k, tuple(sorted((filters or {}).items())))
            
            if key in self._cache:
                # Move to end (most recently used)
                entry = self._cache.pop(key)
                self._cache[key] = entry
                self.stats['hits'] += 1
                return entry['results']
            
            self.stats['misses'] += 1
            return None
    
    def put(self, query: str, top_k: int, filters: dict, results: List[RetrievalResult]):
        """Cache query results."""
        with self._lock:
            key = self._make_key(query, top_k, tuple(sorted((filters or {}).items())))
            
            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self.stats['evictions'] += 1
            
            self._cache[key] = {
                'results': results,
                'timestamp': time.time()
            }
    
    def invalidate(self):
        """Invalidate all cached results (call when index changes)."""
        with self._lock:
            self._cache.clear()
            self._index_version += 1
            logger.info("Query cache invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total if total > 0 else 0
            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'hit_rate': hit_rate,
                'size': len(self._cache)
            }


class FuzzySearcher:
    """Hybrid fuzzy search combining vector similarity with text matching."""
    
    def __init__(self):
        self.text_cache: Dict[str, str] = {}
    
    def _tokenize(self, text: str) -> Set[str]:
        """Tokenize text into words."""
        # Simple tokenization, can be improved
        return set(re.findall(r'\b\w+\b', text.lower()))
    
    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """Calculate Jaccard similarity between two sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def fuzzy_score(self, query: str, chunk: CodeChunk) -> float:
        """Calculate fuzzy text match score."""
        query_tokens = self._tokenize(query)
        content_tokens = self._tokenize(chunk.content)
        
        # Jaccard similarity on content
        content_score = self._jaccard_similarity(query_tokens, content_tokens)
        
        # Bonus for filepath matching
        path_tokens = self._tokenize(chunk.filepath)
        path_score = self._jaccard_similarity(query_tokens, path_tokens) * 0.5
        
        # Bonus for exact substring match
        substring_bonus = 0.3 if query.lower() in chunk.content.lower() else 0.0
        
        return min(1.0, content_score + path_score + substring_bonus)
    
    def hybrid_search(
        self,
        vector_results: List[Tuple[CodeChunk, float]],
        query: str,
        vector_weight: float = 0.7,
        fuzzy_weight: float = 0.3
    ) -> List[Tuple[CodeChunk, float, float]]:
        """Combine vector and fuzzy scores."""
        combined = []
        
        for chunk, vector_score in vector_results:
            fuzzy_score = self.fuzzy_score(query, chunk)
            combined_score = vector_weight * vector_score + fuzzy_weight * fuzzy_score
            combined.append((chunk, combined_score, fuzzy_score))
        
        # Sort by combined score
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined


class MMREtriever:
    """Retriever using Maximal Marginal Relevance for diverse results."""
    
    def __init__(self, lambda_param: float = 0.5):
        self.lambda_param = lambda_param
    
    def retrieve(
        self,
        query_embedding: np.ndarray,
        candidates: List[Tuple[CodeChunk, float]],
        k: int = 5
    ) -> List[Tuple[CodeChunk, float]]:
        """Retrieve diverse results using MMR."""
        if not candidates:
            return []
        
        if len(candidates) <= k:
            return candidates
        
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        
        candidate_embeddings = []
        for chunk, _ in candidates:
            if chunk.embedding is not None:
                emb = chunk.embedding / np.linalg.norm(chunk.embedding)
                candidate_embeddings.append(emb)
            else:
                candidate_embeddings.append(None)
        
        selected = []
        selected_indices = []
        remaining = list(range(len(candidates)))
        
        while len(selected) < k and remaining:
            mmr_scores = []
            
            for idx in remaining:
                relevance = candidates[idx][1]
                
                diversity = 0.0
                if selected_indices and candidate_embeddings[idx] is not None:
                    for sel_idx in selected_indices:
                        if candidate_embeddings[sel_idx] is not None:
                            sim = np.dot(candidate_embeddings[idx], candidate_embeddings[sel_idx])
                            diversity = max(diversity, sim)
                
                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * diversity
                mmr_scores.append((idx, mmr_score))
            
            best_idx, best_score = max(mmr_scores, key=lambda x: x[1])
            selected.append((candidates[best_idx][0], candidates[best_idx][1]))
            selected_indices.append(best_idx)
            remaining.remove(best_idx)
        
        return selected


class ContextRetriever:
    """Main retriever class - OPTIMIZED with caching and fuzzy search."""
    
    def __init__(
        self,
        model_name: str = 'sentence-transformers/all-MiniLM-L6-v2',
        cross_encoder_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        use_cross_encoder: bool = True,
        rerank_threshold: int = 20,
        use_fuzzy: bool = True,
        cache_dir: str = None
    ):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.cross_encoder_name = cross_encoder_name
        self.cross_encoder: Optional[CrossEncoder] = None
        self.use_cross_encoder = use_cross_encoder
        self.rerank_threshold = rerank_threshold
        self.use_fuzzy = use_fuzzy
        self.cache_dir = cache_dir
        self.mmr_retriever = MMREtriever(lambda_param=0.5)
        self.fuzzy_searcher = FuzzySearcher()
        self.query_cache = QueryCache(max_size=100)
        self.indexer: Optional[ProjectIndexer] = None
        self._lock = threading.RLock()
        
        self.stats = {
            'queries_processed': 0,
            'avg_retrieval_time_ms': 0,
            'total_retrieval_time_ms': 0,
            'cache_hits': 0
        }
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            self.model = ModelCache.get_model(self.model_name)
    
    def _load_cross_encoder(self):
        """Lazy load the cross-encoder model."""
        if self.cross_encoder is None and self.use_cross_encoder:
            logger.info(f"Loading cross-encoder: {self.cross_encoder_name}")
            self.cross_encoder = CrossEncoder(self.cross_encoder_name)
    
    def load_index(self, project_path: str) -> bool:
        """Load index for a project."""
        with self._lock:
            self._load_model()
            
            self.indexer = get_indexer(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                project_path=project_path
            )
            
            # Model already loaded above via _load_model()
            import hashlib
            project_hash = hashlib.md5(project_path.encode()).hexdigest()[:16]
            index_path = os.path.join(self.indexer.cache_dir, project_hash)
            
            if not os.path.exists(f"{index_path}_chunks.json"):
                logger.warning(f"No index found for {project_path}")
                return False
            
            self.indexer.vector_store = self.indexer.vector_store or VectorStore(
                dimension=self.model.get_sentence_embedding_dimension()
            )
            self.indexer.vector_store.load(index_path)
            
            # Invalidate cache when loading new index
            self.query_cache.invalidate()
            
            logger.info(f"Loaded index with {len(self.indexer.vector_store.chunks)} chunks")
            return True
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        filter_ext: Optional[List[str]] = None,
        filter_path: Optional[List[str]] = None,
        use_mmr: bool = True,
        lambda_mmr: float = 0.5,
        use_cache: bool = True,
        hybrid_weight: float = 0.7
    ) -> List[RetrievalResult]:
        """Query the index for relevant context - OPTIMIZED with caching."""
        import time
        start_time = time.time()
        
        with self._lock:
            if self.indexer is None or self.indexer.vector_store is None:
                raise ValueError("No index loaded. Call load_index() first.")
            
            # Check cache
            if use_cache:
                filters = {'ext': filter_ext, 'path': filter_path}
                cached = self.query_cache.get(query, top_k, filters)
                if cached is not None:
                    self.stats['cache_hits'] += 1
                    return cached
            
            self._load_model()
            
            # Encode query
            query_embedding = self.model.encode(query)
            
            # Initial retrieval
            initial_k = max(top_k * 3, self.rerank_threshold) if (use_mmr or self.use_cross_encoder) else top_k
            candidates = self.indexer.vector_store.search(query_embedding, k=initial_k)
            
            # Apply filters
            if filter_ext or filter_path:
                filtered = []
                for chunk, score in candidates:
                    include = True
                    
                    if filter_ext:
                        ext = os.path.splitext(chunk.filepath)[1].lower()
                        if ext not in filter_ext:
                            include = False
                    
                    if filter_path and include:
                        if not any(pattern in chunk.filepath for pattern in filter_path):
                            include = False
                    
                    if include:
                        filtered.append((chunk, score))
                
                candidates = filtered
            
            # Hybrid fuzzy search
            if self.use_fuzzy:
                combined = self.fuzzy_searcher.hybrid_search(
                    candidates, query, vector_weight=hybrid_weight, fuzzy_weight=1-hybrid_weight
                )
                candidates = [(chunk, score) for chunk, score, _ in combined]
            
            # Apply MMR for diversity
            if use_mmr and len(candidates) > top_k:
                self.mmr_retriever.lambda_param = lambda_mmr
                candidates = self.mmr_retriever.retrieve(query_embedding, candidates, k=top_k * 2)
            
            # Re-rank with cross-encoder
            if self.use_cross_encoder and len(candidates) >= self.rerank_threshold:
                self._load_cross_encoder()
                candidates = self._rerank(query, candidates)
            
            # Take top_k
            candidates = candidates[:top_k]
            
            # Create results
            results = []
            for rank, (chunk, score) in enumerate(candidates, 1):
                results.append(RetrievalResult(
                    chunk=chunk,
                    similarity_score=score,
                    rank=rank,
                    is_reranked=self.use_cross_encoder and len(candidates) >= self.rerank_threshold
                ))
            
            # Cache results
            if use_cache:
                filters = {'ext': filter_ext, 'path': filter_path}
                self.query_cache.put(query, top_k, filters, results)
            
            # Update stats
            retrieval_time = int((time.time() - start_time) * 1000)
            self.stats['queries_processed'] += 1
            self.stats['total_retrieval_time_ms'] += retrieval_time
            self.stats['avg_retrieval_time_ms'] = (
                self.stats['total_retrieval_time_ms'] // self.stats['queries_processed']
            )
            
            return results
    
    def _rerank(
        self,
        query: str,
        candidates: List[Tuple[CodeChunk, float]]
    ) -> List[Tuple[CodeChunk, float]]:
        """Re-rank candidates using cross-encoder."""
        if not candidates or self.cross_encoder is None:
            return candidates
        
        pairs = [(query, chunk.content[:512]) for chunk, _ in candidates]
        scores = self.cross_encoder.predict(pairs)
        
        reranked = [(candidates[i][0], float(scores[i])) for i in range(len(candidates))]
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        return reranked
    
    def query_with_context(
        self,
        query: str,
        top_k: int = 5,
        context_lines: int = 3,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Query with expanded context (surrounding lines)."""
        results = self.query(query, top_k=top_k, **kwargs)
        
        enriched_results = []
        for result in results:
            chunk = result.chunk
            
            expanded_content = chunk.content
            try:
                if os.path.exists(chunk.filepath):
                    with open(chunk.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    start = max(0, chunk.start_line - context_lines - 1)
                    end = min(len(lines), chunk.end_line + context_lines)
                    expanded_content = ''.join(lines[start:end])
            except Exception as e:
                logger.debug(f"Could not expand context for {chunk.filepath}: {e}")
            
            enriched_results.append({
                'content': expanded_content,
                'filepath': chunk.filepath,
                'start_line': chunk.start_line,
                'end_line': chunk.end_line,
                'chunk_type': chunk.chunk_type,
                'language': chunk.language,
                'similarity_score': result.similarity_score,
                'rank': result.rank
            })
        
        return enriched_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        with self._lock:
            stats = self.stats.copy()
            stats['cache'] = self.query_cache.get_stats()
            return stats
    
    def invalidate_cache(self):
        """Manually invalidate query cache."""
        self.query_cache.invalidate()


# Import hashlib for cache key generation
import hashlib

# Singleton instance
_retriever_instance: Optional[ContextRetriever] = None
_retriever_lock = threading.Lock()


def get_retriever(**kwargs) -> ContextRetriever:
    """Get or create singleton retriever instance."""
    global _retriever_instance
    with _retriever_lock:
        if _retriever_instance is None:
            _retriever_instance = ContextRetriever(**kwargs)
        return _retriever_instance


def clear_retriever():
    """Clear singleton retriever instance."""
    global _retriever_instance
    with _retriever_lock:
        _retriever_instance = None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python retriever.py <project_path> <query>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    query = sys.argv[2]
    
    retriever = ContextRetriever()
    
    if retriever.load_index(project_path):
        results = retriever.query_with_context(query, top_k=5)
        
        print(f"\nQuery: {query}")
        print(f"Results: {len(results)}\n")
        
        for r in results:
            print(f"[{r['rank']}] {r['filepath']}:{r['start_line']}-{r['end_line']} "
                  f"(score: {r['similarity_score']:.3f})")
            print(f"Type: {r['chunk_type']} | Language: {r['language']}")
            print("-" * 60)
            print(r['content'][:500] + "..." if len(r['content']) > 500 else r['content'])
            print("=" * 60)
    else:
        print(f"No index found. Please index the project first.")
