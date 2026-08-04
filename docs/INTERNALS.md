# Kimi-PIMCP: Documentación Interna

## Índice
1. [Arquitectura General](#arquitectura-general)
2. [Flujo de Datos](#flujo-de-datos)
3. [Módulos Principales](#módulos-principales)
4. [Web UI - Funcionalidades Detalladas](#web-ui---funcionalidades-detalladas)
5. [Protocolo MCP](#protocolo-mcp)
6. [Optimizaciones Implementadas](#optimizaciones-implementadas)

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              KIMI-PIMCP                                      │
│                    (Model Context Protocol Server)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │   Indexer    │───▶│  Retriever   │───▶│  Compressor  │───▶│  Skills  │  │
│  │  (indexer)   │    │ (retriever)  │    │ (compressor) │    │ (router) │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘  │
│         │                   │                   │                  │        │
│         ▼                   ▼                   ▼                  ▼        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         FAISS Vector Store                           │   │
│  │              (Almacenamiento de embeddings + metadatos)              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Módulos Auxiliares (Opcionales)                   │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │   │
│  │  │File Watcher│  │  Git Int.  │  │  DepGraph  │  │ Summarizer │    │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Web UI + REST API                            │   │
│  │                    (FastAPI + HTML/JS Frontend)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Datos

### 1. Indexación de Proyecto

```
Proyecto (carpeta)
       │
       ▼
┌──────────────┐
│  File Scanner │  ← Recorre recursivamente todos los archivos
│   (indexer)   │
└──────────────┘
       │
       ▼
┌──────────────┐
│ File Filter   │  ← Filtra por extensión y tamaño (ignora >10MB)
│   (indexer)   │
└──────────────┘
       │
       ▼
┌──────────────┐
│ Hash Checker  │  ← Compara hash MD5 para indexación incremental
│   (indexer)   │
└──────────────┘
       │
       ▼
┌──────────────┐
│ Code Chunker  │  ← Divide archivos en chunks (funciones, clases, etc.)
│   (indexer)   │
└──────────────┘
       │
       ▼
┌──────────────┐
│  Embedding    │  ← Convierte texto a vectores (384 dimensiones)
│ (sentence-   │    Modelo: 'all-MiniLM-L6-v2'
│ transformers)│
└──────────────┘
       │
       ▼
┌──────────────┐
│ FAISS Index   │  ← Almacena vectores para búsqueda eficiente
│  (indexer)    │    IndexFlatIP (producto interno = similitud coseno)
└──────────────┘
```

### 2. Búsqueda (Query)

```
Query del usuario
       │
       ▼
┌──────────────┐
│ Query Cache   │  ← Verifica si la query ya fue procesada (LRU cache)
│ (retriever)   │
└──────────────┘
       │ Cache miss
       ▼
┌──────────────┐
│  Embedding    │  ← Convierte query a vector (mismo modelo)
│   (query)     │
└──────────────┘
       │
       ▼
┌──────────────┐
│ FAISS Search  │  ← Busca los K vectores más similares
│  (retriever)  │    Usa IndexFlatIP (búsqueda exacta O(n))
└──────────────┘
       │
       ▼
┌──────────────┐
│     MMR       │  ← Maximal Marginal Relevance (opcional)
│  (retriever)  │    Balance entre relevancia y diversidad
└──────────────┘
       │
       ▼
┌──────────────┐
│ Re-ranking    │  ← Cross-encoder reordena resultados (opcional)
│ (retriever)   │    Modelo: 'cross-encoder/ms-marco-MiniLM-L-6-v2'
└──────────────┘
       │
       ▼
┌──────────────┐
│ Context Build │  ← Enriquece con contexto (imports, llamadas)
│ (retriever)   │
└──────────────┘
       │
       ▼
  Resultados
```

### 3. Compresión de Texto

```
Texto de entrada
       │
       ▼
┌──────────────┐
│ Token Count   │  ← Cuenta tokens con tiktoken (encoding cl100k_base)
│ (compressor)  │
└──────────────┘
       │
       ▼
┌──────────────┐
│ Level Select  │  ← Selecciona nivel de compresión:
│ (compressor)  │    - auto: basado en tamaño del texto
│               │    - lite: elimina comentarios y espacios
│               │    - full: + abreviaciones, + contracciones
│               │    - ultra: + elimina código muerto
│               │    - wenyan: convierte a chino clásico (experimental)
└──────────────┘
       │
       ▼
┌──────────────┐
│  Compressor   │  ← Aplica transformaciones según nivel
│   Engine      │    - Regex para comentarios
│ (compressor)  │    - Mapas de abreviaciones
│               │    - Análisis de imports no usados
└──────────────┘
       │
       ▼
  Texto comprimido + estadísticas
```

---

## Módulos Principales

### 1. `indexer.py` - Indexación Semántica

**Clase Principal:** `ProjectIndexer`

**Funciones Clave:**

| Método | Descripción |
|--------|-------------|
| `index_project(path)` | Indexa un proyecto completo con soporte incremental |
| `_chunk_file(filepath)` | Divide un archivo en chunks semánticos |
| `_get_file_hash(filepath)` | Calcula MD5 para detectar cambios |
| `_compute_embeddings_batch()` | Genera embeddings en batches dinámicos |
| `get_stats()` | Retorna estadísticas de indexación |

**Indexación Incremental:**
```python
# Pseudocódigo del flujo incremental
old_hashes = load_saved_hashes()
new_hashes = compute_all_hashes()

for file in all_files:
    if file.hash != old_hashes.get(file.path):
        reindex_file(file)  # Solo archivos modificados
    else:
        skip_file(file)       # Archivos sin cambios
```

**Chunking Inteligente:**
- **Python:** Detecta `def`, `class`, `import` usando regex compiladas
- **JavaScript/TypeScript:** Detecta `function`, `class`, `=>` arrow functions
- **Otros:** Divide por líneas en blanco o tamaño fijo (500 líneas)

**Optimizaciones:**
- **Batch sizing dinámico:** Calcula tamaño basado en RAM disponible
- **Memory mapping:** Para archivos >5MB usa `mmap` en lugar de cargar todo
- **FAISS IVF:** Para >10k vectores, usa IndexIVFFlat (más rápido, aproximado)

---

### 2. `retriever.py` - Recuperación de Contexto

**Clase Principal:** `ContextRetriever`

**Funciones Clave:**

| Método | Descripción |
|--------|-------------|
| `query(text, top_k=5)` | Búsqueda vectorial básica |
| `query_with_context()` | Búsqueda + enriquecimiento de contexto |
| `query_mmr()` | Búsqueda con diversidad (MMR) |
| `fuzzy_search()` | Búsqueda híbrida vector + texto |
| `load_index(path)` | Carga índice FAISS en memoria |

**Maximal Marginal Relevance (MMR):**
```python
# Fórmula MMR
# lambda = 0.5 (balance relevancia/diversidad)
# MMR = lambda * sim(query, doc) - (1-lambda) * max(sim(doc, selected))

selected = []
candidates = all_results

while len(selected) < top_k:
    best_mmr_score = -inf
    best_doc = None
    
    for doc in candidates:
        relevance = similarity(query_vector, doc.vector)
        diversity = max([similarity(doc.vector, s.vector) for s in selected]) if selected else 0
        mmr_score = 0.5 * relevance - 0.5 * diversity
        
        if mmr_score > best_mmr_score:
            best_mmr_score = mmr_score
            best_doc = doc
    
    selected.append(best_doc)
    candidates.remove(best_doc)
```

**Cross-Encoder Re-ranking:**
1. FAISS retorna top 20 candidatos
2. Cross-encoder evalúa pares `(query, document)`
3. Reordena por score del cross-encoder
4. Retorna top 5 reordenados

**Query Cache (LRU):**
```python
# Clave del cache: hash(query + top_k + filters)
# Valor: resultados + timestamp
# Evicción: LRU (Least Recently Used) cuando se alcanza max_size
```

---

### 3. `compressor.py` - Compresión de Texto

**Clase Principal:** `CavemanCompressor`

**Niveles de Compresión:**

| Nivel | Descripción | Ratio Típico |
|-------|-------------|--------------|
| `lite` | Elimina comentarios y espacios extra | 10-20% |
| `full` | + abreviaciones, contracciones | 30-40% |
| `ultra` | + elimina código muerto, imports no usados | 40-50% |
| `wenyan` | Convierte a chino clásico | 50-60% |
| `auto` | Selecciona nivel basado en tokens | variable |

**Proceso de Compresión:**
```python
def compress(text, level="auto"):
    # 1. Contar tokens originales
    original_tokens = count_tokens(text)
    
    # 2. Determinar nivel si es auto
    if level == "auto":
        if original_tokens < 1000: level = "lite"
        elif original_tokens < 5000: level = "full"
        else: level = "ultra"
    
    # 3. Aplicar transformaciones
    compressed = text
    compressed = remove_comments(compressed)
    compressed = remove_extra_whitespace(compressed)
    
    if level in ["full", "ultra"]:
        compressed = apply_abbreviations(compressed)
        compressed = apply_contractions(compressed)
    
    if level == "ultra":
        compressed = remove_dead_code(compressed)
        compressed = remove_unused_imports(compressed)
    
    # 4. Retornar con estadísticas
    compressed_tokens = count_tokens(compressed)
    ratio = 1 - (compressed_tokens / original_tokens)
    
    return compressed, {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": ratio
    }
```

---

### 4. `skills/router.py` - Enrutamiento de Skills

**Clase Principal:** `SkillRouter`

**Skills Disponibles:**

| Skill | Trigger Words | Descripción |
|-------|---------------|-------------|
| `code_search` | "find", "search", "where is" | Búsqueda de código |
| `debug` | "fix", "bug", "error", "debug" | Ayuda con debugging |
| `refactor` | "refactor", "improve", "clean" | Sugerencias de refactorización |
| `explain` | "explain", "what does", "how" | Explicación de código |
| `generate` | "create", "generate", "write" | Generación de código |
| `test` | "test", "unit test", "spec" | Generación de tests |
| `document` | "document", "docstring", "readme" | Generación de documentación |
| `review` | "review", "check", "analyze" | Revisión de código |

**Proceso de Selección:**
```python
def select_skill(query):
    # 1. Extraer palabras clave
    keywords = extract_keywords(query.lower())
    
    # 2. Calcular score para cada skill
    scores = {}
    for skill_name, skill in self.skills.items():
        score = 0
        for keyword in keywords:
            if keyword in skill.trigger_words:
                score += skill.trigger_weights[keyword]
        scores[skill_name] = score / len(keywords) if keywords else 0
    
    # 3. Normalizar a probabilidades (softmax)
    probabilities = softmax(scores)
    
    # 4. Seleccionar skill con mayor probabilidad
    best_skill = max(probabilities, key=probabilities.get)
    confidence = probabilities[best_skill]
    
    return {
        "skill": best_skill,
        "confidence": confidence,
        "all_scores": probabilities
    }
```

---

## Web UI - Funcionalidades Detalladas

### Tab 1: 📁 Index (Indexar Proyecto)

**Flujo:**
1. Usuario ingresa path del proyecto
2. Click en "Index Project"
3. Backend ejecuta `indexer.index_project(path)`
4. Retorna estadísticas:
   - `files_indexed`: Número de archivos indexados
   - `chunks_created`: Número de chunks generados
   - `files_skipped`: Archivos sin cambios (indexación incremental)
   - `files_updated`: Archivos que fueron actualizados
   - `index_time_ms`: Tiempo de indexación en milisegundos

**File Watcher (automático):**
- Se inicia después de indexar
- Monitorea cambios en archivos del proyecto
- Re-indexa automáticamente archivos modificados (debounce 2 segundos)

**Dependency Graph (automático):**
- Se construye después de indexar
- Analiza imports entre archivos
- Permite encontrar dependencias circulares

---

### Tab 2: 🔎 Query (Buscar Código)

**Flujo:**
1. Usuario ingresa query de búsqueda
2. Opcional: filtra por extensiones (ej: `.py, .js`)
3. Opcional: ajusta `top_k` (número de resultados)
4. Backend ejecuta `retriever.query_with_context()`

**Parámetros:**
- `query`: Texto de búsqueda
- `top_k`: Número de resultados (1-50, default 5)
- `filter_ext`: Lista de extensiones a incluir
- `use_mmr`: Usar Maximal Marginal Relevance (default true)

**Respuesta:**
```json
{
  "query": "authenticate user",
  "results_count": 5,
  "results": [
    {
      "filepath": "/src/auth.py",
      "start_line": 45,
      "end_line": 67,
      "content": "def authenticate_user(username, password):...",
      "similarity_score": 0.92,
      "chunk_type": "function"
    }
  ]
}
```

---

### Tab 3: 🗜️ Compress (Comprimir Texto)

**Flujo:**
1. Usuario pega texto en el textarea
2. Selecciona nivel de compresión (o deja "auto")
3. Backend ejecuta `compressor.compress(text, level)`

**Niveles:**
- **Auto:** Selecciona nivel basado en cantidad de tokens
- **Lite:** Elimina comentarios y espacios
- **Full:** + abreviaciones y contracciones
- **Ultra:** + elimina código muerto
- **Wenyan:** Convierte a chino clásico (experimental)

**Respuesta:**
```json
{
  "original_text": "...",
  "compressed_text": "...",
  "stats": {
    "original_tokens": 1500,
    "compressed_tokens": 900,
    "compression_ratio": 0.40,
    "level": "full",
    "processing_time_ms": 45
  }
}
```

---

### Tab 4: 🎯 Skills (Detección de Skill)

**Flujo:**
1. Usuario ingresa query (ej: "fix login bug")
2. Backend ejecuta `router.execute_skill(query)`
3. Retorna skill seleccionado + scores de todos los skills

**Visualización:**
- Barra de progreso para cada skill
- Skill seleccionado resaltado en verde
- Porcentaje de confianza

**Respuesta:**
```json
{
  "routing": {
    "skill": "debug",
    "confidence": 0.85,
    "all_scores": {
      "debug": 0.85,
      "code_search": 0.10,
      "explain": 0.05,
      ...
    }
  },
  "retrieved_files": [...],
  "suggested_actions": [...]
}
```

---

## Protocolo MCP

### Formato de Mensajes (JSON-RPC 2.0)

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "query",
  "params": {
    "query": "authenticate user",
    "top_k": 5
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "results": [...],
    "results_count": 5
  }
}
```

**Error:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  }
}
```

### Métodos MCP Disponibles

| Método | Descripción | Parámetros |
|--------|-------------|------------|
| `initialize` | Inicializa el servidor | - |
| `index_project` | Indexa un proyecto | `project_path`, `force_reindex` |
| `query` | Busca código | `query`, `top_k`, `filter_ext`, `use_mmr` |
| `compress` | Comprime texto | `text`, `level` |
| `select_skill` | Selecciona skill | `query` |
| `get_stats` | Obtiene estadísticas | - |
| `ping` | Health check | - |

---

## Optimizaciones Implementadas

### 1. Indexación Incremental

**Problema:** Re-indexar todo el proyecto cada vez es lento.

**Solución:**
- Guardar hash MD5 de cada archivo indexado
- Al re-indexar, comparar hashes
- Solo procesar archivos modificados

**Resultado:** Indexación de 57 archivos pasa de ~30s a ~2s (incremental).

### 2. Query Cache (LRU)

**Problema:** Queries repetidas recalculan embeddings y búsqueda FAISS.

**Solución:**
- Cache LRU con clave = hash(query + params)
- Tamaño máximo: 100 entradas
- Evicción automática (LRU)

**Resultado:** Queries repetidas son ~100x más rápidas.

### 3. Batch Sizing Dinámico

**Problema:** Batch fijo puede causar OOM o ser ineficiente.

**Solución:**
```python
available_ram = psutil.virtual_memory().available
batch_size = min(256, max(8, available_ram // (100 * 1024 * 1024)))
```

**Resultado:** Adaptación automática a la RAM disponible.

### 4. FAISS IVF para Grandes Datasets

**Problema:** IndexFlatIP es O(n), lento para >10k vectores.

**Solución:**
- Auto-detectar cuando hay >10k vectores
- Migrar a IndexIVFFlat (búsqueda aproximada O(log n))
- nlist = sqrt(n_vectors) clusters

**Resultado:** Búsqueda 10-50x más rápida en datasets grandes.

### 5. Memory Mapping

**Problema:** Archivos grandes (>5MB) consumen mucha RAM.

**Solución:**
- Usar `mmap` para archivos >5MB
- Leer solo las partes necesarias

**Resultado:** Menor uso de RAM, mejor performance.

### 6. Model Cache (LRU)

**Problema:** Cargar modelos sentence-transformers es lento (~2-5s).

**Solución:**
- Cache LRU de modelos cargados
- Clave = nombre del modelo
- Reutilización entre instancias

**Resultado:** Segunda carga es instantánea.

---

## Estructura de Archivos del Índice

```
~/.kimi_cache/indexes/
└── {project_hash}/
    ├── index.faiss          # Vectores FAISS
    ├── chunks.json          # Metadatos de chunks
    ├── file_index.json      # Hashes de archivos (incremental)
    └── config.json          # Configuración del índice
```

---

## Métricas de Performance

| Operación | Tiempo Típico | Memoria |
|-----------|---------------|---------|
| Indexar proyecto (57 archivos, 291 chunks) | ~7s (full) / ~2s (incremental) | ~500MB |
| Query (sin cache) | ~200-500ms | ~100MB |
| Query (con cache) | ~1-5ms | ~10MB |
| Compresión (1000 tokens) | ~20-50ms | ~10MB |
| Skill selection | ~5-10ms | ~5MB |

---

## Debugging y Logs

**Nivel de logging:** INFO (default)

**Logs importantes:**
```
INFO - Indexing complete in 7234ms
INFO - Files indexed: 57
INFO - Files skipped: 0
INFO - Files updated: 0
INFO - Total chunks: 291
INFO - Query cache hit rate: 0.75
INFO - FAISS search: 50 vectors, 12.3ms
```

**Para debug más detallado:**
```python
logging.basicConfig(level=logging.DEBUG)
```

---

## Extensiones Futuras

1. **Multi-project support:** Indexar múltiples proyectos simultáneamente
2. **REST API completa:** Endpoints adicionales para integración
3. **Webhooks:** Notificaciones de cambios en archivos
4. **Plugins:** Sistema de plugins para skills personalizados
5. **Distributed indexing:** Indexación distribuida para proyectos muy grandes
