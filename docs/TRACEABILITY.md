# Trazabilidad en Kimi-PIMCP

## ¿Qué es la Trazabilidad?

La trazabilidad en Kimi-PIMCP te permite:
1. **Generar resúmenes automáticos** de la actividad del proyecto
2. **Documentar qué se hizo** sin usar tokens de LLM
3. **Analizar cambios** usando Git de forma inteligente
4. **Guardar reportes** en Markdown para referencia futura

---

## ¿Cómo funciona? (Sin Tokens)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANÁLISIS INTELIGENTE SIN LLM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Git History                                                                │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. EXTRACCIÓN DE DATOS                                              │   │
│  │     - git log (commits, autores, fechas)                             │   │
│  │     - git diff (líneas añadidas/eliminadas)                          │   │
│  │     - git show (archivos modificados)                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. ANÁLISIS HEURÍSTICO (sin LLM)                                    │   │
│  │                                                                      │   │
│  │  Keywords de mensajes de commit:                                     │   │
│  │  - "add", "implement", "create" → feature ✨                         │   │
│  │  - "fix", "bug", "resolve" → bugfix 🐛                               │   │
│  │  - "refactor", "clean", "improve" → refactor ♻️                      │   │
│  │  - "test", "spec", "coverage" → test 🧪                              │   │
│  │  - "doc", "readme", "comment" → docs 📚                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. GENERACIÓN DE RESUMEN                                            │   │
│  │     - Contar commits por tipo                                        │   │
│  │     - Sumar líneas añadidas/eliminadas                               │   │
│  │     - Identificar archivos nuevos/modificados/eliminados             │   │
│  │     - Crear frases usando plantillas                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. GUARDAR EN MARKDOWN                                              │   │
│  │     - daily_report_2024-01-15.md                                     │   │
│  │     - weekly_report_2024-01-08.md                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Herramientas MCP Disponibles

### 1. `generate_daily_report`

Genera un reporte diario basado en commits de Git.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp generate_daily_report

Kimi: Generando reporte diario...
      
      📊 Reporte del 2024-01-15
      - Commits: 8
      - Archivos cambiados: 12
      - Líneas: +450/-120
      
      ✨ feat(auth): implementar login con JWT
      🐛 fix(api): corregir error en endpoint /users
      ♻️ refactor(models): simplificar relaciones
      
      Reporte guardado en: .kimi_pimcp/traceability/daily_report_2024-01-15.md
```

**Parámetros:**
- `date` (opcional): Fecha en formato YYYY-MM-DD (default: hoy)

---

### 2. `generate_weekly_report`

Genera un reporte semanal agregando datos de 7 días.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp generate_weekly_report

Kimi: Generando reporte semanal...
      
      📈 Resumen Semanal (2024-01-08 al 2024-01-14)
      - Total commits: 35
      - Archivos cambiados: 28
      - Total líneas: +2,100/-890
      - Net change: +1,210 líneas
      
      Días más activos:
      - Martes: 12 commits
      - Jueves: 10 commits
      
      Archivos más modificados:
      - src/auth.py (5 cambios)
      - src/api.py (4 cambios)
      - tests/test_auth.py (3 cambios)
```

**Parámetros:**
- `week_start` (opcional): Fecha de inicio de semana (default: lunes actual)

---

### 3. `get_recent_activity`

Obtiene un resumen rápido de los últimos N días.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp get_recent_activity {"days": 3}

Kimi: 📅 Actividad de los últimos 3 días (15 commits)
      
      2024-01-15 (5 commits):
      - ✨ feat(auth): implementar login con JWT
      - 🐛 fix(api): corregir error en endpoint /users
      - ... y 3 más
      
      2024-01-14 (7 commits):
      - ♻️ refactor(models): simplificar relaciones
      - 🧪 test(auth): agregar tests para login
      - ... y 5 más
      
      2024-01-13 (3 commits):
      - 📚 docs(readme): actualizar instrucciones
      - ⚙️ config(deps): actualizar dependencias
      - ... y 1 más
```

**Parámetros:**
- `days` (opcional): Número de días a incluir (default: 7)

---

### 4. `list_traceability_reports`

Lista todos los reportes generados.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp list_traceability_reports

Kimi: 📁 Reportes disponibles en .kimi_pimcp/traceability/:
      
      - daily_report_2024-01-15.md
      - daily_report_2024-01-14.md
      - daily_report_2024-01-13.md
      - weekly_report_2024-01-08.md
      
      Total: 4 reportes
```

---

### 5. `get_traceability_report`

Obtiene el contenido completo de un reporte específico.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp get_traceability_report {"report_name": "daily_report_2024-01-15.md"}

Kimi: Contenido del reporte:
      
      # Daily Report - 2024-01-15
      
      ## Summary
      High activity with 8 commits including 3 features, 2 bugfixes, 
      1 refactor, 2 tests. 2 new files added. (+450/-120) lines changed.
      
      ## Statistics
      - **Commits:** 8
      - **Files Changed:** 12
      - **Additions:** +450
      - **Deletions:** -120
      
      ## Key Changes
      - ✨ feat(auth): implementar login con JWT
      - 🐛 fix(api): corregir error en endpoint /users
      - ♻️ refactor(models): simplificar relaciones
      - 🧪 test(auth): agregar tests para login
      - 🧪 test(api): tests para endpoint /users
      
      ...
```

**Parámetros:**
- `report_name` (requerido): Nombre del archivo del reporte

---

### 6. `start_traceability_session`

Inicia una sesión de trazabilidad para trackear actividad en tiempo real.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp start_traceability_session

Kimi: ✅ Sesión de trazabilidad iniciada: abc123def456
      
      Las queries y archivos accedidos serán trackeados.
      Usa `end_traceability_session` para finalizar.
```

---

### 7. `end_traceability_session`

Finaliza la sesión de trazabilidad y genera un resumen.

**Uso desde Kimi-CLI:**
```
You: @kimi-pimcp end_traceability_session

Kimi: ✅ Sesión de trazabilidad finalizada: abc123def456
      
      ## Session Summary (abc123def456)
      **Duration:** 45.3 minutes
      **Files touched:** 8
      **Queries made:** 12
      
      ### Queries Made
      1. "función de autenticación"
      2. "cómo funciona el login"
      3. "middleware de auth"
      ...
      
      ### Files Accessed
      - `src/auth.py`
      - `src/middleware/auth.py`
      - `src/models/user.py`
      ...
```

**Parámetros:**
- `generate_summary` (opcional): Si generar resumen (default: true)

---

## Flujo de Uso Típico

### Escenario: Documentar el trabajo del día

```
# 1. Al empezar a trabajar
You: @kimi-pimcp start_traceability_session

# 2. Trabajas normalmente, haciendo preguntas...
You: ¿Dónde está la función de login?
You: Explícame el middleware de autenticación
You: Busca ejemplos de JWT

# 3. Al finalizar
You: @kimi-pimcp end_traceability_session

# 4. Generar reporte del día
You: @kimi-pimcp generate_daily_report

# 5. Ver reporte semanal
You: @kimi-pimcp generate_weekly_report
```

---

## Estructura de Reportes

### Ubicación

```
~/Developer/my-project/
├── .kimi_pimcp/
│   └── traceability/
│       ├── daily_report_2024-01-15.md
│       ├── daily_report_2024-01-14.md
│       ├── weekly_report_2024-01-08.md
│       └── sessions.json
```

### Formato de Reporte Diario

```markdown
# Daily Report - 2024-01-15

## Summary
High activity with 8 commits including 3 features, 2 bugfixes, 
1 refactor, 2 tests. 2 new files added. (+450/-120) lines changed.

## Statistics
- **Commits:** 8
- **Files Changed:** 12
- **Additions:** +450
- **Deletions:** -120

## Key Changes
- ✨ feat(auth): implementar login con JWT
- 🐛 fix(api): corregir error en endpoint /users
- ♻️ refactor(models): simplificar relaciones

## Commits
### `a1b2c3d4` - feat(auth): implementar login con JWT
- **Author:** Juan Pérez
- **Type:** feature
- **Changes:** 3 files (+120/-20)

...

---
*Generated by Kimi-PIMCP Traceability on 2024-01-15 18:30:45*
```

---

## Ventajas vs. LLM

| Aspecto | Con LLM | Sin LLM (Kimi-PIMCP) |
|---------|---------|---------------------|
| **Costo** | $$$ (tokens) | FREE |
| **Velocidad** | 2-5 segundos | <100ms |
| **Determinismo** | Variable | Consistente |
| **Privacidad** | Datos a terceros | Local solo |
| **Offline** | ❌ No | ✅ Sí |
| **Personalización** | Limitada | Completa |

---

## Categorización de Commits

El sistema usa **keywords** para categorizar commits:

| Tipo | Keywords | Emoji |
|------|----------|-------|
| **feature** | add, implement, create, new, feature, introduce | ✨ |
| **bugfix** | fix, bug, issue, resolve, correct, patch | 🐛 |
| **refactor** | refactor, clean, improve, optimize, restructure | ♻️ |
| **test** | test, spec, coverage, unit, e2e | 🧪 |
| **docs** | doc, readme, comment, changelog, license | 📚 |
| **config** | config, setup, dependency, package, requirements | ⚙️ |
| **other** | (default) | 📝 |

### Ejemplos

```
"feat(auth): add JWT authentication" → ✨ feature
"fix(api): resolve null pointer exception" → 🐛 bugfix
"refactor(models): simplify relationships" → ♻️ refactor
"test(auth): add unit tests" → 🧪 test
"docs(readme): update instructions" → 📚 docs
"chore(deps): update packages" → ⚙️ config
```

---

## Integración con Git

### Requisitos

- El proyecto debe ser un repositorio Git
- Git debe estar instalado y disponible en PATH

### Datos Extraídos

1. **Commits:** hash, autor, fecha, mensaje
2. **Estadísticas:** archivos cambiados, líneas +/-
3. **Archivos:** nuevos, modificados, eliminados
4. **Historial:** cambios por archivo (blame)

---

## Troubleshooting

### "No Git repository found"

```bash
# Verificar que es un repo Git
cd ~/Developer/my-project
git status

# Si no es repo, inicializar:
git init
git add .
git commit -m "Initial commit"
```

### "No commits found"

```bash
# Verificar commits
git log --oneline -10

# Si no hay commits, crear uno:
git add .
git commit -m "feat: initial implementation"
```

### Reportes vacíos

- Verifica que hayas hecho commits en la fecha solicitada
- Verifica la zona horaria (los reportes usan fechas locales)

---

## Ejemplo Completo de Integración

```python
# En tu código Python (si quieres usarlo programáticamente)
from traceability import TraceabilityAnalyzer

# Crear analyzer
analyzer = TraceabilityAnalyzer("/path/to/project")

# Generar reporte diario
report = analyzer.generate_daily_report("2024-01-15")
print(f"Commits: {len(report.commits)}")
print(f"Summary: {report.summary}")

# Generar reporte semanal
weekly = analyzer.generate_weekly_report("2024-01-08")

# Obtener resumen rápido
summary = analyzer.get_traceability_summary(days=7)
print(summary)
```

---

## Conclusión

La trazabilidad en Kimi-PIMCP te permite:

1. ✅ **Documentar automáticamente** sin costo de tokens
2. ✅ **Analizar patrones** de desarrollo
3. ✅ **Generar reportes** para stakeholders
4. ✅ **Trackear sesiones** de trabajo
5. ✅ **Mantener historial** local y privado

Todo esto de forma **rápida, gratuita y privada**.
