"""
Code Summarizer Module for Kimi-PIMCP
Automatically summarizes code chunks using heuristics and patterns.
"""

import re
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CodeElementType(Enum):
    """Types of code elements."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"
    COMMENT = "comment"
    OTHER = "other"


@dataclass
class CodeElement:
    """Represents a code element."""
    element_type: CodeElementType
    name: str
    signature: str
    docstring: Optional[str]
    complexity: int  # Estimated complexity
    lines: int


class CodeSummarizer:
    """Summarizes code chunks using heuristics."""
    
    # Patterns for extracting information
    PATTERNS = {
        'python': {
            'function': re.compile(r'def\s+(\w+)\s*\(([^)]*)\)'),
            'class': re.compile(r'class\s+(\w+)(?:\s*\(([^)]*)\))?'),
            'docstring': re.compile(r'^[\s]*["\']{3}([\s\S]*?)["\']{3}', re.MULTILINE),
            'comment': re.compile(r'#\s*(.+)'),
        },
        'javascript': {
            'function': re.compile(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*:\s*(?:async\s*)?\()\s*\(([^)]*)\)'),
            'class': re.compile(r'class\s+(\w+)(?:\s+extends\s+(\w+))?'),
            'docstring': re.compile(r'/\*\*([\s\S]*?)\*/'),
            'comment': re.compile(r'//\s*(.+)'),
        },
        'typescript': {
            'function': re.compile(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*:\s*(?:async\s*)?\()\s*\(([^)]*)\)'),
            'class': re.compile(r'class\s+(\w+)(?:\s+extends\s+(\w+))?'),
            'docstring': re.compile(r'/\*\*([\s\S]*?)\*/'),
            'comment': re.compile(r'//\s*(.+)'),
        }
    }
    
    def __init__(self):
        self.stats = {
            'chunks_summarized': 0,
            'avg_summary_length': 0
        }
    
    def detect_language(self, content: str, extension: str = '') -> str:
        """Detect programming language."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        
        if extension in ext_map:
            return ext_map[extension]
        
        # Heuristic detection
        if 'def ' in content and ':' in content:
            return 'python'
        if 'function ' in content or 'const ' in content:
            return 'javascript'
        
        return 'unknown'
    
    def extract_docstring(self, content: str, language: str) -> Optional[str]:
        """Extract docstring/comment from code."""
        patterns = self.PATTERNS.get(language, {})
        docstring_pattern = patterns.get('docstring')
        
        if docstring_pattern:
            match = docstring_pattern.search(content)
            if match:
                docstring = match.group(1).strip()
                # Clean up
                docstring = re.sub(r'^[\s]*[*\s]*', '', docstring, flags=re.MULTILINE)
                return docstring[:500]  # Limit length
        
        return None
    
    def extract_function_info(self, content: str, language: str) -> Optional[CodeElement]:
        """Extract function information."""
        patterns = self.PATTERNS.get(language, {})
        function_pattern = patterns.get('function')
        
        if not function_pattern:
            return None
        
        match = function_pattern.search(content)
        if not match:
            return None
        
        # Extract name from groups
        name = next((g for g in match.groups() if g), 'unknown')
        params = match.groups()[-1] if match.groups()[-1] else ''
        
        # Count parameters
        param_count = len([p for p in params.split(',') if p.strip()]) if params else 0
        
        # Estimate complexity
        complexity = self._estimate_complexity(content)
        
        # Extract docstring
        docstring = self.extract_docstring(content, language)
        
        # Count lines
        lines = content.count('\n') + 1
        
        return CodeElement(
            element_type=CodeElementType.FUNCTION,
            name=name,
            signature=f"{name}({params})",
            docstring=docstring,
            complexity=complexity,
            lines=lines
        )
    
    def extract_class_info(self, content: str, language: str) -> Optional[CodeElement]:
        """Extract class information."""
        patterns = self.PATTERNS.get(language, {})
        class_pattern = patterns.get('class')
        
        if not class_pattern:
            return None
        
        match = class_pattern.search(content)
        if not match:
            return None
        
        name = match.group(1)
        parent = match.group(2) if len(match.groups()) > 1 and match.group(2) else None
        
        # Count methods
        method_count = len(re.findall(r'\s+def\s+|\s+\w+\s*\([^)]*\)\s*[{]', content))
        
        # Estimate complexity
        complexity = self._estimate_complexity(content)
        
        # Extract docstring
        docstring = self.extract_docstring(content, language)
        
        # Count lines
        lines = content.count('\n') + 1
        
        signature = f"class {name}"
        if parent:
            signature += f"({parent})"
        
        return CodeElement(
            element_type=CodeElementType.CLASS,
            name=name,
            signature=signature,
            docstring=docstring,
            complexity=complexity,
            lines=lines
        )
    
    def _estimate_complexity(self, content: str) -> int:
        """Estimate code complexity using simple heuristics."""
        complexity = 1
        
        # Count control structures
        complexity += len(re.findall(r'\bif\b|\belse\b|\belif\b', content))
        complexity += len(re.findall(r'\bfor\b|\bwhile\b', content))
        complexity += len(re.findall(r'\btry\b|\bexcept\b|\bfinally\b', content))
        complexity += len(re.findall(r'\band\b|\bor\b', content))
        complexity += len(re.findall(r'\?\s*:', content))  # Ternary operators
        
        # Count function calls (indicates coupling)
        complexity += len(re.findall(r'\w+\s*\([^)]*\)', content)) // 3
        
        return min(complexity, 50)  # Cap at 50
    
    def summarize_chunk(self, content: str, chunk_type: str = 'other', 
                       language: str = 'unknown') -> str:
        """Generate a summary of a code chunk."""
        if not content.strip():
            return "Empty chunk"
        
        if language == 'unknown':
            language = self.detect_language(content)
        
        # Extract elements based on chunk type
        element = None
        if chunk_type == 'function' or 'def ' in content:
            element = self.extract_function_info(content, language)
        elif chunk_type == 'class' or 'class ' in content:
            element = self.extract_class_info(content, language)
        
        if element:
            return self._format_summary(element)
        
        # Fallback: extract comments and first line
        return self._summarize_generic(content, language)
    
    def _format_summary(self, element: CodeElement) -> str:
        """Format element into human-readable summary."""
        parts = []
        
        # Type and name
        type_label = {
            CodeElementType.FUNCTION: "Function",
            CodeElementType.CLASS: "Class",
            CodeElementType.METHOD: "Method",
        }.get(element.element_type, "Code")
        
        parts.append(f"{type_label}: {element.signature}")
        
        # Docstring
        if element.docstring:
            # Take first sentence
            first_sentence = element.docstring.split('.')[0]
            parts.append(f"Purpose: {first_sentence}")
        
        # Stats
        stats = f"Lines: {element.lines}, Complexity: {element.complexity}/50"
        parts.append(stats)
        
        return " | ".join(parts)
    
    def _summarize_generic(self, content: str, language: str) -> str:
        """Generate generic summary for unknown code."""
        lines = content.strip().split('\n')
        
        # Get first non-empty, non-comment line
        first_line = ""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
                first_line = stripped[:80]
                break
        
        # Count lines and comments
        total_lines = len(lines)
        comment_lines = sum(1 for line in lines if line.strip().startswith(('#', '//', '*')))
        
        # Extract any docstring
        docstring = self.extract_docstring(content, language)
        
        parts = []
        if first_line:
            parts.append(f"Starts with: {first_line}")
        if docstring:
            parts.append(f"Documentation: {docstring[:100]}...")
        
        parts.append(f"Lines: {total_lines}, Comments: {comment_lines}")
        
        return " | ".join(parts)
    
    def summarize_file(self, filepath: str, content: str) -> Dict:
        """Summarize an entire file."""
        from pathlib import Path
        
        language = self.detect_language(content, Path(filepath).suffix)
        
        # Count elements
        function_count = len(re.findall(r'\bdef\s+|\bfunction\s+', content))
        class_count = len(re.findall(r'\bclass\s+', content))
        import_count = len(re.findall(r'\bimport\s+|\bfrom\s+|\brequire\s*\(', content))
        
        # Extract file-level docstring
        file_docstring = self.extract_docstring(content, language)
        
        # Calculate metrics
        lines = content.count('\n') + 1
        non_empty_lines = len([l for l in content.split('\n') if l.strip()])
        comment_lines = sum(1 for l in content.split('\n') 
                          if l.strip().startswith(('#', '//', '/*', '*')))
        
        return {
            'filepath': filepath,
            'language': language,
            'lines': lines,
            'non_empty_lines': non_empty_lines,
            'comment_lines': comment_lines,
            'functions': function_count,
            'classes': class_count,
            'imports': import_count,
            'description': file_docstring[:200] if file_docstring else None,
            'summary': f"{language} file with {function_count} functions, {class_count} classes"
        }
    
    def get_stats(self) -> Dict:
        """Get summarizer statistics."""
        return self.stats.copy()


class SimilarCodeDetector:
    """Detects similar/duplicate code blocks."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
    
    def normalize_code(self, content: str) -> str:
        """Normalize code for comparison."""
        # Remove comments
        content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Remove whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Normalize variable names
        content = re.sub(r'\b[a-zA-Z_]\w*\b', 'VAR', content)
        
        # Normalize strings
        content = re.sub(r'["\'][^"\']*["\']', '"STR"', content)
        
        # Normalize numbers
        content = re.sub(r'\b\d+\b', 'NUM', content)
        
        return content.strip().lower()
    
    def calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two code blocks."""
        norm1 = self.normalize_code(content1)
        norm2 = self.normalize_code(content2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use Jaccard similarity on tokens
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_duplicates(self, chunks: List[tuple]) -> List[tuple]:
        """
        Find duplicate/similar code blocks.
        
        Args:
            chunks: List of (filepath, content) tuples
        
        Returns:
            List of (chunk1, chunk2, similarity) tuples
        """
        duplicates = []
        
        for i in range(len(chunks)):
            for j in range(i + 1, len(chunks)):
                filepath1, content1 = chunks[i]
                filepath2, content2 = chunks[j]
                
                similarity = self.calculate_similarity(content1, content2)
                
                if similarity >= self.similarity_threshold:
                    duplicates.append((filepath1, filepath2, similarity))
        
        # Sort by similarity
        duplicates.sort(key=lambda x: x[2], reverse=True)
        
        return duplicates


if __name__ == '__main__':
    # Test summarizer
    summarizer = CodeSummarizer()
    
    test_code = '''
def calculate_fibonacci(n, memo=None):
    """
    Calculate the nth Fibonacci number using memoization.
    
    Args:
        n: The position in the Fibonacci sequence
        memo: Cache for memoization (optional)
    
    Returns:
        The nth Fibonacci number
    """
    if memo is None:
        memo = {}
    
    if n in memo:
        return memo[n]
    
    if n <= 1:
        return n
    
    memo[n] = calculate_fibonacci(n - 1, memo) + calculate_fibonacci(n - 2, memo)
    return memo[n]
'''
    
    print("=== Code Summary ===")
    summary = summarizer.summarize_chunk(test_code, 'function', 'python')
    print(summary)
    
    # Test duplicate detection
    print("\n=== Duplicate Detection ===")
    detector = SimilarCodeDetector()
    
    code1 = "def add(a, b): return a + b"
    code2 = "def sum(x, y): return x + y"
    code3 = "def multiply(a, b): return a * b"
    
    print(f"Similarity 1-2: {detector.calculate_similarity(code1, code2):.2f}")
    print(f"Similarity 1-3: {detector.calculate_similarity(code1, code3):.2f}")
