"""
File Watcher Module for Kimi-PIMCP
Monitors file changes and triggers incremental reindexing.
"""

import os
import time
import threading
from typing import Callable, Set, Optional, Dict, List
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileChangeType(Enum):
    """Types of file changes."""
    MODIFIED = "modified"
    CREATED = "created"
    DELETED = "deleted"


@dataclass
class FileChangeEvent:
    """Represents a file change event."""
    filepath: str
    change_type: FileChangeType
    timestamp: float


class PollingWatcher:
    """File watcher using polling (fallback when watchdog not available)."""
    
    def __init__(self, project_path: str, callback: Callable[[FileChangeEvent], None], interval: float = 2.0):
        self.project_path = project_path
        self.callback = callback
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_states: Dict[str, tuple] = {}  # filepath -> (mtime, size)
        self._supported_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.md'}
        self._exclude_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build', '.kimi_cache'}
    
    def _get_file_state(self, filepath: str) -> Optional[tuple]:
        """Get file state (mtime, size)."""
        try:
            stat = os.stat(filepath)
            return (stat.st_mtime, stat.st_size)
        except OSError:
            return None
    
    def _scan_files(self) -> Set[str]:
        """Scan project for files to watch."""
        files = set()
        for root, dirs, filenames in os.walk(self.project_path):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in self._exclude_dirs]
            
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if ext in self._supported_extensions:
                    files.add(os.path.join(root, filename))
        return files
    
    def _check_changes(self):
        """Check for file changes."""
        current_files = self._scan_files()
        
        # Check for new files
        for filepath in current_files:
            if filepath not in self._file_states:
                self._file_states[filepath] = self._get_file_state(filepath)
                self.callback(FileChangeEvent(filepath, FileChangeType.CREATED, time.time()))
            else:
                # Check for modifications
                old_state = self._file_states[filepath]
                new_state = self._get_file_state(filepath)
                if new_state and new_state != old_state:
                    self._file_states[filepath] = new_state
                    self.callback(FileChangeEvent(filepath, FileChangeType.MODIFIED, time.time()))
        
        # Check for deleted files
        for filepath in list(self._file_states.keys()):
            if filepath not in current_files:
                del self._file_states[filepath]
                self.callback(FileChangeEvent(filepath, FileChangeType.DELETED, time.time()))
    
    def _run(self):
        """Main polling loop."""
        # Initial scan
        for filepath in self._scan_files():
            self._file_states[filepath] = self._get_file_state(filepath)
        
        while self._running:
            self._check_changes()
            time.sleep(self.interval)
    
    def start(self):
        """Start watching."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Polling watcher started for {self.project_path}")
    
    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Polling watcher stopped")


class WatchdogHandler(FileSystemEventHandler):
    """Event handler for watchdog."""
    
    def __init__(self, callback: Callable[[FileChangeEvent], None], supported_extensions: Set[str]):
        self.callback = callback
        self.supported_extensions = supported_extensions
    
    def _should_handle(self, filepath: str) -> bool:
        """Check if file should be handled."""
        ext = Path(filepath).suffix.lower()
        return ext in self.supported_extensions
    
    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            if self._should_handle(event.src_path):
                self.callback(FileChangeEvent(event.src_path, FileChangeType.MODIFIED, time.time()))
    
    def on_created(self, event):
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            if self._should_handle(event.src_path):
                self.callback(FileChangeEvent(event.src_path, FileChangeType.CREATED, time.time()))
    
    def on_deleted(self, event):
        if isinstance(event, FileDeletedEvent) and not event.is_directory:
            if self._should_handle(event.src_path):
                self.callback(FileChangeEvent(event.src_path, FileChangeType.DELETED, time.time()))


class ProjectFileWatcher:
    """High-level file watcher that manages both watchdog and polling."""
    
    def __init__(
        self,
        project_path: str,
        on_change: Callable[[FileChangeEvent], None],
        use_watchdog: bool = True,
        poll_interval: float = 2.0,
        debounce_seconds: float = 1.0
    ):
        self.project_path = project_path
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._watcher = None
        self._pending_changes: Dict[str, FileChangeEvent] = {}
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        if use_watchdog and WATCHDOG_AVAILABLE:
            self._setup_watchdog()
        else:
            self._setup_polling(poll_interval)
    
    def _setup_watchdog(self):
        """Setup watchdog observer."""
        supported_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.md'}
        handler = WatchdogHandler(self._on_file_change, supported_extensions)
        
        self._observer = Observer()
        self._observer.schedule(handler, self.project_path, recursive=True)
        logger.info(f"Watchdog observer configured for {self.project_path}")
    
    def _setup_polling(self, interval: float):
        """Setup polling watcher."""
        self._watcher = PollingWatcher(self.project_path, self._on_file_change, interval)
        logger.info(f"Polling watcher configured for {self.project_path}")
    
    def _on_file_change(self, event: FileChangeEvent):
        """Handle file change with debouncing."""
        with self._lock:
            self._pending_changes[event.filepath] = event
            
            # Cancel existing timer
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # Start new timer
            self._debounce_timer = threading.Timer(self.debounce_seconds, self._process_changes)
            self._debounce_timer.start()
    
    def _process_changes(self):
        """Process pending changes."""
        with self._lock:
            changes = list(self._pending_changes.values())
            self._pending_changes.clear()
        
        # Group changes by type
        for event in changes:
            logger.info(f"File {event.change_type.value}: {event.filepath}")
            self.on_change(event)
    
    def start(self):
        """Start watching."""
        if WATCHDOG_AVAILABLE and hasattr(self, '_observer'):
            self._observer.start()
            logger.info("Watchdog observer started")
        elif self._watcher:
            self._watcher.start()
    
    def stop(self):
        """Stop watching."""
        if WATCHDOG_AVAILABLE and hasattr(self, '_observer'):
            self._observer.stop()
            self._observer.join()
            logger.info("Watchdog observer stopped")
        elif self._watcher:
            self._watcher.stop()
        
        # Cancel pending debounce
        if self._debounce_timer:
            self._debounce_timer.cancel()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python file_watcher.py <project_path>")
        sys.exit(1)
    
    project_path = sys.argv[1]
    
    def on_change(event: FileChangeEvent):
        print(f"[{event.change_type.value.upper()}] {event.filepath}")
    
    watcher = ProjectFileWatcher(project_path, on_change)
    watcher.start()
    
    print(f"Watching {project_path}... Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        watcher.stop()
