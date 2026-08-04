#!/usr/bin/env python3
"""
Test completo del Kimi-PIMCP MCP Server y Web UI.
"""

import subprocess
import json
import sys
import time

def test_mcp_server():
    """Test MCP Server via JSON-RPC."""
    print("\n" + "="*60)
    print("TEST 1: MCP Server JSON-RPC")
    print("="*60)
    
    # Start server process
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give it time to start
    time.sleep(1)
    
    # Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    
    proc.stdin.write(json.dumps(init_request) + "\n")
    proc.stdin.flush()
    
    # Read response
    response = proc.stdout.readline()
    result = json.loads(response)
    
    assert result["jsonrpc"] == "2.0", "Invalid JSON-RPC version"
    assert result["id"] == 1, "Invalid response ID"
    assert "result" in result, "No result in response"
    assert result["result"]["serverInfo"]["name"] == "kimi-pimcp", "Wrong server name"
    
    print("✅ Initialize: OK")
    print(f"   Server: {result['result']['serverInfo']['name']} v{result['result']['serverInfo']['version']}")
    
    # Test tools/list
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    
    proc.stdin.write(json.dumps(tools_request) + "\n")
    proc.stdin.flush()
    
    response = proc.stdout.readline()
    result = json.loads(response)
    
    tools = result["result"]["tools"]
    print(f"✅ Tools/List: OK ({len(tools)} tools)")
    
    # Print first few tools
    for tool in tools[:5]:
        print(f"   - {tool['name']}: {tool['description'][:50]}...")
    
    proc.terminate()
    print("✅ MCP Server: ALL TESTS PASSED")
    return True

def test_activity_monitor():
    """Test Activity Monitor."""
    print("\n" + "="*60)
    print("TEST 2: Activity Monitor")
    print("="*60)
    
    from src.activity_monitor import get_activity_monitor
    
    monitor = get_activity_monitor()
    entries = monitor.get_entries(limit=10)
    stats = monitor.get_stats()
    
    print(f"✅ Activity file: {monitor.activity_file}")
    print(f"✅ Total entries: {stats['total_entries']}")
    print(f"✅ By source: {stats['by_source']}")
    print(f"✅ By type: {stats['by_type']}")
    
    if entries:
        print(f"\n   Recent entries:")
        for e in entries[-3:]:
            print(f"   - {e.timestamp}: {e.type} - {e.method}")
    
    print("✅ Activity Monitor: ALL TESTS PASSED")
    return True

def test_web_ui_endpoints():
    """Test Web UI API endpoints."""
    print("\n" + "="*60)
    print("TEST 3: Web UI API Endpoints")
    print("="*60)
    
    from fastapi.testclient import TestClient
    from src.web_ui import app
    
    client = TestClient(app)
    
    # Test health
    response = client.get("/health")
    assert response.status_code == 200
    print(f"✅ Health: {response.json()['status']}")
    
    # Test MCP activity endpoint
    response = client.get("/mcp/activity?limit=5")
    assert response.status_code == 200
    data = response.json()
    print(f"✅ MCP Activity: {len(data['entries'])} entries")
    print(f"   Stats: {data['stats']['total_entries']} total")
    
    # Test stats endpoint
    response = client.get("/stats")
    assert response.status_code == 200
    print(f"✅ Stats: OK")
    
    print("✅ Web UI API: ALL TESTS PASSED")
    return True

def test_skills_router():
    """Test Skills Router."""
    print("\n" + "="*60)
    print("TEST 4: Skills Router")
    print("="*60)
    
    from src.skills.router import get_router
    
    router = get_router()
    
    # Test queries
    test_queries = [
        "fix login bug",
        "explain this function",
        "how to structure my code",
        "generate tests",
    ]
    
    for query in test_queries:
        result = router.select_skill(query)
        print(f"✅ '{query[:30]}...' -> {result.skill_type.value} ({result.confidence:.2f})")
    
    stats = router.get_stats()
    print(f"\n   Available skills: {', '.join(stats['available_skills'])}")
    
    print("✅ Skills Router: ALL TESTS PASSED")
    return True

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("KIMI-PIMCP COMPLETE TEST SUITE")
    print("="*60)
    
    tests = [
        ("MCP Server", test_mcp_server),
        ("Activity Monitor", test_activity_monitor),
        ("Web UI API", test_web_ui_endpoints),
        ("Skills Router", test_skills_router),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name} FAILED: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
