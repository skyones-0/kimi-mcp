"""
Git Integration Module for Kimi-PIMCP
Integrates with Git to index only modified files and track changes.
"""

import os
import subprocess
from typing import List, Set, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Git change types."""
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNTRACKED = "??"


@dataclass
class GitChange:
    """Represents a Git change."""
    filepath: str
    change_type: ChangeType
    old_path: Optional[str] = None  # For renames


class GitIntegration:
    """Git integration for selective indexing."""
    
    SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.md'}
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self._git_available = self._check_git()
        self._git_dir = self._find_git_dir()
    
    def _check_git(self) -> bool:
        """Check if git is available."""
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _find_git_dir(self) -> Optional[str]:
        """Find the .git directory for the project."""
        if not self._git_available:
            return None
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True
            )
            git_dir = result.stdout.strip()
            if not os.path.isabs(git_dir):
                git_dir = os.path.join(self.project_path, git_dir)
            return git_dir
        except subprocess.CalledProcessError:
            return None
    
    def is_git_repo(self) -> bool:
        """Check if project is a Git repository."""
        return self._git_dir is not None
    
    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run a git command."""
        return subprocess.run(
            ['git'] + args,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
    
    def get_changed_files_since(self, ref: str = "HEAD") -> List[GitChange]:
        """Get files changed since a Git reference."""
        if not self.is_git_repo():
            return []
        
        result = self._run_git(['diff', '--name-status', ref])
        
        if result.returncode != 0:
            logger.warning(f"Git diff failed: {result.stderr}")
            return []
        
        changes = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            status = parts[0][0]  # First character is status
            filepath = parts[1]
            old_path = parts[2] if len(parts) > 2 else None
            
            # Map status to ChangeType
            status_map = {
                'A': ChangeType.ADDED,
                'M': ChangeType.MODIFIED,
                'D': ChangeType.DELETED,
                'R': ChangeType.RENAMED,
                'C': ChangeType.COPIED,
            }
            
            change_type = status_map.get(status, ChangeType.MODIFIED)
            
            # Filter by extension
            ext = Path(filepath).suffix.lower()
            if ext in self.SUPPORTED_EXTENSIONS:
                changes.append(GitChange(
                    filepath=os.path.join(self.project_path, filepath),
                    change_type=change_type,
                    old_path=old_path
                ))
        
        return changes
    
    def get_untracked_files(self) -> List[str]:
        """Get untracked files."""
        if not self.is_git_repo():
            return []
        
        result = self._run_git(['ls-files', '--others', '--exclude-standard'])
        
        if result.returncode != 0:
            return []
        
        files = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            filepath = os.path.join(self.project_path, line)
            ext = Path(filepath).suffix.lower()
            
            if ext in self.SUPPORTED_EXTENSIONS:
                files.append(filepath)
        
        return files
    
    def get_staged_files(self) -> List[GitChange]:
        """Get staged files."""
        if not self.is_git_repo():
            return []
        
        result = self._run_git(['diff', '--cached', '--name-status'])
        
        if result.returncode != 0:
            return []
        
        changes = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            status = parts[0][0]
            filepath = parts[1]
            
            status_map = {
                'A': ChangeType.ADDED,
                'M': ChangeType.MODIFIED,
                'D': ChangeType.DELETED,
            }
            
            change_type = status_map.get(status, ChangeType.MODIFIED)
            
            ext = Path(filepath).suffix.lower()
            if ext in self.SUPPORTED_EXTENSIONS:
                changes.append(GitChange(
                    filepath=os.path.join(self.project_path, filepath),
                    change_type=change_type
                ))
        
        return changes
    
    def get_last_commit_hash(self) -> Optional[str]:
        """Get the hash of the last commit."""
        if not self.is_git_repo():
            return None
        
        result = self._run_git(['rev-parse', 'HEAD'])
        
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    def get_files_to_index(self, since_ref: Optional[str] = None) -> Tuple[List[str], List[str]]:
        """
        Get files that need to be indexed.
        
        Returns:
            Tuple of (files_to_index, files_to_remove)
        """
        if not self.is_git_repo():
            # Not a git repo, return all files
            return self._get_all_files(), []
        
        files_to_index = set()
        files_to_remove = set()
        
        # Get changed files since reference
        if since_ref:
            changes = self.get_changed_files_since(since_ref)
            for change in changes:
                if change.change_type == ChangeType.DELETED:
                    files_to_remove.add(change.filepath)
                else:
                    files_to_index.add(change.filepath)
        
        # Get untracked files
        untracked = self.get_untracked_files()
        files_to_index.update(untracked)
        
        # Get staged files
        staged = self.get_staged_files()
        for change in staged:
            if change.change_type == ChangeType.DELETED:
                files_to_remove.add(change.filepath)
            else:
                files_to_index.add(change.filepath)
        
        return list(files_to_index), list(files_to_remove)
    
    def _get_all_files(self) -> List[str]:
        """Get all supported files in the project."""
        files = []
        exclude_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build'}
        
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, filename))
        
        return files
    
    def get_file_history(self, filepath: str, limit: int = 10) -> List[Dict]:
        """Get commit history for a file."""
        if not self.is_git_repo():
            return []
        
        rel_path = os.path.relpath(filepath, self.project_path)
        
        result = self._run_git([
            'log', f'-{limit}',
            '--format=%H|%an|%ae|%ad|%s',
            '--date=short',
            '--follow',
            '--',
            rel_path
        ])
        
        if result.returncode != 0:
            return []
        
        history = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|', 4)
            if len(parts) >= 5:
                history.append({
                    'hash': parts[0],
                    'author': parts[1],
                    'email': parts[2],
                    'date': parts[3],
                    'message': parts[4]
                })
        
        return history
    
    def get_blame_info(self, filepath: str, line_start: int = 1, line_end: int = 10) -> List[Dict]:
        """Get git blame info for lines in a file."""
        if not self.is_git_repo():
            return []
        
        rel_path = os.path.relpath(filepath, self.project_path)
        
        result = self._run_git([
            'blame',
            '-L', f'{line_start},{line_end}',
            '--porcelain',
            '--',
            rel_path
        ])
        
        if result.returncode != 0:
            return []
        
        # Parse porcelain output
        lines = result.stdout.strip().split('\n')
        blame_info = []
        
        i = 0
        while i < len(lines):
            parts = lines[i].split()
            if len(parts) >= 2:
                commit_hash = parts[0]
                original_line = parts[1]
                
                # Find author info
                author = ""
                timestamp = ""
                j = i + 1
                while j < len(lines) and not lines[j].startswith('\t'):
                    if lines[j].startswith('author '):
                        author = lines[j][7:]
                    elif lines[j].startswith('author-time '):
                        timestamp = lines[j][12:]
                    j += 1
                
                blame_info.append({
                    'commit': commit_hash,
                    'line': int(original_line),
                    'author': author,
                    'timestamp': int(timestamp) if timestamp else None
                })
                
                i = j
            else:
                i += 1
        
        return blame_info
    
    def get_stats(self) -> Dict:
        """Get Git integration statistics."""
        return {
            'is_git_repo': self.is_git_repo(),
            'git_dir': self._git_dir,
            'git_available': self._git_available,
            'last_commit': self.get_last_commit_hash()[:8] if self.get_last_commit_hash() else None
        }


class IncrementalIndexer:
    """Indexer that uses Git for incremental updates."""
    
    def __init__(self, project_path: str, indexer):
        self.project_path = project_path
        self.indexer = indexer
        self.git = GitIntegration(project_path)
        self._last_indexed_commit: Optional[str] = None
    
    def index(self, force_full: bool = False) -> Dict:
        """Index project incrementally."""
        if not self.git.is_git_repo() or force_full:
            # Full index
            return self.indexer.index_project(self.project_path, force_reindex=True)
        
        # Get current commit
        current_commit = self.git.get_last_commit_hash()
        
        # Get files to index
        files_to_index, files_to_remove = self.git.get_files_to_index(self._last_indexed_commit)
        
        logger.info(f"Incremental index: {len(files_to_index)} files to index, "
                   f"{len(files_to_remove)} files to remove")
        
        # Remove deleted files from index
        for filepath in files_to_remove:
            if self.indexer.vector_store:
                self.indexer.vector_store.remove_chunks_by_file(filepath)
        
        # Index new/modified files
        if files_to_index:
            # Process only changed files
            all_chunks = []
            for filepath in files_to_index:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Remove old chunks for this file
                    if self.indexer.vector_store:
                        self.indexer.vector_store.remove_chunks_by_file(filepath)
                    
                    chunks = self.indexer.parser.parse_file(filepath, content)
                    all_chunks.extend(chunks)
                    
                except Exception as e:
                    logger.warning(f"Error processing {filepath}: {e}")
            
            # Generate embeddings
            if all_chunks:
                model = ModelCache.get_model(self.indexer.model_name)
                batch_size = self.indexer._get_optimal_batch_size()
                
                for i in range(0, len(all_chunks), batch_size):
                    batch = all_chunks[i:i + batch_size]
                    texts = [c.content for c in batch]
                    embeddings = model.encode(texts, show_progress_bar=False)
                    
                    for chunk, embedding in zip(batch, embeddings):
                        chunk.embedding = embedding
                
                self.indexer.vector_store.add(all_chunks)
        
        # Save index
        import hashlib
        project_hash = hashlib.md5(self.project_path.encode()).hexdigest()[:16]
        index_path = os.path.join(self.indexer.cache_dir, project_hash)
        self.indexer.vector_store.save(index_path)
        
        # Update last indexed commit
        self._last_indexed_commit = current_commit
        
        return {
            'files_indexed': len(files_to_index),
            'files_removed': len(files_to_remove),
            'chunks_created': len(all_chunks) if files_to_index else 0,
            'incremental': True
        }


# Import ModelCache from indexer
try:
    from indexer import ModelCache
except ImportError:
    from .indexer import ModelCache


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python git_integration.py <project_path>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    git = GitIntegration(project_path)
    
    print("=== Git Integration Stats ===")
    print(f"  Is Git repo: {git.is_git_repo()}")
    print(f"  Last commit: {git.get_last_commit_hash()}")
    
    if git.is_git_repo():
        print("\n=== Changed Files (since HEAD~1) ===")
        changes = git.get_changed_files_since("HEAD~1")
        for change in changes[:10]:
            print(f"  [{change.change_type.value}] {Path(change.filepath).name}")
        
        print("\n=== Untracked Files ===")
        untracked = git.get_untracked_files()
        for filepath in untracked[:10]:
            print(f"  {Path(filepath).name}")
