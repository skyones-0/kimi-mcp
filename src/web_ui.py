"""
Web UI + REST API Combined Server for Kimi-PIMCP
Serves web interface and API endpoints on the same port.
"""

import os
import sys
from pathlib import Path

# Try to import FastAPI
try:
    from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available. Install with: pip install fastapi uvicorn")
    sys.exit(1)

# Import our modules
try:
    from indexer import ProjectIndexer, get_indexer, clear_all_indexers, ModelCache
    from retriever import ContextRetriever, get_retriever, clear_retriever
    from compressor import CavemanCompressor, get_compressor, clear_compressor
    from skills.router import SkillRouter, get_router
    from file_watcher import ProjectFileWatcher, FileChangeEvent, FileChangeType
    from dependency_graph import DependencyGraph
    from git_integration import GitIntegration
    from activity_monitor import ActivityMonitor, get_activity_monitor
except ImportError:
    from .indexer import ProjectIndexer, get_indexer, clear_all_indexers, ModelCache
    from .retriever import ContextRetriever, get_retriever, clear_retriever
    from .compressor import CavemanCompressor, get_compressor, clear_compressor
    from .skills.router import SkillRouter, get_router
    from .file_watcher import ProjectFileWatcher, FileChangeEvent, FileChangeType
    from .dependency_graph import DependencyGraph
    from .git_integration import GitIntegration
    from .activity_monitor import ActivityMonitor, get_activity_monitor

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import OrderedDict
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============ Action Logger for Web UI ============

class ActionLogger:
    """Logger for tracking actions in the Web UI."""
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
    
    def log(self, action_type: str, action: str, details: str, data: Dict = None):
        """Log an action."""
        with self._lock:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'type': action_type,  # 'index', 'query', 'compress', 'skill', 'error', 'info'
                'action': action,
                'details': details,
                'data': data or {}
            }
            self.entries.append(entry)
            
            # Keep only last max_entries
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries:]
            
            # Also log to standard logger
            logger.info(f"[{action_type.upper()}] {action}: {details}")
            
            return entry
    
    def get_entries(self, action_type: str = None, limit: int = 100) -> List[Dict]:
        """Get log entries, optionally filtered by type."""
        with self._lock:
            entries = self.entries
            if action_type:
                entries = [e for e in entries if e['type'] == action_type]
            return entries[-limit:]
    
    def clear(self):
        """Clear all entries."""
        with self._lock:
            self.entries.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get count of entries by type."""
        with self._lock:
            stats = {}
            for entry in self.entries:
                stats[entry['type']] = stats.get(entry['type'], 0) + 1
            return stats


# Global action logger
action_logger = ActionLogger()


# Pydantic models
class IndexRequest(BaseModel):
    project_path: str = Field(..., description="Path to project")
    force_reindex: bool = Field(False, description="Force full reindex")


class QueryRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, ge=1, le=50)
    filter_ext: Optional[List[str]] = Field(None)
    use_mmr: bool = Field(True)


class CompressRequest(BaseModel):
    text: str = Field(..., description="Text to compress")
    level: str = Field("auto", description="Compression level")


class SkillRequest(BaseModel):
    query: str = Field(..., description="Query to classify")


@dataclass
class QueryHistoryEntry:
    query: str
    timestamp: float
    results_count: int
    skill: str


# Global state
class APIState:
    def __init__(self):
        self.indexer: Optional[ProjectIndexer] = None
        self.retriever: Optional[ContextRetriever] = None
        self.compressor: Optional[CavemanCompressor] = None
        self.router: Optional[SkillRouter] = None
        self.file_watcher: Optional[ProjectFileWatcher] = None
        self.dependency_graph: Optional[DependencyGraph] = None
        self.git: Optional[GitIntegration] = None
        self.current_project: Optional[str] = None
        self.projects: Dict[str, Dict] = {}
        self.query_history: OrderedDict[str, QueryHistoryEntry] = OrderedDict()
        self.max_history = 50
        self._lock = threading.RLock()
    
    def _add_to_history(self, query: str, results_count: int, skill: str):
        with self._lock:
            entry = QueryHistoryEntry(
                query=query, timestamp=time.time(),
                results_count=results_count, skill=skill
            )
            if query in self.query_history:
                del self.query_history[query]
            self.query_history[query] = entry
            while len(self.query_history) > self.max_history:
                self.query_history.popitem(last=False)


state = APIState()


def _initialize_components():
    """Lazy initialize components."""
    if state.indexer is None:
        state.indexer = get_indexer()
    if state.retriever is None:
        state.retriever = get_retriever(use_cross_encoder=False)
    if state.compressor is None:
        state.compressor = get_compressor()
    if state.router is None:
        state.router = get_router()


def _on_file_change(event: FileChangeEvent):
    """Handle file change events."""
    logger.info(f"File {event.change_type.value}: {event.filepath}")
    if state.current_project and event.change_type in (FileChangeType.MODIFIED, FileChangeType.CREATED):
        try:
            state.indexer.index_project(state.current_project)
            state.retriever.load_index(state.current_project)
            logger.info("Incremental reindex completed")
        except Exception as e:
            logger.error(f"Error during incremental reindex: {e}")


# Create FastAPI app
app = FastAPI(
    title="Kimi-PIMCP",
    description="Project Intelligence MCP - Web UI and API",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ HTML UI ============

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kimi-PIMCP</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; color: #c9d1d9; line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header {
            background: #161b22; border-bottom: 1px solid #30363d;
            padding: 20px 0; margin-bottom: 30px;
        }
        header h1 { color: #58a6ff; font-size: 28px; }
        header p { color: #8b949e; margin-top: 5px; }
        .card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 20px; margin-bottom: 20px;
        }
        .card h2 { color: #f0f6fc; margin-bottom: 15px; font-size: 18px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #8b949e; font-size: 14px; }
        input, textarea, select {
            width: 100%; padding: 10px 12px; background: #0d1117;
            border: 1px solid #30363d; border-radius: 6px;
            color: #c9d1d9; font-size: 14px;
        }
        input:focus, textarea:focus, select:focus {
            outline: none; border-color: #58a6ff;
        }
        textarea { min-height: 120px; resize: vertical; font-family: monospace; }
        button {
            background: #238636; color: white; border: none;
            padding: 10px 20px; border-radius: 6px; cursor: pointer;
            font-size: 14px; transition: background 0.2s;
        }
        button:hover { background: #2ea043; }
        button.secondary { background: #21262d; border: 1px solid #30363d; }
        button.secondary:hover { background: #30363d; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px; margin-bottom: 20px;
        }
        .stat-card {
            background: #0d1117; border: 1px solid #30363d;
            border-radius: 6px; padding: 15px; text-align: center;
        }
        .stat-value { font-size: 28px; font-weight: bold; color: #58a6ff; }
        .stat-label { color: #8b949e; font-size: 12px; text-transform: uppercase; margin-top: 5px; }
        .result-item {
            background: #0d1117; border: 1px solid #30363d;
            border-radius: 6px; padding: 15px; margin-bottom: 10px;
        }
        .result-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
        }
        .result-filepath { color: #58a6ff; font-family: monospace; font-size: 13px; }
        .result-score {
            background: #238636; color: white; padding: 2px 8px;
            border-radius: 12px; font-size: 12px;
        }
        .result-content {
            background: #161b22; border-radius: 4px; padding: 10px;
            font-family: monospace; font-size: 12px;
            overflow-x: auto; white-space: pre-wrap; color: #c9d1d9;
        }
        .loading { display: none; text-align: center; padding: 20px; }
        .loading.active { display: block; }
        .spinner {
            border: 3px solid #30363d; border-top: 3px solid #58a6ff;
            border-radius: 50%; width: 30px; height: 30px;
            animation: spin 1s linear infinite; margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .alert {
            padding: 12px 15px; border-radius: 6px; margin-bottom: 15px;
        }
        .alert-success { background: #238636; color: white; }
        .alert-error { background: #da3633; color: white; }
        .tabs { display: flex; border-bottom: 1px solid #30363d; margin-bottom: 20px; }
        .tab {
            padding: 10px 20px; cursor: pointer;
            border-bottom: 2px solid transparent; color: #8b949e;
        }
        .tab.active { color: #f0f6fc; border-bottom-color: #58a6ff; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .flex-row { display: flex; gap: 10px; }
        .flex-row > * { flex: 1; }
        code { background: #0d1117; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 12px; }
        
        /* Log Panel Styles */
        .log-panel {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            max-height: 500px;
            overflow-y: auto;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 12px;
        }
        .log-entry {
            padding: 8px 12px;
            border-bottom: 1px solid #21262d;
            display: flex;
            gap: 10px;
        }
        .log-entry:last-child { border-bottom: none; }
        .log-timestamp { color: #8b949e; min-width: 80px; }
        .log-type {
            min-width: 60px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
        }
        .log-type-request { background: #1f6feb; color: white; }
        .log-type-response { background: #238636; color: white; }
        .log-type-action { background: #8957e5; color: white; }
        .log-type-error { background: #da3633; color: white; }
        .log-type-info { background: #6e7681; color: white; }
        .log-method { color: #58a6ff; font-weight: bold; }
        .log-endpoint { color: #d29922; }
        .log-status-success { color: #3fb950; }
        .log-status-error { color: #f85149; }
        .log-details {
            color: #c9d1d9;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .log-details:hover {
            white-space: pre-wrap;
            overflow: visible;
        }
        .log-json {
            background: #161b22;
            padding: 10px;
            border-radius: 4px;
            margin-top: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .log-controls {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            align-items: center;
        }
        .log-filter {
            display: flex;
            gap: 10px;
        }
        .log-filter label {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
        }
        .log-filter input[type="checkbox"] {
            width: auto;
        }
        .log-clear-btn {
            background: #da3633 !important;
        }
        .log-clear-btn:hover {
            background: #f85149 !important;
        }
        .log-stats {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 12px;
            color: #8b949e;
        }
        .log-stats span {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .log-stats .count {
            color: #f0f6fc;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>🔍 Kimi-PIMCP</h1>
            <p>Project Intelligence MCP - Web Interface</p>
        </div>
    </header>
    
    <div class="container">
        <!-- MCP Server Status -->
        <div class="card" style="border-left: 4px solid #238636;">
            <h2>🔧 MCP Server Status</h2>
            <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 15px;">
                <span style="display: flex; align-items: center; gap: 8px;">
                    <span id="mcp-status-dot" style="width: 12px; height: 12px; background: #238636; border-radius: 50%; display: inline-block;"></span>
                    <span id="mcp-status-text" style="color: #238636; font-weight: bold;">Active</span>
                </span>
                <span style="color: #8b949e; font-size: 13px;">
                    Activity file: <code>~/.kimi_cache/activity.json</code>
                </span>
            </div>
            <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));">
                <div class="stat-card">
                    <div class="stat-value" id="mcp-total-requests">-</div>
                    <div class="stat-label">Total Requests</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="mcp-tool-calls">-</div>
                    <div class="stat-label">Tool Calls</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="mcp-recent-5min">-</div>
                    <div class="stat-label">Last 5 Min</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="mcp-errors">-</div>
                    <div class="stat-label">Errors</div>
                </div>
            </div>
        </div>
        
        <!-- Index Statistics -->
        <div class="card">
            <h2>📊 Index Statistics (From MCP Server)</h2>
            <p style="color: #8b949e; margin-bottom: 15px; font-size: 13px;">
                These stats reflect the actual index created by the MCP Server when used with Kimi-CLI.
            </p>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="stat-projects">-</div>
                    <div class="stat-label">Projects</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-files">-</div>
                    <div class="stat-label">Files Indexed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-chunks">-</div>
                    <div class="stat-label">Chunks</div>
                </div>
            </div>
            
            <!-- Projects List -->
            <div id="projects-list" style="margin-top: 20px;">
                <h3 style="font-size: 14px; color: #8b949e; margin-bottom: 10px;">Indexed Projects:</h3>
                <div id="projects-container" style="display: flex; flex-wrap: wrap; gap: 10px;">
                    <span style="color: #6e7681; font-size: 13px;">No projects indexed yet.</span>
                </div>
            </div>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="showTab('index')">📁 Index</div>
            <div class="tab" onclick="showTab('query')">🔎 Query</div>
            <div class="tab" onclick="showTab('compress')">🗜️ Compress</div>
            <div class="tab" onclick="showTab('skills')">🎯 Skills</div>
            <div class="tab" onclick="showTab('logs')">📋 Logs</div>
        </div>
        
        <div id="tab-index" class="tab-content active">
            <div class="card">
                <h2>Index Project</h2>
                <div id="available-projects-info" style="background: #0d1117; padding: 12px; border-radius: 6px; margin-bottom: 15px; display: none;">
                    <span style="color: #8b949e; font-size: 13px;">Available projects (click to select):</span>
                    <div id="available-projects-list" style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px;"></div>
                </div>
                <div class="form-group">
                    <label>Project Path</label>
                    <input type="text" id="project-path" placeholder="/path/to/your/project" value="">
                </div>
                <div class="form-group">
                    <label><input type="checkbox" id="force-reindex"> Force reindex</label>
                </div>
                <button onclick="indexProject()">Index Project</button>
                <button class="secondary" onclick="checkStatus()">Check Status</button>
            </div>
        </div>
        
        <div id="tab-query" class="tab-content">
            <div class="card">
                <h2>Search Code</h2>
                <div class="form-group">
                    <label>Query</label>
                    <input type="text" id="query-text" placeholder="e.g., authenticate user function">
                </div>
                <div class="flex-row">
                    <div class="form-group">
                        <label>Top K</label>
                        <input type="number" id="query-topk" value="5" min="1" max="50">
                    </div>
                    <div class="form-group">
                        <label>Filter Extensions</label>
                        <input type="text" id="query-ext" placeholder=".py, .js">
                    </div>
                </div>
                <button onclick="searchCode()">Search</button>
            </div>
            <div id="query-results"></div>
        </div>
        
        <div id="tab-compress" class="tab-content">
            <div class="card">
                <h2>Compress Text</h2>
                <div class="form-group">
                    <label>Text to Compress</label>
                    <textarea id="compress-text" placeholder="Enter text..."></textarea>
                </div>
                <div class="form-group">
                    <label>Compression Level</label>
                    <select id="compress-level">
                        <option value="auto">Auto</option>
                        <option value="lite">Lite</option>
                        <option value="full">Full</option>
                        <option value="ultra">Ultra</option>
                        <option value="wenyan">Wenyan</option>
                    </select>
                </div>
                <button onclick="compressText()">Compress</button>
            </div>
            <div id="compress-results"></div>
        </div>
        
        <div id="tab-skills" class="tab-content">
            <div class="card">
                <h2>Skill Selection</h2>
                <div class="form-group">
                    <label>Query</label>
                    <input type="text" id="skill-query" placeholder="e.g., fix login bug">
                </div>
                <button onclick="selectSkill()">Detect Skill</button>
            </div>
            <div id="skill-results"></div>
        </div>
        
        <div id="tab-logs" class="tab-content">
            <div class="card">
                <h2>📋 MCP Server Activity Monitor</h2>
                <p style="color: #8b949e; margin-bottom: 15px; font-size: 13px;">
                    Real-time view of what the MCP Server is doing. Shows JSON-RPC requests, tool calls, and responses.
                </p>
                
                <!-- MCP Activity Stats -->
                <div class="log-stats" id="mcp-stats">
                    <span>🔌 MCP Requests: <span class="count" id="mcp-count-request">0</span></span>
                    <span>📤 MCP Responses: <span class="count" id="mcp-count-response">0</span></span>
                    <span>🛠️ Tool Calls: <span class="count" id="mcp-count-tool">0</span></span>
                    <span>❌ MCP Errors: <span class="count" id="mcp-count-error">0</span></span>
                    <span>📊 Total: <span class="count" id="mcp-count-total">0</span></span>
                </div>
                
                <!-- Controls -->
                <div class="log-controls">
                    <div class="log-filter">
                        <label><input type="checkbox" id="filter-mcp-request" checked onchange="applyMCPFilter()"> 🔌 MCP Request</label>
                        <label><input type="checkbox" id="filter-mcp-response" checked onchange="applyMCPFilter()"> 📤 MCP Response</label>
                        <label><input type="checkbox" id="filter-mcp-tool" checked onchange="applyMCPFilter()"> 🛠️ Tool Call</label>
                        <label><input type="checkbox" id="filter-mcp-error" checked onchange="applyMCPFilter()"> ❌ MCP Error</label>
                    </div>
                    <button class="secondary" onclick="refreshMCPActivity()">🔄 Refresh</button>
                    <button class="secondary log-clear-btn" onclick="clearMCPActivity()">🗑️ Clear</button>
                    <button class="secondary" onclick="exportMCPActivity()">💾 Export</button>
                </div>
                
                <!-- Activity Panel -->
                <div class="log-panel" id="mcp-activity-panel">
                    <div class="log-entry">
                        <span class="log-timestamp">--:--:--</span>
                        <span class="log-type log-type-info">INFO</span>
                        <span class="log-details">
                            📋 Waiting for MCP Server activity...
                            
                            To see activity here:
                            1. Open a terminal and run: kimi
                            2. Ask something about your code
                            3. Watch this panel update automatically!
                            
                            Activity file: ~/.kimi_cache/activity.json
                        </span>
                    </div>
                </div>
            </div>
            
            <!-- Web UI Logs (secondary) -->
            <div class="card" style="margin-top: 20px;">
                <h3>🌐 Web UI Internal Logs</h3>
                <div class="log-panel" id="log-panel" style="max-height: 200px;">
                    <div class="log-entry">
                        <span class="log-timestamp">--:--:--</span>
                        <span class="log-type log-type-info">INFO</span>
                        <span class="log-details">Web UI logs will appear here.</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Processing...</p>
        </div>
    </div>
    
    <script>
        const API_BASE = window.location.origin;
        
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tabName).classList.add('active');
        }
        
        function showLoading(show) {
            document.getElementById('loading').classList.toggle('active', show);
        }
        
        function showAlert(message, type = 'success') {
            const div = document.createElement('div');
            div.className = `alert alert-${type}`;
            div.textContent = message;
            const container = document.querySelector('.container');
            const tabs = document.querySelector('.tabs');
            if (container && tabs && container.contains(tabs)) {
                container.insertBefore(div, tabs);
            } else if (container) {
                container.insertBefore(div, container.firstChild);
            } else {
                document.body.insertBefore(div, document.body.firstChild);
            }
            setTimeout(() => div.remove(), 5000);
        }
        
        async function apiCall(method, endpoint, body = null) {
            const options = {
                method: method,
                headers: { 'Content-Type': 'application/json' }
            };
            if (body) options.body = JSON.stringify(body);
            
            const url = `${API_BASE}${endpoint}`;
            console.log(`API Call: ${method} ${url}`);
            
            const response = await fetch(url, options);
            if (!response.ok) {
                let errorMsg = `HTTP ${response.status}`;
                try {
                    const error = await response.json();
                    errorMsg = error.detail || error.message || errorMsg;
                } catch (e) {
                    errorMsg = await response.text() || errorMsg;
                }
                throw new Error(errorMsg);
            }
            return response.json();
        }
        
        function selectProject(path) {
            document.getElementById('project-path').value = path;
            showAlert(`Selected: ${path.split('/').pop()}`, 'success');
        }
        
        async function indexProject() {
            const path = document.getElementById('project-path').value;
            const force = document.getElementById('force-reindex').checked;
            if (!path) { showAlert('Please enter a project path', 'error'); return; }
            
            showLoading(true);
            try {
                const data = await apiCall('POST', '/index', { project_path: path, force_reindex: force });
                showAlert(`Indexed ${data.stats.files_indexed} files successfully!`);
                updateStats();
            } catch (e) {
                showAlert(e.message, 'error');
            }
            showLoading(false);
        }
        
        async function checkStatus() {
            showLoading(true);
            try {
                const data = await apiCall('GET', '/index/status');
                showAlert(data.is_indexed ? `Project indexed: ${data.current_project}` : 'No project indexed');
            } catch (e) {
                showAlert(e.message, 'error');
            }
            showLoading(false);
        }
        
        async function searchCode() {
            const query = document.getElementById('query-text').value;
            const topK = parseInt(document.getElementById('query-topk').value);
            const extFilter = document.getElementById('query-ext').value;
            if (!query) { showAlert('Please enter a query', 'error'); return; }
            
            showLoading(true);
            try {
                const body = { query: query, top_k: topK, use_mmr: true };
                if (extFilter) body.filter_ext = extFilter.split(',').map(e => e.trim());
                const data = await apiCall('POST', '/query', body);
                displayQueryResults(data);
            } catch (e) {
                showAlert(e.message, 'error');
            }
            showLoading(false);
        }
        
        function displayQueryResults(data) {
            const container = document.getElementById('query-results');
            if (!data.results || data.results.length === 0) {
                container.innerHTML = '<div class="card"><p>No results found.</p></div>';
                return;
            }
            let html = `<div class="card"><h2>Results (${data.results_count})</h2>`;
            data.results.forEach((r, i) => {
                html += `<div class="result-item">
                    <div class="result-header">
                        <span class="result-filepath">${r.filepath}:${r.start_line}-${r.end_line}</span>
                        <span class="result-score">${(r.similarity_score * 100).toFixed(1)}%</span>
                    </div>
                    <div class="result-content">${escapeHtml(r.content)}</div>
                </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
        }
        
        async function compressText() {
            const text = document.getElementById('compress-text').value;
            const level = document.getElementById('compress-level').value;
            if (!text) { showAlert('Please enter text', 'error'); return; }
            
            showLoading(true);
            try {
                const data = await apiCall('POST', '/compress', { text: text, level: level });
                displayCompressResults(data);
            } catch (e) {
                showAlert(e.message, 'error');
            }
            showLoading(false);
        }
        
        function displayCompressResults(data) {
            const container = document.getElementById('compress-results');
            const stats = data.stats;
            container.innerHTML = `<div class="card">
                <h2>Compression Results</h2>
                <div class="stats-grid">
                    <div class="stat-card"><div class="stat-value">${stats.original_tokens}</div><div class="stat-label">Original</div></div>
                    <div class="stat-card"><div class="stat-value">${stats.compressed_tokens}</div><div class="stat-label">Compressed</div></div>
                    <div class="stat-card"><div class="stat-value">${(stats.compression_ratio * 100).toFixed(1)}%</div><div class="stat-label">Reduction</div></div>
                </div>
                <h3 style="margin-top: 20px;">Compressed Text:</h3>
                <div class="result-content">${escapeHtml(data.compressed_text)}</div>
            </div>`;
        }
        
        async function selectSkill() {
            const query = document.getElementById('skill-query').value;
            if (!query) { showAlert('Please enter a query', 'error'); return; }
            
            showLoading(true);
            try {
                const data = await apiCall('POST', '/skills/select', { query: query });
                displaySkillResults(data);
            } catch (e) {
                showAlert(e.message, 'error');
            }
            showLoading(false);
        }
        
        function displaySkillResults(data) {
            const container = document.getElementById('skill-results');
            const routing = data.routing;
            let scoresHtml = '';
            for (const [skill, score] of Object.entries(routing.all_scores)) {
                const barWidth = (score * 100).toFixed(1);
                const color = skill === routing.skill ? '#238636' : '#58a6ff';
                scoresHtml += `<div style="margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span>${skill}</span><span>${barWidth}%</span>
                    </div>
                    <div style="background: #30363d; height: 8px; border-radius: 4px;">
                        <div style="background: ${color}; height: 100%; border-radius: 4px; width: ${barWidth}%;"></div>
                    </div>
                </div>`;
            }
            container.innerHTML = `<div class="card">
                <h2>Skill Selection Results</h2>
                <div style="background: #0d1117; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                    <strong>Selected:</strong> <code>${routing.skill}</code> (${(routing.confidence * 100).toFixed(1)}%)
                </div>
                <h3>All Skills:</h3>${scoresHtml}
            </div>`;
        }
        
        async function updateStats() {
            try {
                const data = await apiCall('GET', '/stats');
                console.log('Stats received:', data);
                
                // Index stats (from disk - reflects MCP Server's work)
                const projectsEl = document.getElementById('stat-projects');
                const filesEl = document.getElementById('stat-files');
                const chunksEl = document.getElementById('stat-chunks');
                
                if (projectsEl) projectsEl.textContent = (data.indexer && data.indexer.projects_indexed) || '0';
                if (filesEl) filesEl.textContent = (data.indexer && data.indexer.files_indexed) || '0';
                if (chunksEl) chunksEl.textContent = (data.indexer && data.indexer.chunks_created) || '0';
                
                // MCP Server stats
                const mcpRequestsEl = document.getElementById('mcp-total-requests');
                const mcpToolCallsEl = document.getElementById('mcp-tool-calls');
                const mcpRecentEl = document.getElementById('mcp-recent-5min');
                const mcpErrorsEl = document.getElementById('mcp-errors');
                
                if (mcpRequestsEl) mcpRequestsEl.textContent = (data.mcp_server && data.mcp_server.total_requests) || '0';
                if (mcpToolCallsEl) mcpToolCallsEl.textContent = (data.mcp_server && data.mcp_server.tool_calls) || '0';
                if (mcpRecentEl) mcpRecentEl.textContent = (data.mcp_server && data.mcp_server.recent_5min) || '0';
                if (mcpErrorsEl) mcpErrorsEl.textContent = (data.mcp_server && data.mcp_server.errors) || '0';
                
                // Update projects list
                const projectsContainer = document.getElementById('projects-container');
                if (projectsContainer && data.indexer && data.indexer.projects && data.indexer.projects.length > 0) {
                    let projectsHtml = '';
                    data.indexer.projects.forEach(p => {
                        projectsHtml += `<span style="background: #21262d; padding: 4px 10px; border-radius: 12px; font-size: 12px; color: #58a6ff; cursor: pointer;" onclick="document.getElementById('project-path').value='${p.full_path}'" title="Click to select">
                            ${p.name}: ${p.files}f, ${p.chunks}c
                        </span>`;
                    });
                    projectsContainer.innerHTML = projectsHtml;
                }
                
                // Update available projects list and pre-fill input
                const availableProjectsInfo = document.getElementById('available-projects-info');
                const availableProjectsList = document.getElementById('available-projects-list');
                const projectPathInput = document.getElementById('project-path');
                
                if (data.indexer && data.indexer.projects && data.indexer.projects.length > 0) {
                    if (availableProjectsInfo) availableProjectsInfo.style.display = 'block';
                    
                    // Show all projects as clickable tags
                    if (availableProjectsList) {
                        let projectsHtml = '';
                        data.indexer.projects.forEach(p => {
                            projectsHtml += `<span style="background: #238636; padding: 4px 10px; border-radius: 12px; font-size: 12px; color: white; cursor: pointer;" onclick="selectProject('${p.full_path}')" title="Click to select">
                                ${p.name}
                            </span>`;
                        });
                        availableProjectsList.innerHTML = projectsHtml;
                    }
                    
                    // Pre-fill input with first project if empty
                    if (projectPathInput && (!projectPathInput.value || projectPathInput.value === '')) {
                        projectPathInput.value = data.indexer.projects[0].full_path;
                    }
                }
            } catch (e) {
                console.error('Error fetching stats:', e);
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Wait for DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                updateStats();
                setInterval(updateStats, 5000);
            });
        } else {
            updateStats();
            setInterval(updateStats, 5000);
        }
        
        // ============ LOGGING SYSTEM ============
        
        // In-memory log storage
        const logs = [];
        const MAX_LOGS = 1000;
        
        function addLog(type, method, endpoint, details, status = null, data = null) {
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = {
                id: Date.now() + Math.random(),
                timestamp,
                type,       // 'request', 'response', 'action', 'error', 'info'
                method,     // HTTP method or action name
                endpoint,   // API endpoint or action description
                details,    // Short description
                status,     // 'success', 'error', or null
                data        // Full data object (for inspection)
            };
            
            logs.push(logEntry);
            
            // Keep only last MAX_LOGS
            if (logs.length > MAX_LOGS) {
                logs.shift();
            }
            
            // Update UI
            renderLogEntry(logEntry);
            updateLogStats();
            
            // Also log to console
            console.log(`[${type.toUpperCase()}] ${method} ${endpoint}: ${details}`);
            
            return logEntry;
        }
        
        function renderLogEntry(log) {
            const panel = document.getElementById('log-panel');
            if (!panel) return;
            
            // Check if filter allows this type
            const filterId = `filter-${log.type}`;
            const filterCheckbox = document.getElementById(filterId);
            if (filterCheckbox && !filterCheckbox.checked) return;
            
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.dataset.logId = log.id;
            entry.dataset.logType = log.type;
            
            const typeClass = `log-type-${log.type}`;
            const statusClass = log.status === 'success' ? 'log-status-success' : 
                               log.status === 'error' ? 'log-status-error' : '';
            
            let detailsHtml = escapeHtml(log.details);
            if (log.data) {
                detailsHtml += `<div class="log-json" style="display:none;">${escapeHtml(JSON.stringify(log.data, null, 2))}</div>`;
            }
            
            entry.innerHTML = `
                <span class="log-timestamp">${log.timestamp}</span>
                <span class="log-type ${typeClass}">${log.type.toUpperCase()}</span>
                <span class="log-method">${log.method}</span>
                <span class="log-endpoint ${statusClass}">${log.endpoint}</span>
                <span class="log-details" onclick="this.querySelector('.log-json').style.display = this.querySelector('.log-json').style.display === 'none' ? 'block' : 'none'">${detailsHtml}</span>
            `;
            
            // Insert at top
            panel.insertBefore(entry, panel.firstChild);
            
            // Remove placeholder if exists
            const placeholder = panel.querySelector('.log-entry:not([data-log-id])');
            if (placeholder) placeholder.remove();
        }
        
        function updateLogStats() {
            const counts = { request: 0, response: 0, action: 0, error: 0, info: 0 };
            logs.forEach(log => counts[log.type]++);
            
            // Update stats if elements exist (they may not in all tabs)
            const requestEl = document.getElementById('log-count-request');
            const responseEl = document.getElementById('log-count-response');
            const actionEl = document.getElementById('log-count-action');
            const errorEl = document.getElementById('log-count-error');
            const infoEl = document.getElementById('log-count-info');
            
            if (requestEl) requestEl.textContent = counts.request;
            if (responseEl) responseEl.textContent = counts.response;
            if (actionEl) actionEl.textContent = counts.action;
            if (errorEl) errorEl.textContent = counts.error;
            if (infoEl) infoEl.textContent = counts.info;
        }
        
        function applyLogFilter() {
            const panel = document.getElementById('log-panel');
            if (!panel) return;
            
            // Clear and re-render all logs
            panel.innerHTML = '';
            
            // Render in reverse order (newest first)
            [...logs].reverse().forEach(log => {
                const filterId = `filter-${log.type}`;
                const filterCheckbox = document.getElementById(filterId);
                if (filterCheckbox && filterCheckbox.checked) {
                    renderLogEntry(log);
                }
            });
            
            if (panel.children.length === 0) {
                panel.innerHTML = `
                    <div class="log-entry">
                        <span class="log-timestamp">--:--:--</span>
                        <span class="log-type log-type-info">INFO</span>
                        <span class="log-details">No logs match the current filter.</span>
                    </div>
                `;
            }
        }
        
        function clearLogs() {
            logs.length = 0;
            const panel = document.getElementById('log-panel');
            if (panel) {
                panel.innerHTML = `
                    <div class="log-entry">
                        <span class="log-timestamp">--:--:--</span>
                        <span class="log-type log-type-info">INFO</span>
                        <span class="log-details">Logs cleared. Perform an action to see new logs.</span>
                    </div>
                `;
            }
            updateLogStats();
        }
        
        function refreshLogs() {
            applyLogFilter();
            addLog('info', 'SYSTEM', 'refresh', 'Logs refreshed manually');
        }
        
        function exportLogs() {
            const dataStr = JSON.stringify(logs, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `kimi-pimcp-logs-${new Date().toISOString().split('T')[0]}.json`;
            link.click();
            URL.revokeObjectURL(url);
            addLog('action', 'SYSTEM', 'export', `Exported ${logs.length} logs to file`);
        }
        
        // Override apiCall to add logging
        const originalApiCall = apiCall;
        apiCall = async function(method, endpoint, body = null) {
            // Log request
            const logId = addLog('request', method, endpoint, body ? `Body: ${JSON.stringify(body).substring(0, 100)}...` : 'No body', null, body).id;
            
            try {
                const startTime = performance.now();
                const result = await originalApiCall(method, endpoint, body);
                const duration = (performance.now() - startTime).toFixed(0);
                
                // Log success response
                addLog('response', method, endpoint, `Success (${duration}ms)`, 'success', result);
                
                return result;
            } catch (error) {
                // Log error response
                addLog('response', method, endpoint, `Error: ${error.message}`, 'error', { error: error.message });
                throw error;
            }
        };
        
        // Log initial load
        addLog('info', 'SYSTEM', 'init', 'Web UI loaded and logging system initialized');
        
        // Sync logs with server periodically
        async function syncServerLogs() {
            try {
                const data = await apiCall('GET', '/logs?limit=50');
                if (data.entries && data.entries.length > 0) {
                    // Add server logs that we don't have yet
                    data.entries.forEach(serverLog => {
                        const exists = logs.some(l => 
                            l.timestamp === serverLog.timestamp && 
                            l.action === serverLog.action
                        );
                        if (!exists) {
                            // Convert server log format to client format
                            addLog(
                                serverLog.type,  // index, query, compress, skill, error, info
                                serverLog.action,
                                serverLog.details.split(':')[0] || serverLog.action,
                                serverLog.status || (serverLog.type === 'error' ? 'error' : 'success'),
                                serverLog.data
                            );
                        }
                    });
                }
            } catch (e) {
                console.error('Error syncing server logs:', e);
            }
        }
        
        // Sync logs every 5 seconds
        setInterval(syncServerLogs, 5000);
        
        // Initial sync
        syncServerLogs();
        
        // ============ MCP ACTIVITY MONITOR ============
        
        let mcpActivityEntries = [];
        let mcpActivityInterval = null;
        
        function formatMCPParams(params) {
            if (!params || Object.keys(params).length === 0) return 'No params';
            const keys = Object.keys(params);
            if (keys.length === 1) {
                const key = keys[0];
                const val = params[key];
                if (typeof val === 'string') {
                    return `${key}: "${val.substring(0, 50)}${val.length > 50 ? '...' : ''}"`;
                }
                return `${key}: ${JSON.stringify(val).substring(0, 50)}`;
            }
            return `${keys.length} params: ${keys.join(', ')}`;
        }
        
        function renderMCPActivityEntry(entry) {
            const panel = document.getElementById('mcp-activity-panel');
            if (!panel) return;
            
            // Check filter
            let typeClass = '';
            let typeLabel = '';
            
            if (entry.type === 'mcp_request') {
                if (!document.getElementById('filter-mcp-request').checked) return;
                typeClass = 'log-type-request';
                typeLabel = 'MCP REQ';
            } else if (entry.type === 'mcp_response') {
                if (!document.getElementById('filter-mcp-response').checked) return;
                typeClass = 'log-type-response';
                typeLabel = 'MCP RES';
            } else if (entry.type === 'tool_call') {
                if (!document.getElementById('filter-mcp-tool').checked) return;
                typeClass = 'log-type-action';
                typeLabel = 'TOOL';
            } else if (entry.type === 'mcp_error') {
                if (!document.getElementById('filter-mcp-error').checked) return;
                typeClass = 'log-type-error';
                typeLabel = 'ERROR';
            } else {
                typeClass = 'log-type-info';
                typeLabel = entry.type.toUpperCase();
            }
            
            const timestamp = new Date(entry.timestamp).toLocaleTimeString();
            const params = formatMCPParams(entry.params);
            const duration = entry.duration_ms ? ` (${entry.duration_ms}ms)` : '';
            const error = entry.error ? ` ❌ ${entry.error}` : '';
            
            const entryDiv = document.createElement('div');
            entryDiv.className = 'log-entry';
            entryDiv.innerHTML = `
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-type ${typeClass}">${typeLabel}</span>
                <span class="log-method">${entry.method}</span>
                <span class="log-details">${params}${duration}${error}</span>
            `;
            
            // Add click to expand
            entryDiv.style.cursor = 'pointer';
            entryDiv.onclick = function() {
                const existingJson = entryDiv.querySelector('.log-json');
                if (existingJson) {
                    existingJson.remove();
                } else {
                    const jsonDiv = document.createElement('div');
                    jsonDiv.className = 'log-json';
                    jsonDiv.innerHTML = `<strong>Full Entry:</strong>\n${escapeHtml(JSON.stringify(entry, null, 2))}`;
                    entryDiv.appendChild(jsonDiv);
                }
            };
            
            panel.insertBefore(entryDiv, panel.firstChild);
        }
        
        function updateMCPStats(stats) {
            const requestEl = document.getElementById('mcp-count-request');
            const responseEl = document.getElementById('mcp-count-response');
            const toolEl = document.getElementById('mcp-count-tool');
            const errorEl = document.getElementById('mcp-count-error');
            const totalEl = document.getElementById('mcp-count-total');
            
            if (requestEl) requestEl.textContent = stats.by_type?.mcp_request || 0;
            if (responseEl) responseEl.textContent = stats.by_type?.mcp_response || 0;
            if (toolEl) toolEl.textContent = stats.by_type?.tool_call || 0;
            if (errorEl) errorEl.textContent = stats.by_type?.mcp_error || 0;
            if (totalEl) totalEl.textContent = stats.total_entries || 0;
        }
        
        async function refreshMCPActivity() {
            try {
                const data = await apiCall('GET', '/mcp/activity?limit=50');
                
                if (data.entries) {
                    mcpActivityEntries = data.entries;
                    
                    // Clear and re-render
                    const panel = document.getElementById('mcp-activity-panel');
                    if (panel) {
                        panel.innerHTML = '';
                        [...data.entries].reverse().forEach(renderMCPActivityEntry);
                    }
                }
                
                if (data.stats) {
                    updateMCPStats(data.stats);
                }
            } catch (e) {
                console.error('Error fetching MCP activity:', e);
            }
        }
        
        function applyMCPFilter() {
            refreshMCPActivity();
        }
        
        async function clearMCPActivity() {
            try {
                await apiCall('POST', '/mcp/activity/clear');
                const panel = document.getElementById('mcp-activity-panel');
                if (panel) {
                    panel.innerHTML = `
                        <div class="log-entry">
                            <span class="log-timestamp">--:--:--</span>
                            <span class="log-type log-type-info">INFO</span>
                            <span class="log-details">MCP activity cleared. New activity will appear here.</span>
                        </div>
                    `;
                }
                updateMCPStats({});
            } catch (e) {
                console.error('Error clearing MCP activity:', e);
            }
        }
        
        function exportMCPActivity() {
            const dataStr = JSON.stringify(mcpActivityEntries, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `kimi-pimcp-mcp-activity-${new Date().toISOString().split('T')[0]}.json`;
            link.click();
            URL.revokeObjectURL(url);
        }
        
        // Start MCP activity polling when logs tab is shown
        const originalShowTab = showTab;
        showTab = function(tabName) {
            originalShowTab(tabName);
            
            if (tabName === 'logs') {
                // Start polling
                if (!mcpActivityInterval) {
                    refreshMCPActivity();
                    mcpActivityInterval = setInterval(refreshMCPActivity, 2000);
                }
            } else {
                // Stop polling
                if (mcpActivityInterval) {
                    clearInterval(mcpActivityInterval);
                    mcpActivityInterval = null;
                }
            }
        };
        
        // Initial load
        addLog('info', 'SYSTEM', 'init', 'Web UI loaded. Go to Logs tab to see MCP Server activity.');
    </script>
</body>
</html>
'''


# ============ API Endpoints ============

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Serve the web UI."""
    return HTML_TEMPLATE


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy", "version": "0.2.0", "current_project": state.current_project}


@app.post("/index")
async def index_project(request: IndexRequest):
    """Index a project."""
    _initialize_components()
    
    # Log the action
    action_logger.log('index', 'INDEX_PROJECT', 
                      f"Indexing {request.project_path} (force={request.force_reindex})",
                      {'path': request.project_path, 'force_reindex': request.force_reindex})
    
    try:
        stats = state.indexer.index_project(request.project_path, force_reindex=request.force_reindex)
        state.retriever.load_index(request.project_path)
        state.current_project = request.project_path
        
        # Store project info
        state.projects[request.project_path] = {
            'path': request.project_path,
            'indexed_at': time.time(),
            'stats': stats
        }
        
        # Setup file watcher
        if state.file_watcher:
            state.file_watcher.stop()
        state.file_watcher = ProjectFileWatcher(
            request.project_path, _on_file_change, debounce_seconds=2.0
        )
        state.file_watcher.start()
        
        # Build dependency graph
        state.dependency_graph = DependencyGraph(request.project_path)
        state.dependency_graph.build()
        
        # Setup git
        state.git = GitIntegration(request.project_path)
        
        # Log success
        action_logger.log('index', 'INDEX_COMPLETE', 
                          f"Indexed {stats.get('files_indexed', 0)} files, {stats.get('chunks_created', 0)} chunks",
                          stats)
        
        return {"success": True, "stats": stats}
    except Exception as e:
        action_logger.log('error', 'INDEX_FAILED', str(e), {'path': request.project_path})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/index/status")
async def index_status():
    """Get indexing status."""
    return {
        "current_project": state.current_project,
        "is_indexed": state.indexer and state.indexer.vector_store is not None,
        "stats": state.indexer.get_stats() if state.indexer else {}
    }


@app.post("/query")
async def query_context(request: QueryRequest):
    """Query the indexed project."""
    if not state.current_project:
        raise HTTPException(status_code=400, detail="No project indexed. Call /index first.")
    
    # Log the query
    action_logger.log('query', 'SEARCH', 
                      f"Query: '{request.query}' (top_k={request.top_k}, mmr={request.use_mmr})",
                      {'query': request.query, 'top_k': request.top_k, 
                       'filter_ext': request.filter_ext, 'use_mmr': request.use_mmr})
    
    try:
        start_time = time.time()
        results = state.retriever.query_with_context(
            query=request.query,
            top_k=request.top_k,
            filter_ext=request.filter_ext,
            use_mmr=request.use_mmr
        )
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log success
        action_logger.log('query', 'SEARCH_COMPLETE', 
                          f"Found {len(results)} results in {duration_ms}ms",
                          {'results_count': len(results), 'duration_ms': duration_ms})
        
        return {"query": request.query, "results_count": len(results), "results": results}
    except Exception as e:
        action_logger.log('error', 'SEARCH_FAILED', str(e), {'query': request.query})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compress")
async def compress_text(request: CompressRequest):
    """Compress text."""
    _initialize_components()
    
    # Log the action
    text_length = len(request.text)
    action_logger.log('compress', 'COMPRESS', 
                      f"Compressing {text_length} chars with level '{request.level}'",
                      {'text_length': text_length, 'level': request.level})
    
    try:
        compressed, stats = state.compressor.compress(request.text, request.level)
        
        # Log success
        action_logger.log('compress', 'COMPRESS_COMPLETE', 
                          f"Compressed {stats.original_tokens} → {stats.compressed_tokens} tokens "
                          f"({stats.compression_ratio*100:.1f}% reduction)",
                          {'original_tokens': stats.original_tokens,
                           'compressed_tokens': stats.compressed_tokens,
                           'compression_ratio': stats.compression_ratio})
        
        return {
            "original_text": request.text[:500] + '...' if len(request.text) > 500 else request.text,
            "compressed_text": compressed[:500] + '...' if len(compressed) > 500 else compressed,
            "stats": {
                "original_tokens": stats.original_tokens,
                "compressed_tokens": stats.compressed_tokens,
                "compression_ratio": stats.compression_ratio,
                "level": stats.level.value,
                "processing_time_ms": stats.processing_time_ms
            }
        }
    except Exception as e:
        action_logger.log('error', 'COMPRESS_FAILED', str(e), {'text_length': text_length})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/skills/select")
async def select_skill(request: SkillRequest):
    """Select the best skill for a query."""
    _initialize_components()
    
    # Log the action
    action_logger.log('skill', 'SKILL_SELECT', 
                      f"Selecting skill for query: '{request.query}'",
                      {'query': request.query})
    
    try:
        retrieved_files = []
        if state.current_project:
            try:
                results = state.retriever.query(request.query, top_k=3)
                retrieved_files = [
                    {"filepath": r.chunk.filepath, "chunk_type": r.chunk.chunk_type, "similarity_score": r.similarity_score}
                    for r in results
                ]
            except Exception:
                pass
        
        result = state.router.execute_skill(
            request.query, retrieved_files=retrieved_files, project_path=state.current_project or ""
        )
        
        # Log success
        routing = result.get('routing', {})
        selected_skill = routing.get('skill', 'unknown')
        confidence = routing.get('confidence', 0)
        action_logger.log('skill', 'SKILL_SELECTED', 
                          f"Selected skill: '{selected_skill}' (confidence: {confidence:.2f})",
                          {'skill': selected_skill, 'confidence': confidence})
        
        return result
    except Exception as e:
        action_logger.log('error', 'SKILL_SELECT_FAILED', str(e), {'query': request.query})
        raise HTTPException(status_code=500, detail=str(e))


def _get_disk_index_stats():
    """Get stats from index files on disk."""
    import json
    
    cache_dir = Path.home() / '.kimi_cache' / 'indexes'
    if not cache_dir.exists():
        return None
    
    # Find all index files
    index_files = list(cache_dir.glob('*_chunks.json'))
    if not index_files:
        return None
    
    projects = []
    total_files = 0
    total_chunks = 0
    first_project_path = None
    
    for chunks_file in index_files:
        try:
            with open(chunks_file, 'r') as f:
                chunks_data = json.load(f)
            
            # Count unique files and total chunks
            files = set()
            for chunk in chunks_data:
                files.add(chunk.get('filepath', ''))
            
            # Get project hash from filename
            project_hash = chunks_file.stem.replace('_chunks', '')
            
            # Try to read metadata for project path
            full_path = ''
            meta_file = chunks_file.parent / f"{project_hash}_meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                        full_path = meta.get('project_path', '')
                except Exception:
                    pass
            
            # Extract just the folder name for display
            if full_path:
                folder_name = full_path.split('/')[-1] or full_path.split('/')[-2]
                if not first_project_path:
                    first_project_path = full_path
            else:
                folder_name = project_hash[:16]
            
            projects.append({
                'hash': project_hash,
                'name': folder_name,
                'full_path': full_path or project_hash[:16],
                'files': len(files),
                'chunks': len(chunks_data)
            })
            total_files += len(files)
            total_chunks += len(chunks_data)
        except Exception as e:
            logger.warning(f"Error reading index file {chunks_file}: {e}")
    
    return {
        'projects': projects,
        'total_files': total_files,
        'total_chunks': total_chunks,
        'index_count': len(projects),
        'first_project_path': first_project_path
    }


@app.get("/stats")
async def get_stats():
    """Get all statistics from MCP Server activity and disk index."""
    
    # Get MCP Server activity stats (always available)
    try:
        monitor = get_activity_monitor()
        mcp_stats = monitor.get_stats()
    except Exception as e:
        logger.warning(f"Error getting MCP stats: {e}")
        mcp_stats = {}
    
    # Get index stats from disk (reflects MCP Server's work)
    disk_stats = _get_disk_index_stats()
    
    # Get recent queries from activity log
    recent_queries = []
    try:
        entries = monitor.get_entries(entry_type='tool_call', limit=20)
        for entry in entries:
            if entry.params and 'query' in str(entry.params):
                recent_queries.append({
                    'timestamp': entry.timestamp,
                    'method': entry.method,
                    'preview': str(entry.params)[:80]
                })
    except Exception:
        pass
    
    return {
        "indexer": {
            "files_indexed": disk_stats['total_files'] if disk_stats else 0,
            "chunks_created": disk_stats['total_chunks'] if disk_stats else 0,
            "projects_indexed": disk_stats['index_count'] if disk_stats else 0,
            "projects": disk_stats['projects'] if disk_stats else [],
            "current_project": disk_stats['first_project_path'] if disk_stats else None,
        },
        "mcp_server": {
            "status": "active",
            "total_requests": mcp_stats.get('by_type', {}).get('mcp_request', 0),
            "total_responses": mcp_stats.get('by_type', {}).get('mcp_response', 0),
            "tool_calls": mcp_stats.get('by_type', {}).get('tool_call', 0),
            "errors": mcp_stats.get('by_type', {}).get('mcp_error', 0),
            "total_activity_entries": mcp_stats.get('total_entries', 0),
            "recent_1min": mcp_stats.get('recent_1min', 0),
            "recent_5min": mcp_stats.get('recent_5min', 0),
        },
        "recent_activity": recent_queries[:10],
        "cache_dir": str(Path.home() / '.kimi_cache'),
    }


@app.post("/cache/clear")
async def clear_cache():
    """Clear all caches."""
    import shutil
    
    action_logger.log('action', 'CACHE_CLEAR', 'Clearing all caches')
    
    if state.file_watcher:
        state.file_watcher.stop()
    
    clear_all_indexers()
    clear_retriever()
    clear_compressor()
    ModelCache.clear_cache()
    
    state.indexer = None
    state.retriever = None
    state.compressor = None
    state.current_project = None
    state.projects.clear()
    state.query_history.clear()
    
    cache_dir = Path.home() / '.kimi_cache' / 'indexes'
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    
    action_logger.log('action', 'CACHE_CLEARED', 'All caches cleared successfully')
    
    return {"success": True, "message": "All caches cleared"}


# ============ Log Endpoints ============

@app.get("/logs")
async def get_logs(limit: int = 100, log_type: Optional[str] = None):
    """Get action logs."""
    entries = action_logger.get_entries(action_type=log_type, limit=limit)
    stats = action_logger.get_stats()
    
    return {
        "entries": entries,
        "stats": stats,
        "total": len(action_logger.entries)
    }


@app.post("/logs/clear")
async def clear_logs():
    """Clear all action logs."""
    action_logger.clear()
    action_logger.log('info', 'LOGS_CLEARED', 'Action logs cleared by user')
    
    return {"success": True, "message": "Logs cleared"}


@app.get("/logs/stats")
async def get_log_stats():
    """Get log statistics."""
    return {
        "stats": action_logger.get_stats(),
        "total": len(action_logger.entries),
        "max_entries": action_logger.max_entries
    }


# ============ MCP Activity Endpoints ============

@app.get("/mcp/activity")
async def get_mcp_activity(limit: int = 50, source: str = None, entry_type: str = None):
    """Get MCP Server activity from shared activity file."""
    monitor = get_activity_monitor(state.current_project if state.current_project else None)
    
    entries = monitor.get_entries(source=source, entry_type=entry_type, limit=limit)
    stats = monitor.get_stats()
    
    # Convert entries to dict for JSON serialization
    entries_dict = []
    for entry in entries:
        entries_dict.append({
            'timestamp': entry.timestamp,
            'type': entry.type,
            'source': entry.source,
            'method': entry.method,
            'params': entry.params,
            'result': entry.result,
            'error': entry.error,
            'duration_ms': entry.duration_ms
        })
    
    return {
        "entries": entries_dict,
        "stats": stats,
        "activity_file": str(monitor.activity_file)
    }


@app.get("/mcp/activity/stats")
async def get_mcp_activity_stats():
    """Get MCP activity statistics."""
    monitor = get_activity_monitor(state.current_project if state.current_project else None)
    
    return monitor.get_stats()


@app.post("/mcp/activity/clear")
async def clear_mcp_activity():
    """Clear MCP activity log."""
    monitor = get_activity_monitor(state.current_project if state.current_project else None)
    monitor.clear()
    
    return {"success": True, "message": "MCP activity log cleared"}


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kimi-PIMCP Web UI + API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Kimi-PIMCP server on http://{args.host}:{args.port}")
    print(f"📁 Web UI: http://{args.host}:{args.port}/")
    print(f"🔌 API endpoints available at same port")
    
    # Log server start
    action_logger.log('info', 'SERVER_START', 
                      f"Server started on {args.host}:{args.port}",
                      {'host': args.host, 'port': args.port})
    
    # Pass the app object directly - no need for import string
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
