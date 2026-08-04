"""
Entry point for running Kimi-PIMCP as a module.

Usage:
    python -m src            # Run MCP Server (default)
    python -m src server     # Run MCP Server
    python -m src web        # Run Web UI
"""

import sys

if len(sys.argv) > 1 and sys.argv[1] == 'web':
    # Run Web UI
    from src.web_ui import main
    main()
else:
    # Run MCP Server (default)
    from src.server import main
    main()
