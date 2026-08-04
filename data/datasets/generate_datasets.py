#!/usr/bin/env python3
"""
Dataset Generator for Kimi-PIMCP
Generates expanded datasets with 500+ examples.
"""

import json
import random
from pathlib import Path

# Templates for generating code snippets
PYTHON_TEMPLATES = [
    # Functions
    ("def {name}({params}):\n    {body}", "function"),
    ("async def {name}({params}):\n    {body}", "function"),
    ("@decorator\ndef {name}({params}):\n    {body}", "function"),
    # Classes
    ("class {class_name}:\n    def __init__(self, {params}):\n        {init_body}\n    def {method_name}(self, {params}):\n        {body}", "class"),
    ("class {class_name}({parent}):\n    def {method_name}(self, {params}):\n        {body}", "class"),
    # Error handling
    ("try:\n    {try_body}\nexcept {exception} as e:\n    {except_body}", "error-handling"),
    # API endpoints
    ("@app.route('{route}', methods=['{method}'])\ndef {name}({params}):\n    {body}", "api"),
]

JS_TS_TEMPLATES = [
    # Functions
    ("function {name}({params}) {{\n    {body}\n}}", "function"),
    ("const {name} = ({params}) => {{\n    {body}\n}};", "function"),
    ("async function {name}({params}) {{\n    {body}\n}}", "function"),
    # Classes
    ("class {class_name} {{\n    constructor({params}) {{\n        {init_body}\n    }}\n    {method_name}({params}) {{\n        {body}\n    }}\n}}", "class"),
    ("class {class_name} extends {parent} {{\n    {method_name}({params}) {{\n        {body}\n    }}\n}}", "class"),
    # React hooks
    ("const [{state}, set{state_cap}] = useState({initial});\nuseEffect(() => {{\n    {body}\n}}, [{deps}]);", "hook"),
    # Error handling
    ("try {{\n    {try_body}\n}} catch (error) {{\n    {except_body}\n}}", "error-handling"),
]

# Names for generation
FUNCTION_NAMES = [
    "authenticate_user", "validate_token", "hash_password", "generate_jwt",
    "get_user", "create_user", "update_user", "delete_user",
    "fetch_data", "process_payment", "send_email", "upload_file",
    "calculate_total", "format_date", "parse_json", "validate_input",
    "connect_database", "execute_query", "cache_result", "log_event",
    "handle_request", "middleware", "decorator", "retry_operation",
    "batch_process", "stream_data", "compress_file", "encrypt_data",
    "schedule_job", "run_task", "cleanup", "initialize", "shutdown"
]

CLASS_NAMES = [
    "User", "Product", "Order", "Payment", "Session", "Token",
    "Database", "Cache", "Queue", "Worker", "Handler", "Controller",
    "Service", "Repository", "Manager", "Client", "Server", "Router",
    "Middleware", "Validator", "Serializer", "Factory", "Builder"
]

PARAMS_LIST = [
    "user_id", "username", "email", "password", "token", "data",
    "request", "response", "config", "options", "callback", "context",
    "payload", "headers", "query", "params", "body", "files"
]

BODY_SNIPPETS = [
    "return data",
    "print('Processing...')",
    "logger.info('Operation completed')",
    "await asyncio.sleep(1)",
    "raise ValueError('Invalid input')",
    "return {'success': True, 'data': result}",
    "if not valid:\n        return None",
    "cache.set(key, value, ttl=3600)",
    "db.execute(query, params)",
    "return json.dumps(result)",
]

TAGS = {
    "function": ["utility", "helper", "core", "api", "internal"],
    "class": ["model", "service", "controller", "manager", "handler"],
    "error-handling": ["validation", "logging", "recovery", "cleanup"],
    "api": ["rest", "graphql", "endpoint", "route", "middleware"],
    "hook": ["react", "state", "effect", "lifecycle"],
}

SKILL_QUERIES_TEMPLATES = {
    "debugger": [
        "{error} in {component}",
        "{component} returning {status_code}",
        "fix {issue} in {file_type}",
        "debug {feature} not working",
        "{error_type} exception in {context}",
        "why is {component} {problem}",
        "{action} causing {error}",
        "troubleshoot {feature} failure",
    ],
    "architect": [
        "how to structure {project_type}",
        "design {feature} for {scale}",
        "best practice for {context}",
        "architecture for {project_type}",
        "scale {component} to {metric}",
        "pattern for {use_case}",
        "refactor {component} to {goal}",
        "database schema for {domain}",
    ],
    "explainer": [
        "explain how {concept} works",
        "what does {code_element} do",
        "document {feature}",
        "how to use {library}",
        "purpose of {pattern}",
        "understand {algorithm}",
        "why use {technology}",
        "difference between {a} and {b}",
    ],
    "tester": [
        "write tests for {component}",
        "test {feature} with {framework}",
        "unit tests for {function}",
        "integration test for {endpoint}",
        "e2e test for {flow}",
        "coverage for {module}",
        "mock {dependency}",
        "test {scenario} scenario",
    ],
}

ERROR_TYPES = [
    "null pointer", "undefined variable", "type error", "syntax error",
    "runtime error", "timeout", "connection refused", "404", "500",
    "401 unauthorized", "403 forbidden", "memory leak", "deadlock"
]

COMPONENTS = [
    "auth service", "login form", "API endpoint", "database query",
    "middleware", "React component", "payment gateway", "email service",
    "file upload", "cache layer", "queue worker", "websocket"
]

PROJECT_TYPES = [
    "microservices", "monolith", "serverless", "SPA", "API",
    "CLI tool", "library", "framework", "mobile app"
]

CONCEPTS = [
    "dependency injection", "event loop", "promises", "async/await",
    "closures", "prototypes", "generics", "decorators", "middleware",
    "caching", "indexing", "sharding", "replication", "CQRS"
]


def generate_python_snippet(index: int) -> dict:
    """Generate a Python code snippet."""
    template, snippet_type = random.choice(PYTHON_TEMPLATES)
    
    name = random.choice(FUNCTION_NAMES)
    class_name = random.choice(CLASS_NAMES)
    params = ", ".join(random.sample(PARAMS_LIST, k=random.randint(1, 3)))
    body = random.choice(BODY_SNIPPETS)
    
    code = template.format(
        name=f"{name}_{index}",
        class_name=f"{class_name}_{index}",
        parent=random.choice(["BaseModel", "object", "Exception"]),
        method_name=f"process_{index}",
        params=params,
        body=body,
        init_body="self.data = data",
        try_body="result = operation()",
        except_body="logger.error(f'Error: {e}')",
        exception=random.choice(["ValueError", "TypeError", "KeyError"]),
        route=f"/api/{name}/{index}",
        method=random.choice(["GET", "POST", "PUT", "DELETE"]),
    )
    
    return {
        "code": code,
        "description": f"{snippet_type.capitalize()} for {name} operation",
        "language": "python",
        "type": snippet_type,
        "tags": random.sample(TAGS.get(snippet_type, ["general"]), k=random.randint(1, 3))
    }


def generate_js_snippet(index: int) -> dict:
    """Generate a JavaScript/TypeScript code snippet."""
    template, snippet_type = random.choice(JS_TS_TEMPLATES)
    
    name = random.choice(FUNCTION_NAMES)
    class_name = random.choice(CLASS_NAMES)
    params = ", ".join(random.sample(PARAMS_LIST, k=random.randint(1, 3)))
    body = random.choice(BODY_SNIPPETS)
    state_name = random.choice(["data", "user", "items", "count"])
    
    code = template.format(
        name=f"{name}{index}",
        class_name=f"{class_name}{index}",
        parent=random.choice(["Component", "Service", "Error"]),
        method_name=f"handle{index}",
        params=params,
        body=body,
        init_body="this.data = data;",
        try_body="const result = await operation();",
        except_body="console.error('Error:', error);",
        state=state_name,
        state_cap=state_name.capitalize(),
        initial="null",
        deps="[]",
    )
    
    language = random.choice(["javascript", "typescript"])
    
    return {
        "code": code,
        "description": f"{snippet_type.capitalize()} for {name} in {language}",
        "language": language,
        "type": snippet_type,
        "tags": random.sample(TAGS.get(snippet_type, ["general"]), k=random.randint(1, 3))
    }


def generate_code_snippets(count: int = 500) -> list:
    """Generate code snippets dataset."""
    snippets = []
    
    # Keep original 20 snippets
    original_file = Path(__file__).parent / "code_snippets.json"
    if original_file.exists():
        with open(original_file, 'r') as f:
            original = json.load(f)
            snippets.extend(original[:20])
    
    # Generate new snippets
    for i in range(len(snippets), count):
        if random.random() < 0.5:
            snippet = generate_python_snippet(i)
        else:
            snippet = generate_js_snippet(i)
        snippets.append(snippet)
    
    return snippets


def generate_skill_queries(count: int = 300) -> list:
    """Generate skill queries dataset."""
    queries = []
    
    # Keep original queries
    original_file = Path(__file__).parent / "skill_queries.json"
    if original_file.exists():
        with open(original_file, 'r') as f:
            original = json.load(f)
            queries.extend(original)
    
    # Generate additional queries
    queries_per_skill = (count - len(queries)) // 4
    
    for skill, templates in SKILL_QUERIES_TEMPLATES.items():
        for _ in range(queries_per_skill):
            template = random.choice(templates)
            
            query = template.format(
                error=random.choice(ERROR_TYPES),
                component=random.choice(COMPONENTS),
                status_code=random.choice(["401", "403", "404", "500", "502", "503"]),
                issue=random.choice(["bug", "error", "crash", "timeout"]),
                file_type=random.choice(["API", "database", "frontend", "backend"]),
                feature=random.choice(["login", "payment", "upload", "search", "filter"]),
                error_type=random.choice(ERROR_TYPES),
                context=random.choice(["production", "testing", "development"]),
                action=random.choice(["updating", "deleting", "creating", "fetching"]),
                problem=random.choice(["slow", "broken", "failing", "crashing"]),
                project_type=random.choice(PROJECT_TYPES),
                scale=random.choice(["1K users", "1M users", "10M users"]),
                metric=random.choice(["1K RPS", "10K RPS", "100K RPS"]),
                use_case=random.choice(["caching", "auth", "logging", "queueing"]),
                goal=random.choice(["microservices", "cleaner code", "better performance"]),
                domain=random.choice(["e-commerce", "social network", "banking"]),
                concept=random.choice(CONCEPTS),
                code_element=random.choice(["function", "class", "decorator"]),
                library=random.choice(["React", "Express", "FastAPI", "Django"]),
                pattern=random.choice(["singleton", "factory", "observer", "strategy"]),
                algorithm=random.choice(["quicksort", "binary search", "DFS", "BFS"]),
                technology=random.choice(["Redis", "Kafka", "GraphQL", "WebSockets"]),
                a=random.choice(["REST", "GraphQL"]),
                b=random.choice(["SQL", "NoSQL"]),
                framework=random.choice(["Jest", "pytest", "Mocha", "Cypress"]),
                function=random.choice(FUNCTION_NAMES),
                endpoint=random.choice(["/api/users", "/api/orders", "/api/products"]),
                flow=random.choice(["checkout", "signup", "login", "payment"]),
                module=random.choice(["auth", "payment", "user", "product"]),
                dependency=random.choice(["database", "API", "cache", "queue"]),
                scenario=random.choice(["edge case", "error", "success", "timeout"]),
            )
            
            queries.append({
                "query": query,
                "skill": skill,
                "context": random.choice(["general", "specific", "urgent"]),
                "confidence": random.choice(["high", "medium", "high"])
            })
    
    return queries[:count]


def generate_project_contexts(count: int = 50) -> list:
    """Generate project contexts dataset."""
    contexts = []
    
    # Keep original
    original_file = Path(__file__).parent / "project_contexts.json"
    if original_file.exists():
        with open(original_file, 'r') as f:
            original = json.load(f)
            contexts.extend(original)
    
    # Project types and their typical files
    project_structures = {
        "react": {
            "files": ["src/App.js", "src/components/{name}.jsx", "src/hooks/use{name}.js", 
                     "src/services/api.js", "src/utils/helpers.js", "package.json"],
            "queries": ["fix {feature} bug", "optimize {feature} performance", "add {feature} test"]
        },
        "flask": {
            "files": ["app.py", "models/{name}.py", "routes/{name}.py", 
                     "services/{name}.py", "utils/validators.py", "config.py"],
            "queries": ["fix {feature} endpoint", "add {feature} validation", "optimize {feature} query"]
        },
        "express": {
            "files": ["server.js", "routes/{name}.js", "controllers/{name}Controller.js",
                     "models/{name}.js", "middleware/auth.js", "config/database.js"],
            "queries": ["fix {feature} middleware", "add {feature} route", "debug {feature}"]
        },
        "django": {
            "files": ["manage.py", "{app}/models.py", "{app}/views.py", 
                     "{app}/serializers.py", "{app}/urls.py", "requirements.txt"],
            "queries": ["fix {feature} view", "add {feature} model", "optimize {feature}"]
        },
        "fastapi": {
            "files": ["main.py", "routers/{name}.py", "models/schemas.py",
                     "services/crud.py", "database/connection.py", "requirements.txt"],
            "queries": ["fix {feature} endpoint", "add {feature} schema", "test {feature}"]
        },
    }
    
    features = ["auth", "payment", "user", "product", "order", "search", "filter", "upload"]
    
    for i in range(len(contexts), count):
        project_type = random.choice(list(project_structures.keys()))
        structure = project_structures[project_type]
        feature = random.choice(features)
        
        files = [f.format(name=feature.capitalize(), app=feature.lower()) for f in structure["files"]]
        query = random.choice(structure["queries"]).format(feature=feature)
        
        # Expected files are those related to the feature
        expected_files = [f for f in files if feature.lower() in f.lower() or "auth" in f.lower()]
        if not expected_files:
            expected_files = files[:3]
        
        contexts.append({
            "project_type": project_type,
            "files": files,
            "query": query,
            "expected_files": expected_files
        })
    
    return contexts


def main():
    """Generate all datasets."""
    output_dir = Path(__file__).parent
    
    print("Generating datasets for Kimi-PIMCP...")
    
    # Generate code snippets
    print("Generating 500 code snippets...")
    code_snippets = generate_code_snippets(500)
    with open(output_dir / "code_snippets.json", 'w') as f:
        json.dump(code_snippets, f, indent=2)
    print(f"  ✓ Generated {len(code_snippets)} code snippets")
    
    # Generate skill queries
    print("Generating 300 skill queries...")
    skill_queries = generate_skill_queries(300)
    with open(output_dir / "skill_queries.json", 'w') as f:
        json.dump(skill_queries, f, indent=2)
    print(f"  ✓ Generated {len(skill_queries)} skill queries")
    
    # Generate project contexts
    print("Generating 50 project contexts...")
    project_contexts = generate_project_contexts(50)
    with open(output_dir / "project_contexts.json", 'w') as f:
        json.dump(project_contexts, f, indent=2)
    print(f"  ✓ Generated {len(project_contexts)} project contexts")
    
    print("\n✅ All datasets generated successfully!")
    print(f"   Location: {output_dir}")


if __name__ == "__main__":
    main()
