# Plan: Frontend Dashboard para Claude-Tasks / Eigen-Squared Pipeline

## Context

Actualmente, monitorear el pipeline autónomo de eigen-squared requiere ejecutar comandos `curl` manualmente contra la API REST de claude-tasks (`$CLAUDE_TASKS_API`). No existe interfaz visual para: ver las tareas en ejecución, leer sus outputs, crear nuevas tareas, o entender en qué punto del pipeline de 7 etapas se encuentra la ejecución. Este frontend resuelve eso.

---

## Tech Stack

- **Vite + React + TypeScript** - SPA ligera, sin SSR (es herramienta de desarrollo)
- **Tailwind CSS** - styling rápido sin dependencia de component library
- **react-router-dom** - hash routing (`#/tasks`, `#/tasks/:id`, etc.)
- **Sin backend adicional** - el proxy de Vite dev server maneja CORS hacia claude-tasks

---

## Arquitectura

```
Browser (SPA)  →  Vite Dev Server (proxy /api → localhost:8080)  →  claude-tasks API
```

- En desarrollo: `vite.config.ts` proxy `/api` → `$CLAUDE_TASKS_API || http://localhost:8080`
- En producción: servir estáticos desde el mismo host o configurar CORS en claude-tasks

---

## API de claude-tasks (contrato confirmado desde código fuente)

Fuente: https://github.com/kylemclaren/claude-tasks

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/api/v1/health` | GET | Health check → `{status, version}` |
| `/api/v1/tasks` | GET | Listar tareas → `{tasks[], total}` |
| `/api/v1/tasks` | POST | Crear tarea (201) |
| `/api/v1/tasks/{id}` | GET | Detalle de tarea |
| `/api/v1/tasks/{id}` | PUT | Actualizar tarea |
| `/api/v1/tasks/{id}` | DELETE | Eliminar tarea |
| `/api/v1/tasks/{id}/toggle` | POST | Toggle enabled/disabled |
| `/api/v1/tasks/{id}/run` | POST | Ejecutar ahora (202 fire-and-forget) |
| `/api/v1/tasks/{id}/runs` | GET | Historial de runs → `{runs[], total}` |
| `/api/v1/tasks/{id}/runs/latest` | GET | Último run |
| `/api/v1/settings` | GET/PUT | Leer/actualizar settings (usage_threshold) |
| `/api/v1/usage` | GET | Uso de API Anthropic |

**Tipos confirmados:**

```typescript
// Request
interface TaskRequest {
  name: string;
  prompt: string;
  cron_expr: string;           // "" para one-off
  scheduled_at?: string;       // ISO 8601
  working_dir: string;
  discord_webhook?: string;
  slack_webhook?: string;
  enabled: boolean;
}

// Response
interface TaskResponse extends TaskRequest {
  id: number;
  is_one_off: boolean;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
  last_run_status?: string;    // "completed" | "failed" | "running"
}

interface TaskRunResponse {
  id: number;
  task_id: number;
  started_at: string;
  ended_at?: string;
  status: "pending" | "running" | "completed" | "failed";
  output: string;              // vacío mientras corre, completo al finalizar
  error?: string;
  duration_ms?: number;
}
```

> **Limitación conocida:** El output se escribe completo al finalizar la tarea (batch, no streaming).
> Mientras `status: "running"`, el campo `output` está vacío. El Output Viewer mostrará
> un indicador de "Running..." y el output completo al completar.

---

## Estructura de directorios

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts                    # Fetch wrapper con base URL configurable
      types.ts                     # Tipos TS para respuestas de API
    hooks/
      usePolling.ts                # Hook genérico de polling con AbortController
      useTasks.ts                  # GET /api/v1/tasks (polling cada 5s)
      useTaskDetail.ts             # GET /api/v1/tasks/<id> + /runs/latest
      useHealth.ts                 # GET /api/v1/health
    components/
      layout/
        Header.tsx                 # Título, health indicator, API URL
        Sidebar.tsx                # Navegación
      pipeline/
        PipelineFlow.tsx           # Diagrama visual de las 7 etapas
        StageNode.tsx              # Nodo individual con estado
      tasks/
        TaskList.tsx               # Tabla filtrable/sorteable
        TaskDetail.tsx             # Vista completa con metadata
        TaskOutputViewer.tsx       # Output en monospace, auto-scroll
        TaskStatusBadge.tsx        # Badge de estado coloreado
      forms/
        CreateTaskForm.tsx         # Formulario libre
        PipelineQuickLaunch.tsx    # Botones preset por etapa del pipeline
      common/
        JsonViewer.tsx             # JSON colapsable
        TimeAgo.tsx                # Tiempo relativo
    pages/
      DashboardPage.tsx            # Pipeline flow + tareas recientes + health
      TaskListPage.tsx             # Lista completa con filtros
      TaskDetailPage.tsx           # Tarea individual + output viewer
      CreateTaskPage.tsx           # Formulario de creación
    lib/
      pipeline.ts                  # Definiciones de etapas, orden, relaciones
      formatters.ts                # Formato de fechas, limpieza de output
    styles/
      globals.css                  # Directivas Tailwind
```

---

## Vistas principales

### 1. Dashboard (`/`)
- **Health bar**: punto verde/rojo de conectividad con claude-tasks API
- **Pipeline Flow**: diagrama horizontal de las 7 etapas con loops de convergencia
  - Cada nodo muestra nombre, estado actual, glow si está activo
  - Click en nodo filtra la lista de abajo
- **Tareas recientes**: últimas 10 tareas en tabla compacta, auto-refresh cada 5s

### 2. Task List (`#/tasks`)
- Tabla con columnas: Name, Status, Scheduled At, Working Dir, Created At, Actions
- Filtros: por etapa del pipeline (parseado del nombre), por status, búsqueda texto
- Polling cada 5 segundos

### 3. Task Detail (`#/tasks/:id`)
- **Panel izquierdo**: metadata (name, prompt, scheduled_at, working_dir, etc.)
- **Panel derecho**: Output viewer monospace con auto-scroll, polling cada 3s
- El output viewer es el valor principal vs. usar `curl | jq .output`

### 4. Create Task (`#/tasks/new`)
- **Pipeline Quick Launch**: botones preset para cada comando (time_split, bootstrap, space_split, etc.)
  - Pre-llena name, prompt, scheduled_at (+3 min), working_dir editable
- **Custom Task**: formulario libre con todos los campos del payload

---

## Estrategia de polling (sin WebSocket)

```typescript
// Hook genérico
function usePolling<T>(fetchFn, intervalMs, enabled): { data, error, loading, refresh }
```

- `AbortController` para cancelar requests en vuelo al desmontar
- Pausa cuando el tab del browser está oculto (`document.visibilityState`)
- Fetch inmediato al montar, luego intervalo
- `refresh()` manual para trigger post-creación de tarea

**Intervalos:**
- Lista de tareas: 5 segundos
- Output de tarea individual: 3 segundos
- Health: 10 segundos

---

## Mapeo pipeline → tareas

Las tareas se nombran con patrón `"eigen: <command> (context)"`. Se parsea con regex:

```typescript
const PIPELINE_STAGES = [
  { id: 'time_split', label: 'Time Split', hasDeepen: true },
  { id: 'bootstrap', label: 'Bootstrap', hasDeepen: true },
  { id: 'space_split', label: 'Space Split', hasDeepen: true },
  { id: 'plan_phase_epic', label: 'Plan Epic', hasDeepen: true },
  { id: 'create_issues_from_plan_swarm', label: 'Create Issues', hasDeepen: false },
  { id: 'orchestrate_swarm', label: 'Orchestrate', hasDeepen: false },
  { id: 'review_swarm_pr', label: 'Review PR', hasDeepen: false },
];

function parseStageFromTaskName(name: string): string | null {
  const match = name.match(/^eigen:\s*(?:deepen_)?(.+?)(?:\s*\(.*\))?$/);
  return match ? match[1].trim() : null;
}
```

---

## Secuencia de implementación

| Paso | Qué | Valor entregado |
|------|-----|-----------------|
| 1 | Scaffold (Vite + React + TS + Tailwind + router) | Proyecto funcional |
| 2 | API layer (`client.ts`, `types.ts`) + confirmar tipos contra API real | Conexión validada |
| 3 | Hooks (`usePolling`, `useTasks`, `useHealth`) | Datos fluyendo |
| 4 | Layout shell (Header + Sidebar + routing) | Navegación |
| 5 | **Task List page** | Reemplaza `curl /api/v1/tasks` |
| 6 | **Task Detail + Output Viewer** | Reemplaza `curl .../runs/latest \| jq .output` |
| 7 | Dashboard + Pipeline visualization | Vista de pipeline |
| 8 | Create Task + Quick Launch | Crear tareas desde UI |

Los pasos 1-6 entregan el 80% del valor (ver tareas y sus outputs). 7-8 añaden la experiencia visual.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| CORS en producción | Proxy en dev; en prod co-host o CORS header |
| Outputs muy grandes (swarm) | `overflow-y: auto` con max-height; suficiente para dev tool |
| Output no disponible durante ejecución | Mostrar status "Running..." con elapsed time; output al completar |
| Nota: webhook es discord/slack, no telegram | El plugin usa `telegram_webhook` pero la API real usa `discord_webhook`/`slack_webhook` — ajustar el form |

---

## Verificación

1. Arrancar claude-tasks: `claude-tasks serve`
2. `cd frontend && npm run dev` - verificar que el proxy funciona contra `/api/v1/health`
3. Crear una tarea desde la UI → verificar que aparece en la lista
4. Abrir detalle de tarea → verificar que el output se muestra y refresca
5. Verificar que el pipeline flow refleja las tareas activas
