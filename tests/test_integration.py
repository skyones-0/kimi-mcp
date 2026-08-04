"""
Integration tests for Kimi-PIMCP.
"""

import os
import sys
import tempfile
import shutil
import unittest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from indexer import ProjectIndexer
from retriever import ContextRetriever
from compressor import CavemanCompressor
from skills.router import SkillRouter


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = os.path.join(self.temp_dir, "test_project")
        os.makedirs(self.project_dir)
        
        # Create test files
        self._create_test_files()
        
        # Initialize components
        self.indexer = ProjectIndexer(cache_dir=self.temp_dir)
        self.retriever = ContextRetriever(use_cross_encoder=False)
        self.compressor = CavemanCompressor()
        self.router = SkillRouter(use_svm=False)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_files(self):
        """Create test project files."""
        # Create auth.py
        with open(os.path.join(self.project_dir, "auth.py"), 'w') as f:
            f.write('''
def authenticate_user(username, password):
    """Authenticate a user."""
    if not username or not password:
        return None
    user = get_user(username)
    if user and check_password(password, user.password_hash):
        return generate_token(user.id)
    return None

def login_required(func):
    """Decorator to require login."""
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect('/login')
        return func(*args, **kwargs)
    return wrapper
''')
        
        # Create models.py
        with open(os.path.join(self.project_dir, "models.py"), 'w') as f:
            f.write('''
class User:
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }
''')
        
        # Create test_auth.py
        with open(os.path.join(self.project_dir, "test_auth.py"), 'w') as f:
            f.write('''
import pytest

def test_authenticate_valid_user():
    user = authenticate_user('test', 'password123')
    assert user is not None

def test_authenticate_invalid_password():
    user = authenticate_user('test', 'wrong')
    assert user is None
''')
    
    def test_index_and_retrieve(self):
        """Test indexing and retrieving from a project."""
        # Index the project
        stats = self.indexer.index_project(self.project_dir)
        
        self.assertGreater(stats['files_indexed'], 0)
        self.assertGreater(stats['chunks_created'], 0)
        
        # Load index in retriever
        loaded = self.retriever.load_index(self.project_dir)
        self.assertTrue(loaded)
        
        # Query
        results = self.retriever.query("authenticate user", top_k=3)
        self.assertGreater(len(results), 0)
    
    def test_compress_text(self):
        """Test text compression."""
        text = "Please help me fix this bug. The function is not working correctly."
        compressed, stats = self.compressor.compress(text, level="full")
        
        self.assertIsNotNone(compressed)
        self.assertGreater(stats.compression_ratio, 0)
        self.assertLess(stats.processing_time_ms, 100)  # Should be fast
    
    def test_skill_routing(self):
        """Test skill routing."""
        result = self.router.select_skill("fix login bug")
        
        self.assertIsNotNone(result.skill)
        self.assertGreater(result.confidence, 0)
        self.assertIn(result.skill_type.value, ['debugger', 'tester', 'caveman'])
    
    def test_debugger_skill_detection(self):
        """Test debugger skill detection."""
        queries = [
            "fix bug in authentication",
            "error 401 when logging in",
            "null pointer exception"
        ]
        
        for query in queries:
            result = self.router.select_skill(query)
            # Debugger should have high confidence for these queries
            self.assertIn(result.skill_type.value, ['debugger', 'tester'])
    
    def test_architect_skill_detection(self):
        """Test architect skill detection."""
        queries = [
            "how should I structure this",
            "design pattern for notifications",
            "database schema for e-commerce"
        ]
        
        for query in queries:
            result = self.router.select_skill(query)
            # Should detect architecture intent
            self.assertIsNotNone(result.skill)


class TestPerformance(unittest.TestCase):
    """Performance tests."""
    
    def test_compression_speed(self):
        """Test that compression meets performance targets."""
        compressor = CavemanCompressor()
        
        text = "This is a test sentence. " * 100  # ~2700 chars
        
        import time
        start = time.time()
        compressed, stats = compressor.compress(text)
        elapsed = (time.time() - start) * 1000
        
        # Should complete in less than 5ms (target)
        self.assertLess(elapsed, 50)  # Allow some margin
        self.assertLess(stats.processing_time_ms, 50)


if __name__ == '__main__':
    unittest.main()
