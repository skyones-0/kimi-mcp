# Integración Kimi-PIMCP con Kimi-CLI

## Índice
1. [Arquitectura de Integración](#arquitectura-de-integración)
2. [Modos de Operación](#modos-de-operación)
3. [Configuración en Kimi-CLI](#configuración-en-kimi-cli)
4. [Flujo de Ejemplo Completo](#flujo-de-ejemplo-completo)
5. [Comandos y Uso](#comandos-y-uso)
6. [Troubleshooting](#troubleshooting)

---

## Arquitectura de Integración

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              KIMI-CLI                                        │
│                     (Tu interfaz de línea de comandos)                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     MCP Client (integrado)                           │    │
│  │         Lee mcp_config.json y conecta a servidores MCP               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    │ stdio (pipes)                           │
│                                    ▼                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                           KIMI-PIMCP (MCP Server)                            │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐   │
│  │   Indexer    │───▶│  Retriever   │───▶│  Compressor  │───▶│  Skills  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────┘   │
│         │                   │                   │                  │         │
│         ▼                   ▼                   ▼                  ▼         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         FAISS Vector Store                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP (opcional, solo para Web UI)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEB UI (Opcional)                                    │
│                                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  📁 Index  │  │  🔎 Query  │  │ 🗜️ Compress│  │ 🎯 Skills  │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
│                                                                              │
│  NOTA: El Web UI es INDEPENDIENTE del MCP Server.                            │
│        Sirve para pruebas y visualización, NO es necesario para Kimi-CLI.    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Modos de Operación

### Modo 1: MCP Server (stdio) - **PARA KIMI-CLI**

```bash
# Este es el modo que usa Kimi-CLI
python -m src.server
```

- **Protocolo:** JSON-RPC 2.0 sobre stdio (pipes)
- **Uso:** Integración con Kimi-CLI
- **Comunicación:** stdin/stdout
- **Web UI:** NO necesario

### Modo 2: Web UI + REST API (HTTP) - **PARA PRUEBAS**

```bash
# Este modo es SOLO para pruebas manuales
python -m src.web_ui
```

- **Protocolo:** HTTP/REST + HTML interface
- **Uso:** Pruebas manuales, debugging, visualización
- **Comunicación:** HTTP en puerto 8080
- **Kimi-CLI:** NO usa este modo

### ⚠️ IMPORTANTE

| Pregunta | Respuesta |
|----------|-----------|
| ¿Necesito `python -m src.web_ui` para Kimi-CLI? | **NO** |
| ¿Qué necesito para Kimi-CLI? | Solo `python -m src.server` |
| ¿Puedo usar ambos simultáneamente? | **SÍ**, son independientes |
| ¿El Web UI afecta al MCP Server? | **NO**, usan índices separados |

---

## Configuración en Kimi-CLI

### Paso 1: Crear/Editar `mcp_config.json`

Ubicación: `~/.config/kimi/mcp_config.json` (o donde tengas tu config)

```json
{
  "mcpServers": {
    "kimi-pimcp": {
      "command": "python",
      "args": [
        "-m",
        "src.server"
      ],
      "cwd": "/Users/jaraujo/Developer/kimi-pimcp",
      "env": {
        "PYTHONPATH": "/Users/jaraujo/Developer/kimi-pimcp",
        "KIMI_PIMCP_CACHE_DIR": "~/.kimi_cache"
      },
      "disabled": false,
      "autoApprove": ["index_project", "query", "compress", "select_skill"]
    }
  }
}
```

**Campos importantes:**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `command` | Comando para ejecutar | `"python"` |
| `args` | Argumentos del comando | `["-m", "src.server"]` |
| `cwd` | Directorio de trabajo | `"/Users/jaraujo/Developer/kimi-pimcp"` |
| `env.PYTHONPATH` | Path para imports | `"/Users/jaraujo/Developer/kimi-pimcp"` |
| `autoApprove` | Métodos auto-aprobados | `["index_project", "query", ...]` |

### Paso 2: Verificar que Kimi-CLI detecta el servidor

```bash
# En tu terminal
kimi mcp list

# Deberías ver:
# ✅ kimi-pimcp (enabled)
```

### Paso 3: Probar conexión

```bash
# En tu terminal
kimi mcp test kimi-pimcp

# Deberías ver:
# Testing connection to kimi-pimcp...
# ✅ Connection successful
# ✅ Server responded to ping
```

---

## Flujo de Ejemplo Completo

### Escenario: Trabajando en un proyecto Python

```
📁 ~/Developer/my-project/
├── src/
│   ├── auth.py          # Quiero entender la autenticación
│   ├── models.py
│   └── api.py
├── tests/
└── README.md
```

---

### Paso 1: Iniciar conversación con Kimi-CLI

```bash
# Entras al directorio de tu proyecto
cd ~/Developer/my-project

# Inicias Kimi-CLI
kimi
```

---

### Paso 2: Indexar el proyecto (automático o manual)

**Opción A: Kimi-CLI detecta el MCP y lo usa automáticamente**

```
You: @kimi-pimcp indexa este proyecto

Kimi: Voy a indexar el proyecto en ~/Developer/my-project
      [llamando a index_project]
      
      ✅ Indexación completada:
      - Archivos indexados: 12
      - Chunks creados: 48
      - Tiempo: 3.2s
```

**Opción B: Indexación automática al detectar cambios**

```
You: (simplemente haces una pregunta sobre el código)

Kimi: (detecta que el proyecto no está indexado)
      Voy a indexar el proyecto primero para darte mejores respuestas...
      [llamando a index_project automáticamente]
      
      ✅ Proyecto indexado. Ahora puedo responder tu pregunta.
```

---

### Paso 3: Hacer preguntas sobre el código

**Ejemplo 1: Buscar función específica**

```
You: ¿Dónde está la función que maneja el login de usuarios?

Kimi: Voy a buscar en el código... [llamando a query]
      
      Encontré la función en `src/auth.py`:
      
      ```python
      def authenticate_user(username: str, password: str) -> User:
          """Authenticate a user with username and password."""
          user = get_user_by_username(username)
          if not user or not verify_password(password, user.password_hash):
              raise AuthenticationError("Invalid credentials")
          return user
      ```
      
      También encontré la función `login()` en la línea 45 que usa 
      `authenticate_user()`.
```

**¿Qué pasó internamente?**

```json
// Request de Kimi-CLI al MCP
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "query",
  "params": {
    "query": "function login users authenticate",
    "top_k": 5,
    "use_mmr": true
  }
}

// Response del MCP
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "results": [
      {
        "filepath": "src/auth.py",
        "start_line": 23,
        "end_line": 29,
        "content": "def authenticate_user(...)",
        "similarity_score": 0.92
      }
    ]
  }
}
```

---

**Ejemplo 2: Pedir explicación de código complejo**

```
You: Explícame qué hace esta función: [pegas código de 100 líneas]

Kimi: Este código es bastante extenso. Voy a comprimirlo primero 
      para procesarlo más eficientemente... [llamando a compress]
      
      [llamando a select_skill]
      Detecté que necesitas una explicación. Aquí va:
      
      Esta función implementa un algoritmo de rate limiting:
      1. Verifica el token bucket (líneas 10-15)
      2. Calcula el tiempo de espera si excede (líneas 20-30)
      3. Actualiza el contador (líneas 35-40)
```

**¿Qué pasó internamente?**

```json
// 1. Detectar skill
{
  "method": "select_skill",
  "params": { "query": "Explícame qué hace esta función..." }
}
// Response: { "skill": "explain", "confidence": 0.95 }

// 2. Comprimir texto largo
{
  "method": "compress",
  "params": { 
    "text": "[código de 100 líneas]",
    "level": "lite"
  }
}
// Response: { "compressed_text": "...", "compression_ratio": 0.30 }
```

---

**Ejemplo 3: Encontrar bugs**

```
You: Hay un error en el manejo de sesiones, ayúdame a debuggear

Kimi: Voy a buscar código relacionado con sesiones... [llamando a query]
      
      [llamando a select_skill]
      Detecté que estás debuggeando. Encontré posibles problemas:
      
      En `src/auth.py:45`:
      ```python
      session = create_session(user)
      # ⚠️ Falta manejo de error si create_session falla
      ```
      
      En `src/api.py:120`:
      ```python
      session_id = request.cookies.get('session_id')
      # ⚠️ No se valida si session_id es None antes de usarlo
      ```
```

---

### Paso 4: Refactorización sugerida

```
You: Este código está muy desordenado, ¿cómo lo mejorarías?

Kimi: Voy a analizar el código... [llamando a query para obtener contexto]
      [llamando a select_skill]
      
      Sugiero estas refactorizaciones:
      
      1. **Extraer función** (src/utils.py:20-45)
         El bloque de validación se repite 3 veces.
         
      2. **Renombrar variable** (src/models.py:15)
         `data` → `user_data` para mayor claridad.
         
      3. **Eliminar código muerto** (src/api.py:80-95)
         La función `old_auth()` ya no se usa.
```

---

## Comandos y Uso

### Comandos Directos (usando @)

```bash
# Indexar proyecto
@kimi-pimcp indexa el proyecto en ~/Developer/my-project

# Buscar código
@kimi-pimcp busca "función de autenticación"

# Comprimir texto
@kimi-pimcp comprime este código: [código]

# Detectar skill
@kimi-pimcp qué skill necesito para "crear tests unitarios"
```

### Uso Implícito (Kimi decide)

```bash
# Kimi detecta automáticamente cuándo usar el MCP
You: ¿Dónde está definida la clase User?

# Kimi automáticamente:
# 1. Detecta que necesita buscar código
# 2. Llama a query() en el MCP
# 3. Retorna resultados
```

### En `kimi_config.json`

```json
{
  "mcp": {
    "servers": ["kimi-pimcp"],
    "auto_index": true,
    "index_on_change": true
  }
}
```

---

## Troubleshooting

### Problema: Kimi-CLI no detecta el servidor

```bash
# Verificar configuración
kimi mcp list

# Si no aparece, verificar mcp_config.json
cat ~/.config/kimi/mcp_config.json

# Verificar que el servidor arranca manualmente
cd ~/Developer/kimi-pimcp
source venv/bin/activate
python -m src.server

# Debería mostrar:
# {"jsonrpc": "2.0", "id": 1, "result": {"status": "initialized"}}
```

### Problema: Error "Module not found"

```bash
# Verificar PYTHONPATH
echo $PYTHONPATH

# Debería incluir: /Users/jaraujo/Developer/kimi-pimcp

# Si no, agregar a mcp_config.json:
"env": {
  "PYTHONPATH": "/Users/jaraujo/Developer/kimi-pimcp"
}
```

### Problema: Indexación muy lenta

```bash
# Verificar que es incremental (segunda vez debe ser rápida)
# Primera vez: ~7s para 57 archivos
# Segunda vez: ~2s (incremental)

# Si siempre es lento, verificar permisos
ls -la ~/.kimi_cache/indexes/

# Limpiar cache si es necesario
rm -rf ~/.kimi_cache/indexes/*
```

### Problema: Queries no encuentran resultados

```bash
# Verificar que el proyecto está indexado
@kimi-pimcp status

# Re-indexar si es necesario
@kimi-pimcp reindex

# Verificar logs del servidor
# (en otra terminal)
tail -f ~/.kimi_cache/logs/mcp.log
```

---

## Diagrama de Secuencia Completo

```
┌─────────┐     ┌──────────┐     ┌─────────────┐     ┌─────────────┐
│  User   │     │ Kimi-CLI │     │ MCP Client  │     │ MCP Server  │
└────┬────┘     └────┬─────┘     └──────┬──────┘     └──────┬──────┘
     │               │                  │                   │
     │ "¿Dónde está  │                  │                   │
     │  la función    │                  │                   │
     │  de login?"    │                  │                   │
     │──────────────▶│                  │                   │
     │               │                  │                   │
     │               │ Detecta necesidad│                   │
     │               │ de búsqueda      │                   │
     │               │                  │                   │
     │               │─────────────────▶│                   │
     │               │  query()         │                   │
     │               │                  │                   │
     │               │                  │ JSON-RPC          │
     │               │                  │──────────────────▶│
     │               │                  │  {"method":"query"}│
     │               │                  │                   │
     │               │                  │                   │ Embedding
     │               │                  │                   │ FAISS search
     │               │                  │                   │ MMR
     │               │                  │                   │
     │               │                  │ JSON-RPC          │
     │               │                  │◀──────────────────│
     │               │                  │  {"results":[...]} │
     │               │                  │                   │
     │               │◀─────────────────│                   │
     │               │  Resultados      │                   │
     │               │                  │                   │
     │ "Encontré en  │                  │                   │
     │  auth.py:23..."│                  │                   │
     │◀──────────────│                  │                   │
     │               │                  │                   │
```

---

## Resumen Rápido

| ¿Quieres...? | Comando/Acción | Necesita Web UI? |
|--------------|----------------|------------------|
| Usar con Kimi-CLI | Configurar `mcp_config.json` | **NO** |
| Indexar proyecto | `@kimi-pimcp indexa` o automático | **NO** |
| Buscar código | Hacer pregunta sobre el código | **NO** |
| Probar funcionalidad | `python -m src.web_ui` | **SÍ** (solo para pruebas) |
| Ver estadísticas | Abrir http://localhost:8080 | **SÍ** |

---

## Comandos de Inicio Rápido

```bash
# 1. Para usar con Kimi-CLI (MCP Server)
cd ~/Developer/kimi-pimcp
source venv/bin/activate
# Kimi-CLI lo inicia automáticamente, o manualmente:
python -m src.server

# 2. Para pruebas manuales (Web UI)
cd ~/Developer/kimi-pimcp
source venv/bin/activate
python -m src.web_ui
# Abrir navegador en http://localhost:8080
```
