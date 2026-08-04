# Kimi Project Intelligence MCP (Kimi-PIMCP) v0.2.0 🚀

A Model Context Protocol (MCP) server for Kimi-CLI that provides semantic indexing, intelligent context retrieval, and dynamic skill selection for enhanced code assistance.

## ✨ Features

### Core Features
- **Semantic Indexing** - Index projects using ML embeddings (sentence-transformers)
- **Intelligent Retrieval** - Find relevant code with cosine similarity + MMR for diversity
- **Skill Routing** - Automatically detect user intent and select optimal skills
- **Caveman Compression** - Heuristic-based text compression for token optimization
- **MCP Protocol** - Full compatibility with Kimi-CLI via stdio JSON-RPC

### New in v0.2.0
- **Incremental Indexing** - Only reindex changed files (10x faster reindexing)
- **Query Caching** - LRU cache for frequently used queries
- **File Watcher** - Auto-reindex when files change
- **Dependency Graph** - Analyze import relationships between files
- **Git Integration** - Index only modified files vs HEAD
- **Code Summarization** - Auto-summarize code chunks
- **Similar Code Detection** - Find duplicate/similar code blocks
- **REST API** - HTTP API for external integrations
- **Web UI** - Beautiful web interface for managing indexes

## 📁 Architecture

```
kimi-pimcp/
├── src/
│   ├── indexer.py           # Semantic indexing with embeddings (OPTIMIZED)
│   ├── retriever.py         # Context retrieval with MMR + caching
│   ├── compressor.py        # Caveman text compression with tiktoken
│   ├── server.py            # MCP stdio server (multi-project support)
│   ├── file_watcher.py      # File change monitoring
│   ├── dependency_graph.py  # Import/dependency analysis
│   ├── git_integration.py   # Git integration for incremental updates
│   ├── code_summarizer.py   # Code summarization and duplicate detection
│   ├── rest_api.py          # HTTP REST API
│   ├── web_ui.py            # Web interface
│   └── skills/
│       ├── base.py          # Base skill classes
│       ├── router.py        # Intent classification
│       └── prompts/         # System prompts
├── data/datasets/           # Training datasets
├── tests/                   # Unit tests
├── notebooks/               # Validation notebooks
└── docs/                    # Documentation
```

## 🚀 Installation

### Linux/Mac

```bash
chmod +x install.sh
./install.sh
```

### Windows

```powershell
.\install.ps1
```

### Manual Installation

```bash
# Clone the repository
git clone <repository-url>
cd kimi-pimcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Pre-download models
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

## 💻 Usage

### Running the MCP Server

```bash
# Start the MCP server
python src/server.py

# Or use the installed command
kimi-pimcp
```

The server communicates via stdin/stdout using JSON-RPC 2.0 protocol.

### Running the REST API

```bash
# Start the REST API server
python src/rest_api.py --host 0.0.0.0 --port 8000

# With auto-reload (development)
python src/rest_api.py --reload
```

The API will be available at `http://localhost:8000`

### Running the Web UI

```bash
# Start the web UI server
python src/web_ui.py
```

Then open `http://localhost:8080` in your browser.

## 🛠️ Available Tools

### Core Tools

#### 1. Initialize Index
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "initialize_index",
    "arguments": {
      "project_path": "/path/to/project",
      "force_reindex": false
    }
  }
}
```

#### 2. Query Context
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "query_context",
    "arguments": {
      "query": "authenticate user",
      "top_k": 5,
      "filter_ext": [".py", ".js"],
      "use_mmr": true
    }
  }
}
```

#### 3. Select Skill
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "select_skill",
    "arguments": {
      "query": "fix login bug"
    }
  }
}
```

#### 4. Compress Output
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "compress_output",
    "arguments": {
      "text": "Please help me fix this bug...",
      "level": "full"
    }
  }
}
```

### New Tools in v0.2.0

#### 5. Get Query History
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_query_history",
    "arguments": {
      "limit": 10
    }
  }
}
```

#### 6. Switch Project
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "switch_project",
    "arguments": {
      "project_path": "/path/to/other/project"
    }
  }
}
```

#### 7. Get Dependencies
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "get_dependencies",
    "arguments": {
      "filepath": "/path/to/file.py"
    }
  }
}
```

#### 8. Find Similar Code
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "find_similar_code",
    "arguments": {
      "filepath": "/path/to/file.py"
    }
  }
}
```

#### 9. Summarize Chunk
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "summarize_chunk",
    "arguments": {
      "content": "def hello(): print('world')",
      "chunk_type": "function",
      "language": "python"
    }
  }
}
```

#### 10. Export/Import Index
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "export_index",
    "arguments": {
      "output_path": "/path/to/export"
    }
  }
}
```

## 🎯 Skills

| Skill | Description | Use Cases |
|-------|-------------|-----------|
| **debugger** | Debug code issues | Errors, exceptions, crashes |
| **architect** | System design | Architecture, patterns, scalability |
| **explainer** | Explain code/concepts | Documentation, understanding |
| **tester** | Testing & QA | Unit tests, integration tests |
| **caveman** | Concise responses | Token-optimized output |

## ⚙️ Configuration

Edit `config.yaml` to customize:

```yaml
models:
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
  use_cross_encoder: true

indexer:
  supported_extensions: [".py", ".js", ".ts"]
  exclude_dirs: ["node_modules", ".git"]
  max_file_size_mb: 10

compressor:
  default_level: "auto"

performance:
  query_cache_size: 100
  model_cache_size: 2
```

## 📊 Performance Targets

| Operation | Target | v0.1.0 | v0.2.0 |
|-----------|--------|--------|--------|
| Indexing | <100ms/file | ~50ms | ~30ms (incremental) |
| Query | <200ms | ~100ms | ~50ms (cached) |
| Classification | <10ms | ~5ms | ~3ms |
| Compression | <5ms | ~2ms | ~1ms |
| Memory | <500MB | ~300MB | ~250MB |

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run validation notebook
jupyter notebook notebooks/validation.ipynb
```

## 📚 REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/index` | POST | Index a project |
| `/index/status` | GET | Get indexing status |
| `/query` | POST | Search code |
| `/compress` | POST | Compress text |
| `/skills/select` | POST | Detect skill |
| `/skills` | GET | List skills |
| `/stats` | GET | Get all stats |
| `/dependencies` | GET | Get file dependencies |
| `/dependencies/stats` | GET | Dependency graph stats |
| `/git/status` | GET | Git status |
| `/git/changes` | GET | Git changes |
| `/cache/clear` | POST | Clear all caches |

## 📖 API Reference

### Indexer Module

```python
from indexer import ProjectIndexer, get_indexer

indexer = get_indexer(project_path="/path/to/project")
stats = indexer.index_project("/path/to/project")
print(f"Indexed {stats['files_indexed']} files")
print(f"Skipped {stats['files_skipped']} unchanged files")
```

### Retriever Module

```python
from retriever import ContextRetriever, get_retriever

retriever = get_retriever()
retriever.load_index("/path/to/project")
results = retriever.query("authenticate user", top_k=5)

# Check cache stats
print(retriever.get_stats()['cache'])
```

### File Watcher

```python
from file_watcher import ProjectFileWatcher

def on_change(event):
    print(f"File {event.change_type.value}: {event.filepath}")

watcher = ProjectFileWatcher("/path/to/project", on_change)
watcher.start()
```

### Dependency Graph

```python
from dependency_graph import DependencyGraph

graph = DependencyGraph("/path/to/project")
graph.build()

# Get dependencies
deps = graph.get_dependencies("/path/to/file.py")
dependents = graph.get_dependents("/path/to/file.py")

# Find circular dependencies
cycles = graph.find_circular_dependencies()
```

### Git Integration

```python
from git_integration import GitIntegration

git = GitIntegration("/path/to/project")

# Get changed files since last commit
changes = git.get_changed_files_since("HEAD~1")
files_to_index, files_to_remove = git.get_files_to_index("HEAD~1")
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- [sentence-transformers](https://www.sbert.net/) for embeddings
- [FAISS](https://github.com/facebookresearch/faiss) for vector search
- [scikit-learn](https://scikit-learn.org/) for classification
- [watchdog](https://github.com/gorakhargosh/watchdog) for file watching
- [FastAPI](https://fastapi.tiangolo.com/) for REST API
