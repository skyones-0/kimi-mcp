"""
Caveman Compressor Module for Kimi-PIMCP - OPTIMIZED VERSION
Heuristic-based text compression for token optimization with tiktoken.

Improvements:
- Precise token counting with tiktoken
- LRU cache for compression results
- Thread-safe operations
- Better code detection
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from collections import OrderedDict
import threading
import logging

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CompressionLevel(Enum):
    """Compression levels available."""
    LITE = "lite"
    FULL = "full"
    ULTRA = "ultra"
    WENYAN = "wenyan"


@dataclass
class CompressionStats:
    """Statistics for compression operation."""
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    level: CompressionLevel
    processing_time_ms: int


class TokenCounter:
    """Accurate token counting using tiktoken."""
    
    _encoder = None
    _lock = threading.Lock()
    
    @classmethod
    def get_encoder(cls):
        """Get or create tiktoken encoder."""
        if not TIKTOKEN_AVAILABLE:
            return None
        
        with cls._lock:
            if cls._encoder is None:
                try:
                    cls._encoder = tiktoken.get_encoding("cl100k_base")
                except Exception as e:
                    logger.warning(f"Could not load tiktoken encoder: {e}")
                    return None
            return cls._encoder
    
    @classmethod
    def count_tokens(cls, text: str) -> int:
        """Count tokens in text accurately."""
        encoder = cls.get_encoder()
        if encoder is None:
            # Fallback to character-based estimation
            return len(text) // 4
        
        try:
            return len(encoder.encode(text))
        except Exception:
            return len(text) // 4


class CompressionCache:
    """LRU cache for compression results."""
    
    def __init__(self, max_size: int = 500):
        self._cache: OrderedDict[str, Tuple[str, CompressionStats]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0
        }
    
    def _make_key(self, text: str, level: str) -> str:
        """Create cache key."""
        import hashlib
        return hashlib.md5(f"{text}:{level}".encode()).hexdigest()
    
    def get(self, text: str, level: str) -> Optional[Tuple[str, CompressionStats]]:
        """Get cached compression result."""
        with self._lock:
            key = self._make_key(text, level)
            if key in self._cache:
                result = self._cache.pop(key)
                self._cache[key] = result
                self.stats['hits'] += 1
                return result
            self.stats['misses'] += 1
            return None
    
    def put(self, text: str, level: str, result: Tuple[str, CompressionStats]):
        """Cache compression result."""
        with self._lock:
            key = self._make_key(text, level)
            
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = result
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            total = self.stats['hits'] + self.stats['misses']
            return {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': self.stats['hits'] / total if total > 0 else 0,
                'size': len(self._cache)
            }


class CavemanCompressor:
    """
    Heuristic text compressor optimized for code and technical content.
    OPTIMIZED with tiktoken and caching.
    """
    
    FILLER_WORDS = {
        'lite': {'the', 'a', 'an'},
        'full': {
            'the', 'a', 'an',
            'very', 'really', 'quite', 'rather', 'pretty',
            'basically', 'essentially', 'fundamentally',
            'obviously', 'clearly', 'certainly', 'definitely',
            'please', 'kindly', 'would you mind',
            'thank you', 'thanks', 'appreciate it',
        },
        'ultra': {
            'the', 'a', 'an',
            'very', 'really', 'quite', 'rather', 'pretty',
            'basically', 'essentially', 'fundamentally',
            'obviously', 'clearly', 'certainly', 'definitely',
            'please', 'kindly', 'would you mind',
            'thank you', 'thanks', 'appreciate it',
            'just', 'simply', 'only', 'merely',
            'actually', 'in fact', 'as a matter of fact',
            'you know', 'i mean', 'like',
            'so', 'then', 'thus', 'therefore',
        }
    }
    
    ABBREVIATIONS = {
        'for example': 'eg',
        'for instance': 'eg',
        'that is': 'ie',
        'in other words': 'ie',
        'et cetera': 'etc',
        'and so on': 'etc',
        'with respect to': 'wrt',
        'as soon as possible': 'asap',
        'in my opinion': 'imo',
        'by the way': 'btw',
        'as far as i know': 'afaik',
        'for your information': 'fyi',
        'if i remember correctly': 'iirc',
        'in case you missed it': 'icymi',
        'to be honest': 'tbh',
        'to be announced': 'tba',
        'to be determined': 'tbd',
        'frequently asked questions': 'faq',
        'at the moment': 'atm',
        'correct me if i am wrong': 'cmiiw',
        'do it yourself': 'diy',
        'estimated time of arrival': 'eta',
        'in real life': 'irl',
        'on the other hand': 'otoh',
        'original poster': 'op',
        'point of view': 'pov',
        'too long did not read': 'tl;dr',
        'what do you think': 'wdyt',
        'your mileage may vary': 'ymmv',
    }
    
    CODE_PATTERNS = [
        r'```[\s\S]*?```',
        r'`[^`]+`',
        r'[\w\.]+\([^)]*\)',
        r'(def|class|function|const|let|var|import|from|return)\s+\w+',
        r'https?://[^\s]+',
        r'[\w\.]+@[\w\.]+',
    ]
    
    def __init__(self):
        self.code_regex = re.compile('|'.join(f'({p})' for p in self.CODE_PATTERNS), re.MULTILINE)
        self.cache = CompressionCache(max_size=500)
        self.stats = {
            'total_compressions': 0,
            'total_tokens_saved': 0,
            'avg_compression_ratio': 0.0
        }
        self._lock = threading.RLock()
    
    def _estimate_tokens(self, text: str) -> int:
        """Accurate token estimation using tiktoken."""
        return TokenCounter.count_tokens(text)
    
    def _detect_code_density(self, text: str) -> float:
        """Detect what percentage of text is code."""
        code_matches = self.code_regex.findall(text)
        code_length = sum(len(m[0]) if isinstance(m, tuple) else len(m) for m in code_matches)
        return code_length / len(text) if text else 0.0
    
    def _auto_select_level(self, text: str) -> CompressionLevel:
        """Automatically select compression level."""
        code_density = self._detect_code_density(text)
        length = len(text)
        
        if code_density > 0.7:
            return CompressionLevel.WENYAN
        elif length > 5000:
            return CompressionLevel.ULTRA
        elif length > 2000:
            return CompressionLevel.FULL
        else:
            return CompressionLevel.LITE
    
    def _protect_code_blocks(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Replace code blocks with placeholders."""
        placeholders = {}
        counter = 0
        
        def replace_code(match):
            nonlocal counter
            placeholder = f"<<CODE_{counter}>>"
            code = match.group(0)
            placeholders[placeholder] = code
            counter += 1
            return placeholder
        
        protected = self.code_regex.sub(replace_code, text)
        return protected, placeholders
    
    def _restore_code_blocks(self, text: str, placeholders: Dict[str, str]) -> str:
        """Restore code blocks from placeholders."""
        for placeholder, code in placeholders.items():
            text = text.replace(placeholder, code)
        return text
    
    def _remove_filler_words(self, text: str, level: CompressionLevel) -> str:
        """Remove filler words."""
        words_to_remove = self.FILLER_WORDS.get(level.value, self.FILLER_WORDS['lite'])
        pattern = r'\b(' + '|'.join(re.escape(w) for w in words_to_remove) + r')\b'
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _apply_abbreviations(self, text: str, level: CompressionLevel) -> str:
        """Apply abbreviations."""
        if level == CompressionLevel.LITE:
            return text
        
        for phrase, abbrev in self.ABBREVIATIONS.items():
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            text = pattern.sub(abbrev, text)
        
        return text
    
    def _compress_sentences(self, text: str, level: CompressionLevel) -> str:
        """Compress sentence structures."""
        if level == CompressionLevel.LITE:
            return text
        
        replacements = [
            (r'\bin order to\b', 'to'),
            (r'\bdue to the fact that\b', 'because'),
            (r'\bin spite of the fact that\b', 'although'),
            (r'\bwith regard to\b', 'about'),
            (r'\bin the event that\b', 'if'),
            (r'\bat this point in time\b', 'now'),
            (r'\bin the near future\b', 'soon'),
            (r'\bon a daily basis\b', 'daily'),
        ]
        
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        if level in (CompressionLevel.ULTRA, CompressionLevel.WENYAN):
            text = re.sub(r'\bthere is\s+|\bthere are\s+', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\bit is\s+|\tthey are\s+', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\bwhich is\s+|\bthat is\s+', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\bwho is\s+|\bwho are\s+', '', text, flags=re.IGNORECASE)
        
        return text
    
    def _wenyan_compress(self, text: str) -> str:
        """Maximum compression - keep only essential information."""
        lines = text.split('\n')
        compressed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if self.code_regex.search(line):
                compressed_lines.append(line)
                continue
            
            if line.startswith('#') or line.startswith('//') or line.startswith('*'):
                clean = re.sub(r'^[#/*\s]+', '', line)
                clean = self._remove_filler_words(clean, CompressionLevel.ULTRA)
                clean = self._apply_abbreviations(clean, CompressionLevel.ULTRA)
                if clean:
                    compressed_lines.append(f'# {clean}')
            else:
                compressed_lines.append(line)
        
        return '\n'.join(compressed_lines)
    
    def compress(
        self,
        text: str,
        level: Optional[str] = "auto"
    ) -> Tuple[str, CompressionStats]:
        """Compress text using caveman heuristics - OPTIMIZED with caching."""
        import time
        
        with self._lock:
            start_time = time.time()
            
            # Determine compression level
            if level == "auto" or level is None:
                compression_level = self._auto_select_level(text)
            else:
                try:
                    compression_level = CompressionLevel(level.lower())
                except ValueError:
                    compression_level = CompressionLevel.FULL
            
            # Check cache
            cached = self.cache.get(text, compression_level.value)
            if cached is not None:
                return cached
            
            original_tokens = self._estimate_tokens(text)
            
            # Special handling for wenyan level
            if compression_level == CompressionLevel.WENYAN:
                compressed = self._wenyan_compress(text)
                compressed_tokens = self._estimate_tokens(compressed)
                ratio = 1 - (compressed_tokens / original_tokens) if original_tokens > 0 else 0
                
                stats = CompressionStats(
                    original_tokens=original_tokens,
                    compressed_tokens=compressed_tokens,
                    compression_ratio=ratio,
                    level=compression_level,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
                result = (compressed, stats)
                self.cache.put(text, compression_level.value, result)
                self._update_stats(stats)
                return result
            
            # Protect code blocks
            protected_text, placeholders = self._protect_code_blocks(text)
            
            # Apply compression steps
            compressed = protected_text
            compressed = self._remove_filler_words(compressed, compression_level)
            compressed = self._apply_abbreviations(compressed, compression_level)
            compressed = self._compress_sentences(compressed, compression_level)
            
            # Restore code blocks
            compressed = self._restore_code_blocks(compressed, placeholders)
            
            # Clean up whitespace
            compressed = re.sub(r'\n{3,}', '\n\n', compressed)
            compressed = compressed.strip()
            
            # Calculate stats
            compressed_tokens = self._estimate_tokens(compressed)
            ratio = 1 - (compressed_tokens / original_tokens) if original_tokens > 0 else 0
            
            stats = CompressionStats(
                original_tokens=original_tokens,
                compressed_tokens=compressed_tokens,
                compression_ratio=ratio,
                level=compression_level,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
            
            result = (compressed, stats)
            self.cache.put(text, compression_level.value, result)
            self._update_stats(stats)
            
            return result
    
    def _update_stats(self, stats: CompressionStats):
        """Update global compression statistics."""
        self.stats['total_compressions'] += 1
        self.stats['total_tokens_saved'] += (stats.original_tokens - stats.compressed_tokens)
        
        n = self.stats['total_compressions']
        current_avg = self.stats['avg_compression_ratio']
        self.stats['avg_compression_ratio'] = ((current_avg * (n - 1)) + stats.compression_ratio) / n
    
    def get_stats(self) -> Dict:
        """Get compression statistics."""
        with self._lock:
            stats = self.stats.copy()
            stats['cache'] = self.cache.get_stats()
            return stats
    
    def batch_compress(
        self,
        texts: List[str],
        level: Optional[str] = "auto"
    ) -> List[Tuple[str, CompressionStats]]:
        """Compress multiple texts."""
        return [self.compress(text, level) for text in texts]


# Singleton instance
_compressor_instance: Optional[CavemanCompressor] = None
_compressor_lock = threading.Lock()


def get_compressor() -> CavemanCompressor:
    """Get or create singleton compressor instance."""
    global _compressor_instance
    with _compressor_lock:
        if _compressor_instance is None:
            _compressor_instance = CavemanCompressor()
        return _compressor_instance


def clear_compressor():
    """Clear singleton compressor instance."""
    global _compressor_instance
    with _compressor_lock:
        _compressor_instance = None


if __name__ == '__main__':
    import sys
    
    test_text = """
    Hello there! I would like to please ask you to help me with this code.
    Basically, I have a function that is not working properly. 
    
    ```python
    def calculate_sum(a, b):
        return a + b
    ```
    
    For example, when I call it with calculate_sum(1, 2), it should return 3.
    In my opinion, this is a very simple function that should work correctly.
    Thank you very much for your help!
    """
    
    compressor = CavemanCompressor()
    
    print("Original text:")
    print(test_text)
    print(f"\nOriginal tokens: ~{compressor._estimate_tokens(test_text)}")
    print("=" * 60)
    
    for level in ['lite', 'full', 'ultra', 'wenyan']:
        compressed, stats = compressor.compress(test_text, level)
        print(f"\n[{level.upper()}] Compression:")
        print(f"Tokens: {stats.original_tokens} → {stats.compressed_tokens} "
              f"({stats.compression_ratio*100:.1f}% reduction)")
        print(f"Time: {stats.processing_time_ms}ms")
        print("-" * 40)
        print(compressed[:500] + "..." if len(compressed) > 500 else compressed)
        print("=" * 60)
