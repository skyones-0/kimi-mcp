"""
Unit tests for the Indexer module.
"""

import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from indexer import (
    CodeChunk, CodeParser, VectorStore, ProjectIndexer,
    get_indexer
)


class TestCodeChunk(unittest.TestCase):
    """Test CodeChunk dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        chunk = CodeChunk(
            content="def test(): pass",
            filepath="/test/file.py",
            start_line=1,
            end_line=2,
            chunk_type="function",
            language="python",
            timestamp=1234567890.0
        )
        
        d = chunk.to_dict()
        self.assertEqual(d['content'], "def test(): pass")
        self.assertEqual(d['filepath'], "/test/file.py")
        self.assertEqual(d['chunk_type'], "function")
        self.assertNotIn('embedding', d)


class TestCodeParser(unittest.TestCase):
    """Test CodeParser functionality."""
    
    def setUp(self):
        self.parser = CodeParser()
    
    def test_detect_language_python(self):
        """Test language detection for Python."""
        lang = self.parser.detect_language("/path/to/file.py")
        self.assertEqual(lang, "python")
    
    def test_detect_language_javascript(self):
        """Test language detection for JavaScript."""
        lang = self.parser.detect_language("/path/to/file.js")
        self.assertEqual(lang, "javascript")
    
    def test_detect_language_typescript(self):
        """Test language detection for TypeScript."""
        lang = self.parser.detect_language("/path/to/file.ts")
        self.assertEqual(lang, "typescript")
    
    def test_detect_language_unknown(self):
        """Test language detection for unknown extension."""
        lang = self.parser.detect_language("/path/to/file.xyz")
        self.assertEqual(lang, "unknown")
    
    def test_parse_python_function(self):
        """Test parsing Python function."""
        code = """def hello():
    print("Hello")
    return True
"""
        chunks = self.parser.parse_file("test.py", code)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_type, "function")
        self.assertEqual(chunks[0].language, "python")
    
    def test_parse_python_class(self):
        """Test parsing Python class."""
        code = """class MyClass:
    def __init__(self):
        self.value = 0
    
    def method(self):
        return self.value
"""
        chunks = self.parser.parse_file("test.py", code)
        self.assertGreaterEqual(len(chunks), 1)
        # First chunk should be the class
        self.assertEqual(chunks[0].chunk_type, "class")


class TestVectorStore(unittest.TestCase):
    """Test VectorStore functionality."""
    
    def setUp(self):
        self.store = VectorStore(dimension=384)
    
    def test_add_and_search(self):
        """Test adding chunks and searching."""
        import numpy as np
        
        # Create test chunks with embeddings
        chunks = [
            CodeChunk(
                content="def add(a, b): return a + b",
                filepath="math.py",
                start_line=1,
                end_line=2,
                chunk_type="function",
                language="python",
                timestamp=1.0,
                embedding=np.random.randn(384).astype('float32')
            ),
            CodeChunk(
                content="def subtract(a, b): return a - b",
                filepath="math.py",
                start_line=4,
                end_line=5,
                chunk_type="function",
                language="python",
                timestamp=1.0,
                embedding=np.random.randn(384).astype('float32')
            )
        ]
        
        self.store.add(chunks)
        self.assertEqual(len(self.store.chunks), 2)
        
        # Search
        query = np.random.randn(384).astype('float32')
        results = self.store.search(query, k=2)
        self.assertEqual(len(results), 2)


class TestProjectIndexer(unittest.TestCase):
    """Test ProjectIndexer functionality."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.indexer = ProjectIndexer(cache_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_should_index_file(self):
        """Test file filtering."""
        self.assertTrue(self.indexer._should_index_file("test.py"))
        self.assertTrue(self.indexer._should_index_file("test.js"))
        self.assertFalse(self.indexer._should_index_file("test.exe"))
        self.assertFalse(self.indexer._should_index_file("node_modules/test.js"))
    
    def test_get_file_hash(self):
        """Test file hash generation."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        hash1 = self.indexer._get_file_hash(test_file)
        hash2 = self.indexer._get_file_hash(test_file)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 32)  # MD5 hash length


class TestGetIndexer(unittest.TestCase):
    """Test get_indexer singleton."""
    
    def test_singleton(self):
        """Test that get_indexer returns singleton."""
        indexer1 = get_indexer()
        indexer2 = get_indexer()
        self.assertIs(indexer1, indexer2)


if __name__ == '__main__':
    unittest.main()
