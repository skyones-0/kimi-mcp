"""
Dependency Graph Module for Kimi-PIMCP
Builds and analyzes import/dependency relationships between files.
"""

import os
import re
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """Represents a dependency between files."""
    source: str
    target: str
    dependency_type: str  # import, require, include, etc.
    line_number: int
    is_external: bool  # True if from node_modules/site-packages


@dataclass
class FileNode:
    """Represents a file in the dependency graph."""
    filepath: str
    language: str
    imports: List[str]  # Files this file imports
    imported_by: List[str]  # Files that import this file
    dependencies: List[Dependency]


class DependencyParser:
    """Parse dependencies from source files."""
    
    # Patterns for different languages
    PATTERNS = {
        'python': {
            'import': re.compile(r'^(?:from\s+(\S+)\s+import|import\s+(\S+))', re.MULTILINE),
            'extension': '.py'
        },
        'javascript': {
            'import': re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
            'extension': '.js'
        },
        'typescript': {
            'import': re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE),
            'extension': '.ts'
        },
    }
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.file_cache: Dict[str, str] = {}
    
    def detect_language(self, filepath: str) -> str:
        """Detect language from file extension."""
        ext = Path(filepath).suffix.lower()
        mapping = {'.py': 'python', '.js': 'javascript', '.jsx': 'javascript', 
                   '.ts': 'typescript', '.tsx': 'typescript'}
        return mapping.get(ext, 'unknown')
    
    def _read_file(self, filepath: str) -> str:
        """Read file content with caching."""
        if filepath not in self.file_cache:
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    self.file_cache[filepath] = f.read()
            except Exception as e:
                logger.warning(f"Could not read {filepath}: {e}")
                return ""
        return self.file_cache[filepath]
    
    def _resolve_import(self, source_file: str, import_path: str, language: str) -> Optional[str]:
        """Resolve an import path to an actual file path."""
        if not import_path:
            return None
        
        # Skip external packages
        if language == 'python':
            if not import_path.startswith('.') and not import_path.startswith('/'):
                # Could be external package or local module
                # Check if it exists in project
                possible_paths = [
                    os.path.join(self.project_path, import_path.replace('.', '/') + '.py'),
                    os.path.join(self.project_path, import_path.replace('.', '/') + '/__init__.py'),
                ]
            else:
                # Relative import
                source_dir = os.path.dirname(source_file)
                dots = import_path.count('.')
                if dots > 0:
                    # Go up directories
                    for _ in range(dots - 1):
                        source_dir = os.path.dirname(source_dir)
                    import_path = import_path.lstrip('.')
                
                relative_path = import_path.replace('.', '/')
                possible_paths = [
                    os.path.join(source_dir, relative_path + '.py'),
                    os.path.join(source_dir, relative_path, '__init__.py'),
                ]
        
        elif language in ('javascript', 'typescript'):
            source_dir = os.path.dirname(source_file)
            
            if import_path.startswith('.'):
                # Relative import
                possible_paths = [
                    os.path.join(source_dir, import_path),
                    os.path.join(source_dir, import_path + '.js'),
                    os.path.join(source_dir, import_path + '.jsx'),
                    os.path.join(source_dir, import_path + '.ts'),
                    os.path.join(source_dir, import_path + '.tsx'),
                    os.path.join(source_dir, import_path, 'index.js'),
                    os.path.join(source_dir, import_path, 'index.ts'),
                ]
            else:
                # External package or absolute
                return None  # Mark as external
        
        else:
            return None
        
        # Check which path exists
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        return None
    
    def parse_file(self, filepath: str) -> FileNode:
        """Parse dependencies from a file."""
        language = self.detect_language(filepath)
        content = self._read_file(filepath)
        
        imports = []
        dependencies = []
        
        if language in self.PATTERNS:
            pattern = self.PATTERNS[language]['import']
            
            for match in pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                import_path = match.group(1) or match.group(2)
                
                resolved = self._resolve_import(filepath, import_path, language)
                is_external = resolved is None
                
                if resolved:
                    imports.append(resolved)
                
                dependencies.append(Dependency(
                    source=filepath,
                    target=resolved or import_path,
                    dependency_type='import',
                    line_number=line_number,
                    is_external=is_external
                ))
        
        return FileNode(
            filepath=filepath,
            language=language,
            imports=list(set(imports)),
            imported_by=[],
            dependencies=dependencies
        )


class DependencyGraph:
    """Builds and queries the dependency graph."""
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.parser = DependencyParser(project_path)
        self.nodes: Dict[str, FileNode] = {}
        self._built = False
    
    def build(self, filepaths: Optional[List[str]] = None):
        """Build the dependency graph."""
        logger.info("Building dependency graph...")
        
        if filepaths is None:
            filepaths = self._discover_files()
        
        # Parse all files
        for filepath in filepaths:
            try:
                node = self.parser.parse_file(filepath)
                self.nodes[filepath] = node
            except Exception as e:
                logger.warning(f"Error parsing {filepath}: {e}")
        
        # Build reverse dependencies (imported_by)
        for filepath, node in self.nodes.items():
            for imported in node.imports:
                if imported in self.nodes:
                    self.nodes[imported].imported_by.append(filepath)
        
        self._built = True
        logger.info(f"Dependency graph built with {len(self.nodes)} files")
    
    def _discover_files(self) -> List[str]:
        """Discover all source files in project."""
        files = []
        extensions = {'.py', '.js', '.jsx', '.ts', '.tsx'}
        exclude_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build'}
        
        for root, dirs, filenames in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in extensions:
                    files.append(os.path.join(root, filename))
        
        return files
    
    def get_dependencies(self, filepath: str) -> List[str]:
        """Get files that a file depends on."""
        if filepath in self.nodes:
            return self.nodes[filepath].imports
        return []
    
    def get_dependents(self, filepath: str) -> List[str]:
        """Get files that depend on a file."""
        if filepath in self.nodes:
            return self.nodes[filepath].imported_by
        return []
    
    def get_related_files(self, filepath: str, depth: int = 2) -> Set[str]:
        """Get related files up to a certain depth."""
        related = set()
        to_process = [(filepath, 0)]
        processed = {filepath}
        
        while to_process:
            current, current_depth = to_process.pop(0)
            
            if current_depth >= depth:
                continue
            
            # Add dependencies
            for dep in self.get_dependencies(current):
                if dep not in processed:
                    related.add(dep)
                    processed.add(dep)
                    to_process.append((dep, current_depth + 1))
            
            # Add dependents
            for dep in self.get_dependents(current):
                if dep not in processed:
                    related.add(dep)
                    processed.add(dep)
                    to_process.append((dep, current_depth + 1))
        
        return related
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies in the graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.get_dependencies(node):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            path.pop()
            rec_stack.remove(node)
        
        for filepath in self.nodes:
            if filepath not in visited:
                dfs(filepath, [])
        
        return cycles
    
    def get_entry_points(self) -> List[str]:
        """Find files that are not imported by any other file (entry points)."""
        return [fp for fp, node in self.nodes.items() if not node.imported_by]
    
    def get_orphan_files(self) -> List[str]:
        """Find files that don't import anything and aren't imported."""
        return [fp for fp, node in self.nodes.items() 
                if not node.imports and not node.imported_by]
    
    def get_stats(self) -> Dict:
        """Get graph statistics."""
        if not self._built:
            return {}
        
        total_files = len(self.nodes)
        external_deps = sum(1 for node in self.nodes.values() 
                          for dep in node.dependencies if dep.is_external)
        internal_deps = sum(len(node.imports) for node in self.nodes.values())
        
        return {
            'total_files': total_files,
            'external_dependencies': external_deps,
            'internal_dependencies': internal_deps,
            'entry_points': len(self.get_entry_points()),
            'orphan_files': len(self.get_orphan_files()),
            'circular_dependencies': len(self.find_circular_dependencies())
        }
    
    def save(self, path: str):
        """Save graph to JSON."""
        data = {
            'project_path': self.project_path,
            'nodes': {
                fp: {
                    'filepath': node.filepath,
                    'language': node.language,
                    'imports': node.imports,
                    'imported_by': node.imported_by,
                    'dependencies': [
                        {
                            'source': d.source,
                            'target': d.target,
                            'type': d.dependency_type,
                            'line': d.line_number,
                            'external': d.is_external
                        }
                        for d in node.dependencies
                    ]
                }
                for fp, node in self.nodes.items()
            }
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Dependency graph saved to {path}")
    
    def load(self, path: str):
        """Load graph from JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.project_path = data['project_path']
        self.nodes = {}
        
        for fp, node_data in data['nodes'].items():
            self.nodes[fp] = FileNode(
                filepath=node_data['filepath'],
                language=node_data['language'],
                imports=node_data['imports'],
                imported_by=node_data['imported_by'],
                dependencies=[
                    Dependency(
                        source=d['source'],
                        target=d['target'],
                        dependency_type=d['type'],
                        line_number=d['line'],
                        is_external=d['external']
                    )
                    for d in node_data['dependencies']
                ]
            )
        
        self._built = True
        logger.info(f"Dependency graph loaded from {path}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dependency_graph.py <project_path>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    graph = DependencyGraph(project_path)
    graph.build()
    
    print("\n=== Dependency Graph Stats ===")
    stats = graph.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n=== Entry Points ===")
    for fp in graph.get_entry_points()[:10]:
        print(f"  {fp}")
    
    print("\n=== Circular Dependencies ===")
    cycles = graph.find_circular_dependencies()
    if cycles:
        for cycle in cycles[:5]:
            print(f"  {' -> '.join([Path(p).name for p in cycle])}")
    else:
        print("  No circular dependencies found!")
