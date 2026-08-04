#!/usr/bin/env python3
"""
MCP Test Script for Kimi-PIMCP
Tests the Model Context Protocol server via JSON-RPC.
"""

import json
import subprocess
import sys
import time
from pathlib import Path


class MCPTester:
    """Test client for MCP server."""
    
    def __init__(self, server_path: str = None):
        """Initialize tester."""
        if server_path is None:
            # Default to src/server.py in same directory
            server_path = Path(__file__).parent / "src" / "server.py"
        
        self.server_path = server_path
        self.process = None
        self.request_id = 0
    
    def start_server(self) -> bool:
        """Start the MCP server."""
        print("🚀 Starting MCP server...")
        
        try:
            self.process = subprocess.Popen(
                [sys.executable, str(self.server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Wait a bit for server to start
            time.sleep(1)
            
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                print(f"❌ Server failed to start: {stderr}")
                return False
            
            print("✅ Server started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server."""
        if self.process:
            print("\n🛑 Stopping server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            print("✅ Server stopped")
    
    def send_request(self, method: str, params: dict = None) -> dict:
        """Send a JSON-RPC request."""
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        if params:
            request["params"] = params
        
        # Send request
        request_line = json.dumps(request) + "\n"
        self.process.stdin.write(request_line)
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        
        try:
            return json.loads(response_line)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {e}", "raw": response_line}
    
    def test_initialize(self) -> bool:
        """Test initialize request."""
        print("\n📋 Test 1: Initialize")
        
        response = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        })
        
        if "result" in response:
            result = response["result"]
            print(f"  ✅ Server: {result.get('serverInfo', {}).get('name')} v{result.get('serverInfo', {}).get('version')}")
            print(f"  ✅ Protocol: {result.get('protocolVersion')}")
            return True
        else:
            print(f"  ❌ Failed: {response.get('error', 'Unknown error')}")
            return False
    
    def test_tools_list(self) -> bool:
        """Test tools/list request."""
        print("\n📋 Test 2: List Tools")
        
        response = self.send_request("tools/list")
        
        if "result" in response:
            tools = response["result"].get("tools", [])
            print(f"  ✅ Available tools: {len(tools)}")
            for tool in tools:
                print(f"     • {tool['name']}: {tool['description'][:50]}...")
            return True
        else:
            print(f"  ❌ Failed: {response.get('error', 'Unknown error')}")
            return False
    
    def test_initialize_index(self, project_path: str = None) -> bool:
        """Test initialize_index tool."""
        print("\n📋 Test 3: Initialize Index")
        
        if project_path is None:
            # Use current directory as test
            project_path = str(Path(__file__).parent)
        
        print(f"  Indexing: {project_path}")
        
        response = self.send_request("tools/call", {
            "name": "initialize_index",
            "arguments": {
                "project_path": project_path,
                "force_reindex": True
            }
        })
        
        if "result" in response:
            content = response["result"].get("content", [{}])[0].get("text", "{}")
            try:
                result = json.loads(content)
                if result.get("success"):
                    stats = result.get("stats", {})
                    print(f"  ✅ Indexed {stats.get('files_indexed', 0)} files")
                    print(f"  ✅ Created {stats.get('chunks_created', 0)} chunks")
                    print(f"  ⏱️  Time: {stats.get('index_time_ms', 0)}ms")
                    return True
                else:
                    print(f"  ❌ Indexing failed")
                    return False
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse result")
                return False
        else:
            error = response.get("error", {})
            print(f"  ❌ Failed: {error.get('message', 'Unknown error')}")
            return False
    
    def test_query_context(self, query: str = "authenticate user") -> bool:
        """Test query_context tool."""
        print(f"\n📋 Test 4: Query Context - '{query}'")
        
        response = self.send_request("tools/call", {
            "name": "query_context",
            "arguments": {
                "query": query,
                "top_k": 3
            }
        })
        
        if "result" in response:
            content = response["result"].get("content", [{}])[0].get("text", "{}")
            try:
                result = json.loads(content)
                results = result.get("results", [])
                print(f"  ✅ Found {len(results)} results")
                for i, r in enumerate(results[:3], 1):
                    print(f"     {i}. {r.get('filepath', 'unknown')} (score: {r.get('similarity_score', 0):.3f})")
                return True
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse result")
                return False
        else:
            error = response.get("error", {})
            print(f"  ❌ Failed: {error.get('message', 'Unknown error')}")
            return False
    
    def test_select_skill(self, query: str = "fix login bug") -> bool:
        """Test select_skill tool."""
        print(f"\n📋 Test 5: Select Skill - '{query}'")
        
        response = self.send_request("tools/call", {
            "name": "select_skill",
            "arguments": {
                "query": query
            }
        })
        
        if "result" in response:
            content = response["result"].get("content", [{}])[0].get("text", "{}")
            try:
                result = json.loads(content)
                routing = result.get("routing", {})
                skill = routing.get("skill", "unknown")
                confidence = routing.get("confidence", 0)
                print(f"  ✅ Selected skill: {skill} (confidence: {confidence:.2f})")
                
                all_scores = routing.get("all_scores", {})
                print(f"  📊 All scores:")
                for s, score in sorted(all_scores.items(), key=lambda x: -x[1]):
                    marker = "✓" if s == skill else " "
                    print(f"     [{marker}] {s}: {score:.3f}")
                return True
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse result")
                return False
        else:
            error = response.get("error", {})
            print(f"  ❌ Failed: {error.get('message', 'Unknown error')}")
            return False
    
    def test_compress_output(self, text: str = None) -> bool:
        """Test compress_output tool."""
        print("\n📋 Test 6: Compress Output")
        
        if text is None:
            text = "Please help me fix this bug. The function is not working correctly. Thank you very much!"
        
        response = self.send_request("tools/call", {
            "name": "compress_output",
            "arguments": {
                "text": text,
                "level": "full"
            }
        })
        
        if "result" in response:
            content = response["result"].get("content", [{}])[0].get("text", "{}")
            try:
                result = json.loads(content)
                stats = result.get("stats", {})
                original = stats.get("original_tokens", 0)
                compressed = stats.get("compressed_tokens", 0)
                ratio = stats.get("compression_ratio", 0)
                print(f"  ✅ Tokens: {original} → {compressed}")
                print(f"  ✅ Reduction: {ratio*100:.1f}%")
                print(f"  ⏱️  Time: {stats.get('processing_time_ms', 0)}ms")
                return True
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse result")
                return False
        else:
            error = response.get("error", {})
            print(f"  ❌ Failed: {error.get('message', 'Unknown error')}")
            return False
    
    def test_get_stats(self) -> bool:
        """Test get_stats tool."""
        print("\n📋 Test 7: Get Stats")
        
        response = self.send_request("tools/call", {
            "name": "get_stats",
            "arguments": {}
        })
        
        if "result" in response:
            content = response["result"].get("content", [{}])[0].get("text", "{}")
            try:
                result = json.loads(content)
                print(f"  ✅ Stats retrieved:")
                
                indexer = result.get("indexer", {})
                print(f"     • Files indexed: {indexer.get('files_indexed', 0)}")
                print(f"     • Chunks created: {indexer.get('chunks_created', 0)}")
                
                retriever = result.get("retriever", {})
                print(f"     • Queries processed: {retriever.get('queries_processed', 0)}")
                
                compressor = result.get("compressor", {})
                print(f"     • Compressions: {compressor.get('total_compressions', 0)}")
                
                return True
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse result")
                return False
        else:
            error = response.get("error", {})
            print(f"  ❌ Failed: {error.get('message', 'Unknown error')}")
            return False
    
    def run_all_tests(self, project_path: str = None) -> dict:
        """Run all tests."""
        print("=" * 60)
        print("🧪 Kimi-PIMCP MCP Test Suite")
        print("=" * 60)
        
        results = {
            "initialize": False,
            "tools_list": False,
            "initialize_index": False,
            "query_context": False,
            "select_skill": False,
            "compress_output": False,
            "get_stats": False
        }
        
        # Start server
        if not self.start_server():
            print("\n❌ Cannot start server, aborting tests")
            return results
        
        try:
            # Run tests
            results["initialize"] = self.test_initialize()
            results["tools_list"] = self.test_tools_list()
            results["initialize_index"] = self.test_initialize_index(project_path)
            results["query_context"] = self.test_query_context()
            results["select_skill"] = self.test_select_skill()
            results["compress_output"] = self.test_compress_output()
            results["get_stats"] = self.test_get_stats()
            
        finally:
            self.stop_server()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test, passed_test in results.items():
            status = "✅ PASS" if passed_test else "❌ FAIL"
            print(f"  {status}: {test}")
        
        print(f"\n🎯 Result: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        elif passed >= total * 0.7:
            print("⚠️  Most tests passed, some issues found")
        else:
            print("❌ Many tests failed, check errors above")
        
        return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Kimi-PIMCP MCP Server")
    parser.add_argument("--server", help="Path to server.py")
    parser.add_argument("--project", help="Project path to index for testing")
    parser.add_argument("--test", choices=["all", "init", "tools", "index", "query", "skill", "compress", "stats"],
                       default="all", help="Test to run")
    
    args = parser.parse_args()
    
    # Create tester
    tester = MCPTester(args.server)
    
    if args.test == "all":
        tester.run_all_tests(args.project)
    else:
        # Run specific test
        if not tester.start_server():
            sys.exit(1)
        
        try:
            if args.test == "init":
                tester.test_initialize()
            elif args.test == "tools":
                tester.test_tools_list()
            elif args.test == "index":
                tester.test_initialize_index(args.project)
            elif args.test == "query":
                tester.test_initialize_index(args.project)
                tester.test_query_context()
            elif args.test == "skill":
                tester.test_select_skill()
            elif args.test == "compress":
                tester.test_compress_output()
            elif args.test == "stats":
                tester.test_initialize_index(args.project)
                tester.test_get_stats()
        finally:
            tester.stop_server()


if __name__ == "__main__":
    main()
