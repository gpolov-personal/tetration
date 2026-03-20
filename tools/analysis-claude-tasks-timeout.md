# Análisis: Timeout de 30 minutos en claude-tasks

## Evidencia

La tarea `orchestrate_swarm P1.E1` (ID:57) falló:

```
status:  failed
error:   signal: killed
duration: 1800028ms (exactamente 30 minutos)
output:  (vacío)
```

## Causa

El timeout está hardcodeado en `internal/executor/executor.go` línea 141:

```go
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
```

No es configurable — no hay flag, variable de entorno, ni setting en la BD.

Cuando el proceso Claude CLI no termina en 30 minutos, el context expira y el proceso recibe `signal: killed`. El output se pierde completamente (el buffer estaba vacío porque `cmd.Run()` no había retornado).

## Impacto en eigen-squared

`orchestrate_swarm` es el comando más largo del pipeline — coordina 8-20 workers en paralelo con fases A (tests), B (código), C (validación). Puede tardar fácilmente más de 30 minutos. Con el timeout actual, este comando falla sistemáticamente en proyectos medianos/grandes.

## Fix recomendado

Hacer el timeout configurable via variable de entorno:

```go
// internal/executor/executor.go, línea 141
timeoutStr := os.Getenv("CLAUDE_TASKS_TIMEOUT_MINUTES")
timeoutMin := 120 // default 2 horas
if timeoutStr != "" {
    if v, err := strconv.Atoi(timeoutStr); err == nil && v > 0 {
        timeoutMin = v
    }
}
ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
```

Uso:

```bash
CLAUDE_TASKS_TIMEOUT_MINUTES=180 claude-tasks serve
```

## Fuente

- Repo: https://github.com/kylemclaren/claude-tasks
- Archivo: `internal/executor/executor.go` línea 141
