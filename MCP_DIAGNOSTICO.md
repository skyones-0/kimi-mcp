# 🔍 Diagnóstico Kimi-PIMCP

## ✅ Estado Actual

### MCP Server (Kimi-CLI)
- **Estado:** FUNCIONANDO CORRECTAMENTE ✅
- **Configuración:** `/Users/jaraujo/.kimi/mcp.json`
- **Herramientas disponibles:** 21
- **Conexión:** Activa

### Web UI
- **Estado:** FUNCIONANDO CORRECTAMENTE ✅
- **URL:** http://localhost:8080
- **Endpoint de actividad MCP:** `/mcp/activity`

### Activity Monitor
- **Estado:** FUNCIONANDO CORRECTAMENTE ✅
- **Archivo:** `~/.kimi_cache/activity.json`
- **Entradas actuales:** 42
- **Fuentes:** mcp_server (42)

---

## 🎯 Problema Encontrado: Confusión Web UI vs MCP Server

### Explicación del Flujo de Datos

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Kimi-CLI      │────▶│   MCP Server     │────▶│  activity.json  │
│   (Terminal)    │◄────│   (src/server.py)│◄────│  (en disco)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                              ┌─────────────────────────┘
                              ▼
                       ┌──────────────────┐
                       │   Web UI         │
                       │   (src/web_ui.py)│
                       └──────────────────┘
```

### Cómo Funciona

1. **Cuando usas Kimi-CLI:**
   - Kimi-CLI envía requests al MCP Server vía JSON-RPC sobre stdio
   - El MCP Server guarda la actividad en `~/.kimi_cache/activity.json`
   - ✅ **Esta actividad NO aparece automáticamente en el Web UI**

2. **Cuando usas el Web UI:**
   - El Web UI tiene su propio servidor FastAPI separado
   - Las acciones desde el navegador se registran en memoria
   - La pestaña "Logs" tiene DOS secciones:
     - **MCP Server Activity:** Muestra la actividad del MCP Server (lee de `activity.json`)
     - **Web UI Internal Logs:** Muestra solo las acciones del Web UI

3. **Para ver la actividad del MCP Server en el Web UI:**
   - Abre el Web UI: http://localhost:8080
   - Ve a la pestaña "📋 Logs"
   - La sección "MCP Server Activity" muestra la actividad de Kimi-CLI
   - Se actualiza automáticamente cada 2 segundos

---

## 🚀 Cómo Usar Correctamente

### 1. Usar con Kimi-CLI (MCP Server)

```bash
# En cualquier directorio de proyecto
kimi

# Dentro de Kimi-CLI, el MCP se activa automáticamente
# O puedes llamar herramientas manualmente:
@kimi-pimcp inicializa el índice para este proyecto
@kimi-pimcp busca "función de autenticación"
```

### 2. Ver la Actividad en el Web UI

```bash
# Terminal 1: Iniciar Web UI
cd ~/Developer/kimi-pimcp
source venv/bin/activate
python -m src.web_ui

# Abrir navegador en http://localhost:8080
# Ir a la pestaña "📋 Logs"
# Ver la sección "MCP Server Activity"
```

### 3. Comandos de Diagnóstico

```bash
# Verificar que el MCP está configurado
kimi mcp list

# Probar conexión al MCP
kimi mcp test kimi-pimcp

# Ver actividad reciente
cat ~/.kimi_cache/activity.json | jq '.entries[-5:]'

# Ver estadísticas
curl http://localhost:8080/mcp/activity/stats
```

---

## 📊 Estructura de Logs

### MCP Server Activity (en `activity.json`)

```json
{
  "timestamp": "2026-04-12T08:00:00",
  "type": "mcp_request|mcp_response|tool_call|mcp_error",
  "source": "mcp_server",
  "method": "tools/call",
  "params": { "name": "query_context", "arguments": {...} },
  "duration_ms": 150
}
```

### Web UI Internal Logs (en memoria)

```json
{
  "timestamp": "08:00:00",
  "type": "request|response|action|error|info",
  "method": "POST",
  "endpoint": "/index",
  "details": "Indexing project...",
  "status": "success|error"
}
```

---

## 🔧 Mejoras Implementadas

1. **Activity Monitor compartido:** El MCP Server y Web UI usan el mismo archivo JSON para actividad
2. **Polling automático:** El Web UI actualiza la actividad del MCP cada 2 segundos
3. **Dataset de skills:** El router de skills tiene datos de entrenamiento en `data/datasets/skill_queries.json`

---

## ❓ Preguntas Frecuentes

**Q: ¿Por qué no veo actividad en el Web UI cuando uso Kimi-CLI?**
A: Asegúrate de:
1. Tener el Web UI corriendo (`python -m src.web_ui`)
2. Ir a la pestaña "📋 Logs"
3. Esperar unos segundos (se actualiza cada 2 segundos)

**Q: ¿El Web UI es necesario para usar Kimi-CLI?**
A: No. El Web UI es solo para visualización. Kimi-CLI funciona independientemente.

**Q: ¿Por qué hay dos loggers separados?**
A: Porque el MCP Server y el Web UI son procesos independientes. El MCP Server guarda en archivo para persistencia, el Web UI usa memoria para velocidad.

---

## 📝 Verificación Rápida

Ejecuta estos comandos para verificar que todo funciona:

```bash
# 1. MCP está configurado
kimi mcp list | grep kimi-pimcp

# 2. MCP responde
kimi mcp test kimi-pimcp

# 3. Hay actividad guardada
ls -la ~/.kimi_cache/activity.json

# 4. Web UI puede leer la actividad
curl -s http://localhost:8080/mcp/activity?limit=1 | jq '.stats.total_entries'
```
