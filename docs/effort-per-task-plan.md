# Plan de cambios: effort por-tarea en claude-tasks

> Branch de trabajo: **`beta`** (en este repo tetration/eigen-squared y, en paralelo, en el repo claude-tasks).
> Estado: plan aprobado, pendiente de implementación.

## Objetivo y alcance

Permitir que cada tarea programada en claude-tasks ejecute `claude -p` con un `--effort` propio, para que el pipeline eigen-squared pueda correr comandos de planning a `xhigh`/`high` y comandos de implementación a `medium`.

**Dentro de alcance**
- Campo `effort` por-tarea, extremo a extremo, en el daemon claude-tasks.
- Que el cliente eigen-squared envíe `effort` según el comando.

**Fuera de alcance (decisión explícita)**
- Effort distinto líder vs teammates dentro de un swarm. Se mantiene el **spawn inline por texto** de los teammates, lo que implica que **líder y teammates comparten el mismo effort**. No se tocan definiciones de subagente, `orchestrate_swarm`, modo tmux, ni profiles/multi-runtime.

### Contexto técnico (verificado empíricamente)

- El daemon spawnea **un único** proceso `claude -p` por tarea (`internal/executor/executor.go:106`). En `orchestrate_swarm` ese proceso es el líder; los teammates son subagentes in-process del mismo proceso.
- `claude -p --effort <level>` funciona y es por-invocación (confirmado: `low`/`medium`/`high`/`xhigh`/`max`).
- `--effort` es a nivel de proceso → en el swarm, líder y teammates heredan el mismo effort. El spawn inline **no** transmite effort por-teammate (sí transmite `model`).
- Si no se pasa `--effort`, Claude Code cae al `effortLevel` global de `settings.json` (hoy `medium`).
- En `claude -p` headless, `teammateMode=tmux` se resuelve a `auto` (in-process); el modo tmux es de sesión interactiva y no aplica al path automatizado.

---

## Rama

claude-tasks:
```bash
cd ~/Projects/misc/claude-tasks && git checkout main && git pull && git checkout -b beta
```
tetration (este repo):
```bash
cd ~/Projects/misc/tetration && git checkout -b beta
```

---

## Parte A — claude-tasks (daemon Go) · núcleo del cambio

Campo `effort` aditivo, default vacío → **100% retrocompatible** (tareas sin effort caen al `effortLevel` global).

### A1. `internal/db/models.go` — struct `Task`
Añadir tras `WorkingDir` (~línea 12):
```go
Effort string `json:"effort,omitempty"` // "", low, medium, high, xhigh, max
```

### A2. `internal/db/db.go` — esquema, migración y CRUD
**Esquema** (`CREATE TABLE tasks`, ~línea 52, junto a `working_dir`):
```sql
effort TEXT NOT NULL DEFAULT '',
```
**Migración idempotente** (bloque de `ALTER TABLE`, ~línea 102, mismo patrón que `slack_webhook`):
```go
_, _ = db.conn.Exec("ALTER TABLE tasks ADD COLUMN effort TEXT NOT NULL DEFAULT ''")
```
**Las 4 queries CRUD** — añadir `effort` en posición consistente (p. ej. tras `working_dir`) y su valor/`&task.Effort` en el mismo orden:
- `CreateTask` `INSERT` (~202-204): columna `effort` + `task.Effort`.
- `GetTask` `SELECT` (~221-223): columna `effort` + `&task.Effort` en `.Scan(...)`.
- `ListTasks` `SELECT` (~233-244): igual.
- `UpdateTask` `UPDATE` (~257-259): `effort = ?` + `task.Effort` en args.

> ⚠️ El orden de columnas en cada `INSERT`/`SELECT` debe coincidir exactamente con el orden de los args/`Scan`. Mantener `effort` en la misma posición en las cuatro queries.

### A3. `internal/api/types.go` — request/response
Añadir a `TaskRequest` (~tras línea 14) y a `TaskResponse` (~tras línea 30):
```go
Effort string `json:"effort,omitempty"`
```

### A4. `internal/api/handlers.go` — propagación + validación
- `CreateTask`, en `task := &db.Task{...}` (~línea 67): `Effort: req.Effort,`
- `UpdateTask` (~línea 148): `task.Effort = req.Effort`
- `taskToResponse` (~línea 417): `Effort: task.Effort,`
- `validateTaskRequest` (~línea 448): whitelist
```go
switch req.Effort {
case "", "low", "medium", "high", "xhigh", "max":
default:
    return errInvalidEffort // añadir const junto a errEmptyPrompt
}
```

### A5. `internal/executor/shutdown_override.go` — emitir `--effort`
```go
func claudeArgs(prompt, effort string) []string {
    args := []string{"-p", "--dangerously-skip-permissions"}
    if effort != "" {
        args = append(args, "--effort", effort)
    }
    if shutdownOverrideEnabled() {
        args = append(args, "--append-system-prompt", shutdownReminderOverride)
    }
    args = append(args, prompt) // el prompt SIEMPRE va el último
    return args
}
```

### A6. `internal/executor/executor.go` — pasar el effort
Línea ~106:
```go
cmd := exec.CommandContext(ctx, "claude", claudeArgs(task.Prompt, task.Effort)...)
```

### A7. `internal/executor/executor_test.go` — tests
- Actualizar las llamadas existentes a `claudeArgs(prompt)` → `claudeArgs(prompt, "")`.
- Añadir caso: `claudeArgs("p", "medium")` contiene `["--effort","medium"]` y `claudeArgs("p", "")` **no** contiene `--effort`.

### A8. (Opcional, recomendable) sitios de construcción de `Task` a mano
`grep -rn "db.Task{" internal/` para confirmar que no haya otro sitio que construya `Task` y deba propagar `Effort`. Confirmar también qué endpoint usa el tercer `Decode` en `handlers.go:340`.

---

## Parte B — cliente eigen-squared (este repo, companion para usarlo de verdad)

claude-tasks solo expone el campo; **quién decide el effort por comando es el cliente**. Cambio mínimo en el scheduler que construye el POST (`plugins/eigen-core/eigen_core/cli/scheduler.py`, función `build_payload`):

1. Mapa comando → effort (configurable; valores por defecto sugeridos):
```python
EFFORT_BY_COMMAND = {
    "time_split": "high",
    "space_split_converge": "high",
    "plan_epic_converge": "xhigh",
    "bootstrap_converge": "high",
    "create_issues_from_plan_swarm": "medium",
    "orchestrate_swarm": "medium",
    "review_swarm_pr": "high",
}
```
2. Añadir `"effort": EFFORT_BY_COMMAND.get(command_name, "")` al payload del POST.

> Nota: en este repo (tetration) el cliente eigen es la variante single-runtime; confirmar la ruta y firma exacta de `build_payload`/`schedule_command` antes de editar. El daemon ignora el campo si no lo envías → se puede desplegar claude-tasks primero y el cliente después.
>
> Interim sin tocar eigen: como el daemon ya acepta `effort` por tarea, se puede fijar manualmente al crear una tarea vía API/TUI; el daemon lo honra igual.

---

## Política de effort sugerida (a revisar)

| Comando | Effort | Razón |
|---|---|---|
| `plan_epic_converge` | `xhigh` | Plan estratégico, lo más sensible a inteligencia |
| `time_split`, `space_split_converge`, `bootstrap_converge`, `review_swarm_pr` | `high` | Arquitectura / decomposición / review |
| `orchestrate_swarm`, `create_issues_from_plan_swarm` | `medium` | Ejecución; líder + teammates a medium |
| (sin mapear) | `""` | Cae al `effortLevel` global |

---

## Verificación

1. **Unit**: `go test ./internal/...` (db CRUD round-trip con effort; executor args).
2. **Migración**: arrancar el daemon contra una DB existente y confirmar que `ALTER TABLE` no rompe y las tareas viejas siguen (`effort=''`).
3. **End-to-end**: crear una tarea con `effort:"xhigh"` vía API, lanzarla, y confirmar con un hook `PreToolUse` (lee `effort.level` del JSON o `$CLAUDE_EFFORT`) que el proceso corre a `xhigh`. Una tarea con `effort:""` debe caer a `medium` (global).

### Receta del hook de verificación
```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "*", "hooks": [ { "type": "command",
        "command": "python3 -c 'import sys,json; d=json.load(sys.stdin); open(\"/tmp/effort_probe.log\",\"a\").write(d.get(\"effort\",{}).get(\"level\",\"?\")+\"\\n\")'" } ] }
    ]
  }
}
```
(Confirmado funcionando: `$CLAUDE_EFFORT` y `effort.level` reflejan el effort real del proceso.)

---

## Compatibilidad y rollback

- **Aditivo y retrocompatible**: columna con default vacío; sin effort → comportamiento idéntico al actual.
- **Rollback**: revertir el commit; la columna `effort` queda en la DB sin uso (inerte). No hace falta down-migration.

---

## Checklist de PR (rama `beta`)

- [ ] A1–A7 implementados en claude-tasks, `effort` en idéntica posición en las 4 queries
- [ ] `validateTaskRequest` rechaza valores fuera del whitelist (400)
- [ ] tests de executor + db actualizados y verdes
- [ ] migración probada sobre DB existente
- [ ] e2e con hook confirmando `--effort` aplicado
- [ ] (companion, este repo) `build_payload` de eigen envía `effort` por comando
