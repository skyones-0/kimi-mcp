# 🚀 Guía Completa de Kimi-PIMCP MCP

Guía práctica para usar tu MCP (Model Context Protocol) con Kimi-CLI y maximizar tu productividad.

---

## 📋 Índice

1. [Instalación Rápida](#instalación-rápida)
2. [Comandos Disponibles](#comandos-disponibles)
3. [Uso en Kimi-CLI](#uso-en-kimi-cli)
4. [Ejemplos Prácticos](#ejemplos-prácticos)
5. [Casos de Uso](#casos-de-uso)
6. [Troubleshooting](#troubleshooting)

---

## ⚡ Instalación Rápida

### 1. Verificar Instalación

```bash
# Verificar que Kimi-CLI detecta el MCP
kimi mcp list

# Deberías ver:
# ✅ kimi-pimcp (enabled)
```

### 2. Probar Conexión

```bash
kimi mcp test kimi-pimcp

# Deberías ver:
# Testing connection to 'kimi-pimcp'...
# ✓ Connected to 'kimi-pimcp'
#   Available tools: 21
```

### 3. Verificar Web UI (Opcional)

```bash
cd ~/Developer/kimi-pimcp
source venv/bin/activate
python -m src.web_ui

# Abrir navegador en http://localhost:8080
```

---

## 🛠️ Comandos Disponibles

### 📁 Indexación

| Comando | Descripción | Uso |
|---------|-------------|-----|
| `initialize_index` | Indexa un proyecto para búsqueda semántica | `@kimi-pimcp indexa este proyecto` |
| `list_projects` | Lista proyectos indexados | `@kimi-pimcp lista proyectos` |
| `switch_project` | Cambia entre proyectos | `@kimi-pimcp cambia al proyecto /path/to/project` |
| `clear_cache` | Borra todos los índices | `@kimi-pimcp limpia caché` |

### 🔍 Búsqueda y Análisis

| Comando | Descripción | Uso |
|---------|-------------|-----|
| `query_context` | Busca código por significado | `@kimi-pimcp busca "función de autenticación"` |
| `select_skill` | Detecta tipo de ayuda necesaria | `@kimi-pimcp qué skill necesito para "debuggear"` |
| `get_dependencies` | Muestra dependencias de archivo | `@kimi-pimcp dependencias de src/auth.py` |
| `find_similar_code` | Encuentra código duplicado | `@kimi-pimcp código similar en src/utils.py` |

### 🗜️ Compresión

| Comando | Descripción | Uso |
|---------|-------------|-----|
| `compress_output` | Comprime texto (ahorra tokens) | `@kimi-pimcp comprime este texto` |

### 📊 Análisis y Reportes

| Comando | Descripción | Uso |
|---------|-------------|-----|
| `summarize_chunk` | Resume bloque de código | `@kimi-pimcp resume este código` |
| `get_stats` | Estadísticas del sistema | `@kimi-pimcp muestra estadísticas` |
| `get_query_history` | Historial de búsquedas | `@kimi-pimcp historial de queries` |

### 📈 Git / Traceability

| Comando | Descripción | Uso |
|---------|-------------|-----|
| `generate_daily_report` | Reporte diario Git | `@kimi-pimcp reporte diario` |
| `generate_weekly_report` | Reporte semanal Git | `@kimi-pimcp reporte semanal` |
| `get_recent_activity` | Actividad reciente Git | `@kimi-pimcp actividad reciente` |
| `start_traceability_session` | Inicia sesión tracking | `@kimi-pimcp inicia sesión` |
| `end_traceability_session` | Termina sesión tracking | `@kimi-pimcp termina sesión` |

---

## 💻 Uso en Kimi-CLI

### Modo 1: Automático (Recomendado)

Simplemente haz preguntas sobre tu código. Kimi detectará automáticamente cuándo usar el MCP:

```
You: cómo funciona la autenticación

Kimi: [detecta que necesita buscar código]
      [llama automáticamente a query_context]
      [retorna resultados del MCP]
```

### Modo 2: Forzar uso del MCP con @

Para asegurar que se use el MCP:

```
@kimi-pimcp busca "función de autenticación"
@kimi-pimcp indexa este proyecto
@kimi-pimcp muestra estadísticas
```

### Modo 3: Desde el Asistente (Como ahora)

Puedo llamar directamente las herramientas:
- `query_context(query="...", top_k=5)`
- `initialize_index(project_path="...")`
- `select_skill(query="...")`

---

## 🎯 Ejemplos Prácticos

### Ejemplo 1: Encontrar una función

**Tú:**
```
cómo se hace la autenticación de usuarios
```

**Kimi responde:**
```
Encontré la función en `src/auth.py:23`:

```python
def authenticate_user(username: str, password: str) -> User:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials")
    return user
```

También encontré `login()` en línea 45 que usa esta función.
```

### Ejemplo 2: Debuggear un error

**Tú:**
```
tengo un error 401 en el login, ayúdame
```

**Kimi responde:**
```
[Detecta skill: debugger]
[Buscando código relacionado con autenticación...]

Encontré posibles problemas:

⚠️ En `src/auth.py:45`:
```python
session = create_session(user)
# Falta manejo de error si create_session falla
```

⚠️ En `src/api.py:120`:
```python
session_id = request.cookies.get('session_id')
# No se valida si session_id es None
```
```

### Ejemplo 3: Refactorizar código

**Tú:**
```
este código está muy desordenado, cómo lo mejoro
```

**Kimi responde:**
```
[Analizando dependencias...]
[Buscando código duplicado...]

Sugerencias:

1. **Extraer función** (src/utils.py:20-45)
   El bloque de validación se repite 3 veces.

2. **Renombrar variable** (src/models.py:15)
   `data` → `user_data` para mayor claridad.

3. **Eliminar código muerto** (src/api.py:80-95)
   La función `old_auth()` ya no se usa.
```

### Ejemplo 4: Comprimir texto largo

**Tú:**
```
@kimi-pimcp comprime este código: [pega 100 líneas de código]
```

**Kimi responde:**
```
Original: 250 tokens
Comprimido: 175 tokens (30% reducción)

```python
def process_data(data):
    # Valida input
    if not data: return None
    
    # Procesa items
    results = [transform(item) for item in data if item.valid]
    
    # Guarda resultados
    return save_to_db(results)
```
```

---

## 🚀 Casos de Uso

### Caso 1: Onboarding en Proyecto Nuevo

```bash
# 1. Indexar proyecto
@kimi-pimcp indexa el proyecto en ~/Developer/nuevo-proyecto

# 2. Explorar arquitectura
@kimi-pimcp busca "estructura del proyecto"
@kimi-pimcp dependencias de src/main.py

# 3. Encontrar ejemplos
@kimi-pimcp busca "cómo se crea un usuario"
```

### Caso 2: Debuggear Producción

```bash
# 1. Buscar código relacionado con el error
@kimi-pimcp busca "manejo de errores 500"

# 2. Ver dependencias afectadas
@kimi-pimcp dependencias de src/error_handler.py

# 3. Encontrar código similar que funcione
@kimi-pimcp código similar en src/utils.py
```

### Caso 3: Code Review

```bash
# 1. Resumir cambios
@kimi-pimcp reporte diario

# 2. Detectar duplicados
@kimi-pimcp código similar en src/components/

# 3. Ver estadísticas
@kimi-pimcp muestra estadísticas
```

### Caso 4: Optimizar Prompts

```bash
# Comprimir contexto antes de enviar a LLM
@kimi-pimcp comprime este contexto: [texto largo]
```

---

## ⚙️ Configuración Avanzada

### Configurar mcp_config.json

Ubicación: `~/.config/kimi/mcp_config.json` o `~/.kimi/mcp.json`

```json
{
  "mcpServers": {
    "kimi-pimcp": {
      "command": "/Users/jaraujo/Developer/kimi-pimcp/venv/bin/python",
      "args": [
        "/Users/jaraujo/Developer/kimi-pimcp/src/server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/jaraujo/Developer/kimi-pimcp",
        "KIMI_PIMCP_CACHE_DIR": "/Users/jaraujo/.kimi_cache",
        "KIMI_PIMCP_LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "autoApprove": [
        "initialize_index",
        "query_context",
        "select_skill",
        "compress_output",
        "get_stats"
      ]
    }
  }
}
```

### Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `KIMI_PIMCP_CACHE_DIR` | Directorio de caché | `~/.kimi_cache` |
| `KIMI_PIMCP_LOG_LEVEL` | Nivel de logging | `INFO` |
| `PYTHONPATH` | Path para imports | `/Users/jaraujo/Developer/kimi-pimcp` |

---

## 🔧 Troubleshooting

### Problema: Kimi no detecta el MCP

```bash
# Verificar configuración
kimi mcp list

# Si no aparece, verificar archivo de config
cat ~/.kimi/mcp.json

# Verificar que el servidor arranca
source venv/bin/activate
python -m src.server
```

### Problema: "No project indexed"

```bash
# Indexar manualmente
@kimi-pimcp indexa este proyecto

# O dejar que Kimi lo haga automáticamente:
cómo funciona X  # Kimi detectará que necesita indexar
```

### Problema: Búsquedas sin resultados

```bash
# Verificar que el proyecto está indexado
@kimi-pimcp muestra estadísticas

# Re-indexar si es necesario
@kimi-pimcp indexa este proyecto (force_reindex=true)

# Limpiar caché y reintentar
@kimi-pimcp limpia caché
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
# Primera indexación: normal que sea lenta (~7s para 50 archivos)
# Segunda indexación: debería ser rápida (~2s, incremental)

# Si siempre es lenta, verificar:
ls -la ~/.kimi_cache/indexes/

# Limpiar e re-indexar
rm -rf ~/.kimi_cache/indexes/*
@kimi-pimcp indexa este proyecto
```

---

## 📊 Monitoreo con Web UI

### Iniciar Web UI

```bash
cd ~/Developer/kimi-pimcp
source venv/bin/activate
python -m src.web_ui
```

### URL: http://localhost:8080

**Pestañas disponibles:**

1. **📁 Index** - Indexar proyectos, ver proyectos disponibles
2. **🔎 Query** - Buscar código directamente
3. **🗜️ Compress** - Comprimir texto
4. **🎯 Skills** - Detectar skills
5. **📋 Logs** - Ver actividad del MCP Server en tiempo real

### Estadísticas en Vivo

El Web UI muestra:
- **MCP Server Status:** Requests, tool calls, errores
- **Index Statistics:** Archivos indexados, chunks, proyectos
- **MCP Activity Monitor:** Logs en tiempo real de Kimi-CLI

---

## 💡 Tips Pro

### 1. Usa `top_k` para más resultados

```
@kimi-pimcp busca "autenticación" con top_k=10
```

### 2. Filtra por extensión

```
@kimi-pimcp busca "función" solo en archivos .py
```

### 3. Re-indexa después de cambios grandes

```
@kimi-pimcp indexa este proyecto (force_reindex=true)
```

### 4. Combina herramientas

```
@kimi-pimcp qué skill necesito para "debuggear error"
@kimi-pimcp busca "código relacionado con autenticación"
@kimi-pimcp dependencias de src/auth.py
```

### 5. Usa el historial

```
@kimi-pimcp historial de queries
```

---

## 📈 Flujo de Trabajo Recomendado

### Diario

1. **Inicia Kimi-CLI** en tu proyecto
2. **Indexa** si es primera vez (o hay cambios grandes)
3. **Pregunta normalmente** sobre tu código
4. **Deja que Kimi use el MCP** automáticamente

### Semanal

1. **Revisa estadísticas:** `@kimi-pimcp muestra estadísticas`
2. **Genera reporte:** `@kimi-pimcp reporte semanal`
3. **Verifica dependencias:** `@kimi-pimcp dependencias de archivos clave`
4. **Limpia si es necesario:** `@kimi-pimcp limpia caché`

### Mensual

1. **Re-indexa todo:** `@kimi-pimcp indexa este proyecto (force_reindex=true)`
2. **Revisa Web UI:** http://localhost:8080
3. **Exporta índices:** `@kimi-pimcp exporta índice`

---

## 🎓 Aprende Más

- **Documentación completa:** `docs/KIMI_CLI_INTEGRATION.md`
- **Documentación interna:** `docs/INTERNALS.md`
- **Web UI:** Abre http://localhost:8080 después de iniciar el servidor

---

## 🆘 Soporte

Si tienes problemas:

1. Verifica que el MCP está activo: `kimi mcp list`
2. Prueba conexión: `kimi mcp test kimi-pimcp`
3. Revisa logs en Web UI → pestaña "📋 Logs"
4. Verifica configuración en `~/.kimi/mcp.json`

---

**¡Listo para usar tu MCP!** 🚀

Prueba ahora: `cómo funciona el indexer en mi proyecto`
