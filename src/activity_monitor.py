"""
Activity Monitor for Kimi-PIMCP
Tracks MCP Server activity and makes it available to the Web UI via shared file.
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ActivityEntry:
    """Single activity entry."""
    timestamp: str
    type: str  # 'mcp_request', 'mcp_response', 'mcp_error', 'tool_call', 'index', 'query'
    source: str  # 'mcp_server' or 'web_ui'
    method: str  # JSON-RPC method or HTTP endpoint
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class ActivityMonitor:
    """
    Monitors and records activity from both MCP Server and Web UI.
    Uses a shared JSON file for inter-process communication.
    """
    
    def __init__(self, project_path: Optional[str] = None, max_entries: int = 500):
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: List[ActivityEntry] = []
        
        # Determine activity file location
        if project_path:
            self.activity_file = Path(project_path) / '.kimi_pimcp' / 'activity.json'
        else:
            self.activity_file = Path.home() / '.kimi_cache' / 'activity.json'
        
        self.activity_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing entries
        self._load_entries()
    
    def _load_entries(self):
        """Load existing entries from file."""
        if self.activity_file.exists():
            try:
                with open(self.activity_file, 'r') as f:
                    data = json.load(f)
                    self._entries = [ActivityEntry(**entry) for entry in data.get('entries', [])]
            except Exception as e:
                logger.warning(f"Error loading activity file: {e}")
                self._entries = []
    
    def _save_entries(self):
        """Save entries to file."""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'entries': [asdict(entry) for entry in self._entries[-self.max_entries:]]
            }
            with open(self.activity_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Error saving activity file: {e}")
    
    def record(self, entry_type: str, source: str, method: str, 
               params: Dict[str, Any] = None, result: Dict[str, Any] = None,
               error: str = None, duration_ms: int = None):
        """Record an activity entry."""
        with self._lock:
            entry = ActivityEntry(
                timestamp=datetime.now().isoformat(),
                type=entry_type,
                source=source,
                method=method,
                params=params or {},
                result=result,
                error=error,
                duration_ms=duration_ms
            )
            
            self._entries.append(entry)
            
            # Keep only last max_entries
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]
            
            # Save to file
            self._save_entries()
            
            return entry
    
    def get_entries(self, source: str = None, entry_type: str = None, 
                    limit: int = 100) -> List[ActivityEntry]:
        """Get activity entries with optional filtering."""
        with self._lock:
            entries = self._entries
            
            if source:
                entries = [e for e in entries if e.source == source]
            
            if entry_type:
                entries = [e for e in entries if e.type == entry_type]
            
            return entries[-limit:]
    
    def get_recent(self, seconds: int = 60) -> List[ActivityEntry]:
        """Get entries from the last N seconds."""
        with self._lock:
            cutoff = time.time() - seconds
            return [e for e in self._entries 
                    if datetime.fromisoformat(e.timestamp).timestamp() > cutoff]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get activity statistics."""
        with self._lock:
            stats = {
                'total_entries': len(self._entries),
                'by_source': {},
                'by_type': {},
                'recent_1min': len(self.get_recent(60)),
                'recent_5min': len(self.get_recent(300)),
                'recent_1hour': len(self.get_recent(3600)),
            }
            
            for entry in self._entries:
                stats['by_source'][entry.source] = stats['by_source'].get(entry.source, 0) + 1
                stats['by_type'][entry.type] = stats['by_type'].get(entry.type, 0) + 1
            
            return stats
    
    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._entries.clear()
            self._save_entries()


# Global instance
_monitor_instance: Optional[ActivityMonitor] = None
_monitor_lock = threading.Lock()


def get_activity_monitor(project_path: str = None) -> ActivityMonitor:
    """Get or create the global activity monitor."""
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = ActivityMonitor(project_path)
        return _monitor_instance


def record_mcp_request(method: str, params: Dict[str, Any]):
    """Record an MCP request."""
    monitor = get_activity_monitor()
    return monitor.record(
        entry_type='mcp_request',
        source='mcp_server',
        method=method,
        params=params
    )


def record_mcp_response(method: str, result: Dict[str, Any], duration_ms: int):
    """Record an MCP response."""
    monitor = get_activity_monitor()
    return monitor.record(
        entry_type='mcp_response',
        source='mcp_server',
        method=method,
        result=result,
        duration_ms=duration_ms
    )


def record_mcp_error(method: str, error: str, params: Dict[str, Any] = None):
    """Record an MCP error."""
    monitor = get_activity_monitor()
    return monitor.record(
        entry_type='mcp_error',
        source='mcp_server',
        method=method,
        params=params or {},
        error=error
    )


def record_tool_call(tool_name: str, arguments: Dict[str, Any], result: Dict[str, Any] = None):
    """Record a tool call."""
    monitor = get_activity_monitor()
    return monitor.record(
        entry_type='tool_call',
        source='mcp_server',
        method=tool_name,
        params=arguments,
        result=result
    )


if __name__ == '__main__':
    # Test
    monitor = ActivityMonitor()
    
    monitor.record('test', 'mcp_server', 'initialize', {'test': True})
    monitor.record('test', 'mcp_server', 'tools/list', {})
    
    print("Entries:")
    for entry in monitor.get_entries():
        print(f"  {entry.timestamp} - {entry.method}")
    
    print("\nStats:", monitor.get_stats())
