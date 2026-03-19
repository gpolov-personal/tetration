# Plan: Fork claude-tasks para capturar output completo del LLM

## Context

El executor de claude-tasks (`internal/executor/executor.go`) ejecuta:

```go
cmd := exec.CommandContext(ctx, "claude", "-p", "--dangerously-skip-permissions", task.Prompt)
var stdout, stderr bytes.Buffer
cmd.Stdout = &stdout
cmd.Stderr = &stderr
err := cmd.Run() // bloquea hasta que Claude CLI termina
run.Output = stdout.String() // solo la respuesta final
```

El flag `-p` (print mode) solo emite la respuesta final a stdout. No captura tool calls, resultados intermedios, ni razonamiento.

## Opciones

### Opción A: `--output-format json` (batch, conversación completa al finalizar)

**Cambio mínimo — 1 línea en executor.go:**

```go
// Antes:
cmd := exec.CommandContext(ctx, "claude", "-p", "--dangerously-skip-permissions", task.Prompt)

// Después:
cmd := exec.CommandContext(ctx, "claude", "-p", "--output-format", "json", "--dangerously-skip-permissions", task.Prompt)
```

**Qué obtienes:** Un JSON estructurado al finalizar con toda la conversación (tool calls, resultados, respuesta final). El output sigue llegando de golpe al completar, pero contiene TODO lo que hizo el LLM.

**Impacto en frontend:** El `TaskOutputViewer` necesitaría parsear el JSON y renderizar la conversación (tool calls colapsables, output formateado, etc.) en vez de mostrar texto plano.

**Cambios necesarios:**
- executor.go: añadir flag (1 línea)
- Opcionalmente: nuevo campo `full_conversation` en `task_runs` para separar el JSON completo del output de texto
- Frontend: parsear JSON y renderizar conversación

---

### Opción B: `--output-format stream-json` (streaming real, progreso en tiempo real)

**Cambio significativo — reescribir el executor:**

```go
// Reemplazar bytes.Buffer + cmd.Run() por:
cmd := exec.CommandContext(ctx, "claude", "-p", "--output-format", "stream-json", "--dangerously-skip-permissions", task.Prompt)
stdoutPipe, _ := cmd.StdoutPipe()
cmd.Start()

scanner := bufio.NewScanner(stdoutPipe)
for scanner.Scan() {
    line := scanner.Text()
    // Parsear evento JSON
    // Append al output en la BD cada N segundos (o cada evento)
    run.Output += line + "\n"
    db.UpdateTaskRun(run) // flush incremental
}
cmd.Wait()
```

**Qué obtienes:** Eventos JSON línea por línea conforme se generan. El frontend puede hacer polling cada 3s y ver el output crecer progresivamente.

**Impacto en frontend:** El `TaskOutputViewer` muestra progreso real — tool calls apareciendo, outputs intermedios, etc. La experiencia pasa de "Running... (vacío)" a ver lo que Claude está haciendo en tiempo real.

**Cambios necesarios:**
- executor.go: reescribir captura de stdout (pipe + scanner + flush periódico)
- DB: updates incrementales al campo output durante ejecución
- Frontend: ya hace polling cada 3s, se beneficia automáticamente
- Opcionalmente: parsear eventos stream-json para renderizar con formato

---

## Comparación

| Aspecto | Opción A (json) | Opción B (stream-json) |
|---------|----------------|----------------------|
| Complejidad del cambio | Mínima (1 línea) | Significativa (reescribir executor) |
| Output durante ejecución | Vacío (igual que ahora) | Progresivo (ver en tiempo real) |
| Output al completar | JSON completo con toda la conversación | JSON completo con toda la conversación |
| Valor para el frontend | Medio (ver conversación completa post-facto) | Alto (ver progreso + conversación completa) |
| Riesgo | Bajo | Medio (concurrencia BD, buffer management) |

## Recomendación

Empezar por **Opción A** (1 línea, bajo riesgo, ya da valor) y evolucionar a **Opción B** si el streaming en tiempo real es necesario.

## Fuente

- Repo: https://github.com/kylemclaren/claude-tasks
- Archivo clave: `internal/executor/executor.go` (línea 92)
- BD: SQLite en `~/.claude-tasks/tasks.db`, tabla `task_runs` (campos `output`, `error`)
