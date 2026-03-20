# Análisis: Race Condition en claude-tasks scheduler

## Evidencia

En el proyecto gecolab, la tarea `deepen_plan_phase_epic` (ID:45) se ejecutó **dos veces simultáneamente**:

```
ID:45 | deepen_plan_phase_epic
  RUN 1: started 01:19:10 → ended 01:33:04 (431s)
  RUN 2: started 01:19:10 → ended 01:36:16 (1026s)
```

Cada run auto-encadenó un paso distinto, bifurcando el pipeline en dos ramas paralelas que tomaron decisiones de convergencia diferentes.

## Root Cause

El bug está en la interacción entre `executeOneOff()` y `SyncTasks()` en `internal/scheduler/scheduler.go`.

### Flujo de `executeOneOff`

```go
func (s *Scheduler) executeOneOff(taskID int64) {
    task, _ := s.db.GetTask(taskID)
    if !task.Enabled { return }           // (1) Check

    s.executor.ExecuteAsync(task)          // (2) Launch (async, non-blocking)

    task.Enabled = false                   // (3) Disable AFTER launch
    _ = s.db.UpdateTask(task)

    s.mu.Lock()
    delete(s.oneOffTimers, taskID)         // (4) Cleanup timer map
    s.mu.Unlock()
}
```

### Flujo de `SyncTasks` (cada 10 segundos)

```go
func (s *Scheduler) SyncTasks() {
    tasks, _ := s.db.ListTasks()
    for _, task := range tasks {
        _, hasOneOffTimer := s.oneOffTimers[task.ID]
        isScheduled := hasCronJob || hasOneOffTimer

        if task.Enabled && !isScheduled {
            // "Task habilitada pero no programada → re-programar"
            _ = s.scheduleTaskLocked(task)
        }
    }
}
```

### La ventana de race

```
T+0ms    Timer dispara → executeOneOff() arranca en goroutine
T+0ms    Lee task de BD → Enabled=true ✓
T+0ms    ExecuteAsync(task) → lanza proceso claude (goroutine, retorna inmediato)
         ──── VENTANA ABIERTA ────
T+?ms    SyncTasks() lee BD → Enabled=true (aún no se escribió false)
T+?ms    SyncTasks() ve !isScheduled (timer borrado o nunca guardado)
T+?ms    SyncTasks() → scheduleTaskLocked → scheduled_at en el pasado → delay <= 0
T+?ms    → go executeOneOff(taskID) ← SEGUNDA EJECUCIÓN
         ──── VENTANA CIERRA ────
T+?ms    Primera executeOneOff escribe Enabled=false (tarde)
```

### Agravante: tareas con `scheduled_at` en el pasado

Cuando `scheduled_at` ya pasó, `scheduleOneOffTaskLocked` hace:

```go
if delay <= 0 {
    go s.executeOneOff(taskID)  // ejecuta inmediatamente
    return nil                   // NO guarda timer en oneOffTimers
}
```

No se guarda timer en el map → `SyncTasks` **siempre** ve `isScheduled=false` para estas tareas → las re-programa en cada ciclo de 10s mientras `Enabled=true`.

## Defensas que faltan

| Defensa | Existe |
|---------|--------|
| Check "is already running" antes de ejecutar | No |
| `UPDATE SET enabled=0 WHERE enabled=1` atómico (CAS) | No |
| Timer/flag en memoria para tareas immediate-execution | No |
| DB transaction en creación de run | No |
| Constraint unique en `(task_id, status='running')` | No |
| Verificación de runs existentes antes de lanzar | No |

## 4 entry points no coordinados

Hay 4+ caminos independientes que pueden llamar `ExecuteAsync` para la misma tarea sin coordinación:

1. **Cron callback** — dispara en cada tick del cron
2. **One-off timer** (`executeOneOff`) — dispara cuando expira el timer
3. **API handler** (`POST /tasks/{id}/run`) — dispara por HTTP request
4. **`SyncTasks`** — re-programa tareas que ve como "enabled + not scheduled"

Ninguno verifica si la tarea ya tiene un run con `status='running'`.

## Fix recomendado

### Opción 1: Atomic compare-and-set (mínimo, resuelve el 90%)

```go
func (s *Scheduler) executeOneOff(taskID int64) {
    // Atomic: disable BEFORE execute. Only one goroutine wins.
    rowsAffected, err := s.db.Exec(
        "UPDATE tasks SET enabled = 0, next_run_at = NULL WHERE id = ? AND enabled = 1",
        taskID,
    )
    if err != nil || rowsAffected == 0 {
        return // another goroutine already claimed it
    }

    task, _ := s.db.GetTask(taskID)
    s.executor.ExecuteAsync(task)

    s.mu.Lock()
    delete(s.oneOffTimers, taskID)
    s.mu.Unlock()
}
```

### Opción 2: Guard en executor (defensa en profundidad)

```go
func (e *Executor) Execute(task db.Task) {
    // Check for existing running run
    runs, _ := e.db.GetTaskRuns(task.ID, 1)
    if len(runs) > 0 && runs[0].Status == "running" {
        return // already executing
    }
    // ... proceed with execution
}
```

### Opción 3: Guardar referencia para immediate one-offs

```go
func (s *Scheduler) scheduleOneOffTaskLocked(task db.Task) error {
    // ...
    if delay <= 0 {
        // Store a sentinel so SyncTasks sees isScheduled=true
        s.oneOffTimers[task.ID] = nil // sentinel, not a real timer
        go s.executeOneOff(task.ID)
        return nil
    }
    // ...
}
```

**La opción 1 es la más robusta** — un solo goroutine gana la escritura atómica y ejecuta. Las demás ven `rowsAffected=0` y se retiran.

## Impacto en eigen-squared

Cuando un paso del pipeline se ejecuta dos veces:
- Cada ejecución auto-encadena el siguiente paso independientemente
- El pipeline se **bifurca** en dos ramas paralelas
- Cada rama puede tomar decisiones de convergencia diferentes
- Resultado: tareas duplicadas, ejecuciones espurias, inconsistencia en `pipeline_state.json`

## Fuente

- Repo: https://github.com/kylemclaren/claude-tasks
- Archivos clave:
  - `internal/scheduler/scheduler.go` — `executeOneOff`, `SyncTasks`, `scheduleOneOffTaskLocked`
  - `internal/executor/executor.go` — `Execute`, `ExecuteAsync`
  - `internal/db/db.go` — `CreateTaskRun`, `UpdateTask`
