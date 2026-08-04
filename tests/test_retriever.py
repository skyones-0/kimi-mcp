"""
Unit tests for the Retriever module.
"""

import os
import sys
import unittest
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from retriever import MMREtriever, ContextRetriever, get_retriever, RetrievalResult
from indexer import CodeChunk


class TestMMRRetriever(unittest.TestCase):
    """Test MMR retriever functionality."""
    
    def setUp(self):
        self.retriever = MMREtriever(lambda_param=0.5)
    
    def test_mmr_diversity(self):
        """Test that MMR provides diverse results."""
        # Create candidates with similar embeddings
        embeddings = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.9, 0.1, 0.0]),  # Similar to first
            np.array([0.0, 1.0, 0.0]),  # Different
        ]
        
        chunks = [
            CodeChunk(
                content=f"chunk {i}",
                filepath="test.py",
                start_line=i,
                end_line=i+1,
                chunk_type="function",
                language="python",
                timestamp=1.0,
                embedding=emb
            )
            for i, emb in enumerate(embeddings)
        ]
        
        candidates = [(chunks[i], 1.0 - i * 0.1) for i in range(len(chunks))]
        
        query = np.array([1.0, 0.0, 0.0])
        results = self.retriever.retrieve(query, candidates, k=2)
        
        # Should get 2 results
        self.assertEqual(len(results), 2)
    
    def test_mmr_empty_candidates(self):
        """Test MMR with empty candidates."""
        query = np.array([1.0, 0.0, 0.0])
        results = self.retriever.retrieve(query, [], k=5)
        self.assertEqual(len(results), 0)


class TestContextRetriever(unittest.TestCase):
    """Test ContextRetriever functionality."""
    
    def setUp(self):
        self.retriever = ContextRetriever(use_cross_encoder=False)
    
    def test_initialization(self):
        """Test retriever initialization."""
        self.assertIsNotNone(self.retriever)
        self.assertEqual(self.retriever.use_cross_encoder, False)
        self.assertEqual(self.retriever.rerank_threshold, 20)
    
    def test_get_stats(self):
        """Test getting statistics."""
        stats = self.retriever.get_stats()
        self.assertIn('queries_processed', stats)
        self.assertIn('avg_retrieval_time_ms', stats)
        self.assertEqual(stats['queries_processed'], 0)


class TestRetrievalResult(unittest.TestCase):
    """Test RetrievalResult dataclass."""
    
    def test_creation(self):
        """Test creating a retrieval result."""
        chunk = CodeChunk(
            content="def test(): pass",
            filepath="test.py",
            start_line=1,
            end_line=2,
            chunk_type="function",
            language="python",
            timestamp=1.0
        )
        
        result = RetrievalResult(
            chunk=chunk,
            similarity_score=0.95,
            rank=1,
            is_reranked=False
        )
        
        self.assertEqual(result.similarity_score, 0.95)
        self.assertEqual(result.rank, 1)
        self.assertFalse(result.is_reranked)


class TestGetRetriever(unittest.TestCase):
    """Test get_retriever singleton."""
    
    def test_singleton(self):
        """Test that get_retriever returns singleton."""
        retriever1 = get_retriever()
        retriever2 = get_retriever()
        self.assertIs(retriever1, retriever2)


if __name__ == '__main__':
    unittest.main()
