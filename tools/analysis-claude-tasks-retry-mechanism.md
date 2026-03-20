# Análisis: Mecanismo de retry para tareas fallidas en claude-tasks

## Context

`orchestrate_swarm` falla por timeout de 30 min (hardcodeado). Los workers dejan checkpoints en `swarm_working_notes/`, por lo que relanzar la tarea permite reanudar desde donde quedó. Se necesita un mecanismo para relanzar automáticamente.

## Estado actual

- La tabla `tasks` **no tiene campo de status** — solo `enabled` (0/1)
- El scheduler (`SyncTasks`, cada 10s) solo mira `enabled && !isScheduled` — no consulta `task_runs`
- Cuando una tarea one-off se ejecuta (éxito o fallo), se marca `enabled=false` automáticamente
- No existe mecanismo de retry nativo

## 3 formas de relanzar una tarea fallida

| Método | Cómo | Auto-deshabilita después? |
|--------|------|--------------------------|
| `POST /api/v1/tasks/{id}/run` | Ejecuta inmediatamente, ignora `enabled` | No |
| `POST /api/v1/tasks/{id}/toggle` | Pone `enabled=true`, scheduler la recoge en ≤10s | Sí (ciclo limpio) |
| SQLite directo | `UPDATE tasks SET enabled=1 WHERE id=X` | Sí |

### El más limpio: `POST /tasks/{id}/run`

- No requiere cambiar `enabled`
- No auto-deshabilita después (el flag queda como estaba)
- Crea un nuevo `task_run` con su propio tracking
- Obtiene un nuevo context con timeout de 30 min

### Auto-retry con script externo

```bash
#!/bin/bash
# Monitorear y relanzar tareas fallidas cada 60 segundos
TASK_ID=57
API="http://localhost:8080/api/v1"

while true; do
  status=$(curl -s "$API/tasks/$TASK_ID/runs/latest" | jq -r '.status')
  if [ "$status" = "failed" ]; then
    echo "$(date) Task $TASK_ID failed, relaunching..."
    curl -s -X POST "$API/tasks/$TASK_ID/run"
  elif [ "$status" = "completed" ]; then
    echo "$(date) Task $TASK_ID completed. Done."
    break
  fi
  sleep 60
done
```

## Limitación

Cada relanzamiento tiene el mismo timeout de 30 minutos. Si `orchestrate_swarm` necesita consistentemente más de 30 min incluso con checkpoint resumption, seguirá fallando en cada intento.

## Solución ideal: fork de claude-tasks con 2 cambios

### 1. Timeout configurable

```go
// internal/executor/executor.go, línea 141
// Antes: ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
// Después:
timeoutMin := 120 // default 2 horas
if v := os.Getenv("CLAUDE_TASKS_TIMEOUT_MINUTES"); v != "" {
    if n, err := strconv.Atoi(v); err == nil && n > 0 {
        timeoutMin = n
    }
}
ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
```

### 2. Auto-retry con max_retries (opcional)

Añadir campo `max_retries` (default 0) a la tabla `tasks`:

```sql
ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 0;
```

En el executor, tras un fallo, contar runs fallidos y relanzar si no se alcanzó el máximo:

```go
// Pseudo-código en executor.go, después de que cmd.Run() falla:
if task.MaxRetries > 0 {
    failedRuns := db.CountFailedRuns(task.ID)
    if failedRuns < task.MaxRetries {
        // Re-enable para que el scheduler lo recoja
        task.Enabled = true
        task.ScheduledAt = time.Now().Add(1 * time.Minute) // delay antes de retry
        db.UpdateTask(task)
    }
}
```

## Fuente

- Repo: https://github.com/kylemclaren/claude-tasks
- Archivos clave:
  - `internal/scheduler/scheduler.go` — `SyncTasks`, `executeOneOff`
  - `internal/executor/executor.go` — `Execute`, `ExecuteAsync` (línea 141: timeout)
  - `internal/api/handlers.go` — `RunTask` handler (`POST /tasks/{id}/run`)
