# Análisis: `orchestrate_swarm` en OpenCode

## 1. Qué hace `orchestrate_swarm` (resumen ejecutivo)

`orchestrate_swarm` es el **orquestador central** del pipeline eigen-squared. Actúa como un **Staff Engineer / Tech Lead** que:

1. **Lee un manifiesto** (`swarm-manifest.json`) que define tareas, olas de ejecución, dependencias, archivos propiedad de cada worker, y archivos compartidos
2. **Crea un equipo de agentes** (`swarm-P<N>.E<M>`) y se convierte en líder (`team-lead`)
3. **Spawn workers por oleadas** — cada worker ejecuta un ciclo TDD: primero diseña tests de validación (`design_validation_tests_swarm`), luego implementa código (`code_from_validation_tests_swarm`)
4. **Gestiona dependencias de interfaz** — providers generan stubs primero, consumers arrancan después
5. **Reacciona a mensajes** — resuelve `[QUESTION]`, `[BLOCKER]`, `[STUCK]`, requests de integración
6. **Integra archivos compartidos** — spawneando un "integrator" especializado
7. **Atribuye y repara fallos post-integración** — re-spawneando fix workers con budgets limitados
8. **Crea PR y cierra el equipo**

### Las 6 etapas

| Stage | Función |
|-------|---------|
| **0** | Setup: verificar branch, leer manifiesto, detectar tech stack, crear equipo |
| **1** | Crear tareas en el task list compartido con dependencias |
| **2** | Spawn workers oleada por oleada (providers → consumers) |
| **3** | Bucle reactivo: responder a mensajes, desbloquear dependencias, guiar workers stuck |
| **4** | Integración: archivos compartidos, verificación de stubs, fix loop post-integración |
| **5** | Shutdown, crear PR, reportar |

### Mecanismos críticos

- **Compaction Resilience**: Todo el estado del líder se persiste en tareas con prefijos (`[WAVE-STATUS]`, `[STUB-READY]`, `[INTEGRATION-REQUEST]`). Si Claude pierde contexto, reconstruye todo estado desde `TaskList()`
- **Fix Budgets**: Cada worker tiene 5 intentos asistidos. Si se agotan, se salta el task
- **Modo autónomo**: Por defecto no pregunta al humano — toma decisiones conservadoras y las documenta en tareas `[DECISION-AUTONOMOUS]`

---

## 2. Arquitectura de agentes en OpenCode

### Modelo jerárquico basado en sesiones

```
Primary Agent (build/plan)
  ├── Subagent: @general (research, multi-step)
  ├── Subagent: @explore (read-only, fast)
  └── Subagent: @custom-agent (definido por usuario)
```

- **Primary agents**: El usuario interactúa directamente (`build` con todos los tools, `plan` read-only)
- **Subagents**: Invocados via `TaskTool` o `@mention`, crean **child sessions** con `parentID`
- Cada subagent tiene su propia sesión aislada con permisos configurables

### Agent Teams (feature reciente)

OpenCode **ya implementó agent teams** inspirándose en Claude Code, con diferencias clave:

| Aspecto | Claude Code (usado por eigen²) | OpenCode |
|---------|-------------------------------|----------|
| **Mensajería** | JSON array files (polling) | JSONL append-only + session injection |
| **Topología** | Líder-céntrica | **Full mesh peer-to-peer** |
| **Proveedores** | Solo Anthropic | **Multi-modelo** (GPT-5 + Gemini + Claude simultáneamente) |
| **Proceso** | Multi-proceso (tmux panes) | **Single-process** con locks en memoria |
| **Auto-wake** | No | Sí — teammates idle se reactivan al recibir mensaje |

### Primitivas disponibles en OpenCode

| Primitiva eigen² | Equivalente OpenCode | Estado |
|-------------------|---------------------|--------|
| `TeammateTool.spawnTeam` | `team_spawn` | ✅ Existe |
| `TeammateTool.write` | `team_message` | ✅ Existe (peer-to-peer) |
| `TeammateTool.broadcast` | Mensajes a todos los peers | ✅ Posible |
| `TeammateTool.requestShutdown` | Shutdown via state machine | ✅ Existe |
| `TaskCreate/Update/List` | TaskTool + child sessions | ✅ Existe |
| `SendMessage` (a teammate) | `team_message` | ✅ Existe |
| Skill tool | Skill tool / Custom commands | ✅ Existe |
| tmux backend | No — single-process | ⚠️ Diferente modelo |

---

## 3. Encaje de `orchestrate_swarm` en OpenCode — Análisis detallado

### Lo que funcionaría directamente

**a) Modelo jerárquico líder-workers**: OpenCode soporta que un primary agent spawne múltiples subagents en paralelo. El patrón "team-lead coordina workers" encaja bien.

**b) Task system**: OpenCode tiene `TaskTool` para crear tareas con `task_id` resumible. Los prefijos `[WORK]`, `[QUESTION]`, `[BLOCKER]` etc. funcionarían como convención sobre el task system existente.

**c) Skill system**: Los workers invocan `Skill("eigen-squared:design_validation_tests_swarm")` — OpenCode tiene un sistema de skills/commands que carga markdown con instrucciones. Esto es directamente compatible.

**d) Plugin tools**: OpenCode permite registrar tools custom en `.opencode/tools/`. Las operaciones del swarm podrían empaquetarse como tools.

**e) Custom agents**: Los workers podrían definirse como agentes custom en `.opencode/agents/` con prompts específicos, permisos restringidos (solo sus archivos), y modelos configurables.

**f) Multi-modelo**: Ventaja de OpenCode — el swarm podría usar **diferentes LLMs** para diferentes roles: Opus para el líder, Sonnet para workers, Gemini para el integrador.

### Fricciones y adaptaciones necesarias

**a) Agent Teams vs. Subagent Sessions**

orchestrate_swarm asume el **TeammateTool de Claude Code** con operaciones específicas (`spawnTeam`, `requestJoin`, `approveShutdown`, etc.). OpenCode tiene su **propia implementación de teams** con API diferente:

```
eigen²:                          OpenCode:
─────────                        ─────────
spawnTeam("name")       →       team_spawn(name, prompt, model)
write(to, message)      →       team_message(to, content)
requestShutdown(name)   →       State machine transition
TeammateTool.cleanup()  →       Automatic single-process cleanup
```

**Adaptación**: Reescribir las llamadas de TeammateTool a las primitivas `team_spawn`/`team_message` de OpenCode. La topología **peer-to-peer** de OpenCode es incluso más flexible que la líder-céntrica de Claude Code.

**b) Compaction Resilience via TaskList**

orchestrate_swarm persiste TODO su estado en tareas prefijadas (`[WAVE-STATUS]`, `[STUB-READY]`, etc.) para sobrevivir a compactación de contexto. OpenCode tiene su propio mecanismo de compaction (un agente `compaction` dedicado que resume el contexto).

**Adaptación**: El patrón de `[WAVE-STATUS]` tasks funciona si OpenCode expone `TaskCreate`/`TaskList` a los agents. Actualmente el `TaskTool` crea **child sessions**, no un task list compartido estilo kanban. Sería necesario:
- Implementar un **shared task board** (posiblemente como un MCP tool o plugin tool)
- O usar archivos JSON en disco como store compartido (más simple)

**c) Backend de ejecución: single-process vs tmux**

eigen² asume tmux panes visibles para cada worker. OpenCode usa **single-process con locks en memoria** — los workers NO son visibles en panes separados.

**Impacto**:
- No puedes "ver" a los workers trabajando en tiempo real en panes tmux
- Pero el rendimiento es **mejor** (sin overhead de procesos separados)
- La comunicación es **más rápida** (memoria vs. archivos JSON en disco)
- El debugging es **más difícil** (no hay panes para inspeccionar)

**d) Working Notes y crash recovery**

orchestrate_swarm usa `swarm_working_notes/working-notes-<task.id>.md` como memoria externa para cada worker. Si un worker crashea, se re-spawnea y lee sus notas para continuar.

En OpenCode, los subagents tienen **sessions resumibles** via `task_id`. Esto es funcionalmente equivalente — el subagent puede reanudar su sesión completa en lugar de leer working notes.

**Adaptación**: Más limpio en OpenCode — en lugar de working notes en disco, cada worker mantiene su sesión persistente. Sin embargo, si la sesión se compacta, se pierde granularidad. Un enfoque híbrido (session + notas en disco) sería óptimo.

**e) Branch isolation y git coordination**

orchestrate_swarm requiere que TODOS los workers operen en la misma branch (`feat/P<N>.E<M>`). Con el modelo single-process de OpenCode, todos comparten el mismo working directory.

**Riesgo**: Conflictos de git si dos workers intentan commitear simultáneamente. OpenCode necesitaría:
- Un **lock de commit** (que ya tiene internamente)
- O **git worktrees** para isolation real (más seguro pero más complejo)

**f) CLI eigen-squared (`eigen-squared get-context`, `eigen-squared complete`)**

El comando depende del CLI `eigen-squared` para obtener contexto y registrar progreso. En OpenCode, esto se implementaría como:
- Un **MCP server** que expone las operaciones del pipeline
- O un **plugin tool** que wrappea las llamadas al CLI

### Diagrama de flujo adaptado a OpenCode

```
┌─────────────────────────────────────────────────────┐
│  OpenCode Primary Agent ("build" mode)               │
│  Role: Swarm Leader / Staff Engineer                 │
│                                                      │
│  1. Read manifest via custom tool/MCP                │
│  2. team_spawn("swarm-P1.E2")                       │
│                                                      │
│  Wave 1:                                             │
│  ├─ team_spawn("worker-1", opus, prompt_A)          │
│  ├─ team_spawn("worker-2", sonnet, prompt_B)  ←multi│
│  └─ team_spawn("worker-3", gemini, prompt_C)  model!│
│                                                      │
│  React loop:                                         │
│  ├─ team_message from worker-1: "Stub ready"        │
│  ├─ team_message from worker-2: "[QUESTION]..."     │
│  │   → Leader decides, team_message back             │
│  ├─ worker-3 idle → auto-wake on new message        │
│  └─ All wave 1 done → spawn wave 2                  │
│                                                      │
│  Integration:                                        │
│  ├─ team_spawn("integrator", opus, int_prompt)      │
│  └─ Verify tests, fix loop if needed                │
│                                                      │
│  5. gh pr create, cleanup, report                    │
└─────────────────────────────────────────────────────┘
```

---

## 4. Ventajas de ejecutar orchestrate_swarm en OpenCode

1. **Multi-modelo**: Workers con Sonnet (barato/rápido), Líder con Opus (inteligente), Integrador con Gemini (contexto largo). Optimización de coste imposible en Claude Code nativo.

2. **Peer-to-peer messaging**: Workers podrían comunicarse entre sí directamente, sin pasar por el líder. Útil para resolver dependencias de interfaz entre workers del mismo wave.

3. **Auto-wake**: Si un worker termina y otro le manda un mensaje (ej. "stub ready"), el worker se reactiva automáticamente. En Claude Code hay que pollear.

4. **Single-process = más rápido**: Sin overhead de tmux panes, comunicación en memoria.

5. **Plugin ecosystem**: El manifiesto y la lógica del pipeline podrían empaquetarse como un plugin de OpenCode distribuible via npm.

---

## 5. Desafíos y riesgos

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| No hay `TaskList` compartido tipo kanban | **Alta** | Implementar como plugin tool o MCP server |
| Single-process = sin visibilidad de workers | Media | Logging estructurado, dashboard custom via TUI plugin |
| Git conflicts con workers concurrentes | **Alta** | Locks de commit o git worktrees |
| TeammateTool API diferente | Media | Capa de adaptación (wrapper functions) |
| No hay `eigen-squared` CLI en el PATH | Media | Portar como MCP server o tool plugin |
| Compaction puede perder estado del líder | Media | Persistir estado en archivos JSON (ya probado por eigen²) |
| State machines de OpenCode teams ≠ eigen² lifecycle | Media | Mapear estados: ready↔active, shutdown_requested↔requestShutdown |

---

## 6. Conclusión

**orchestrate_swarm es mayormente compatible con OpenCode**, pero requiere una **capa de adaptación** en tres áreas clave:

1. **API de teams**: Traducir `TeammateTool.*` → `team_spawn`/`team_message` de OpenCode
2. **Task board compartido**: Implementar el patrón `[WAVE-STATUS]`/`[WORK]` como plugin tool o archivos JSON en disco (OpenCode no tiene un TaskList compartido nativo equivalente)
3. **CLI del pipeline**: Empaquetar `eigen-squared get-context`/`complete` como MCP server o plugin

La **mayor ventaja** de correr el swarm en OpenCode es el soporte **multi-modelo** — podrías usar Claude Opus para decisiones arquitectónicas del líder, Sonnet para workers de implementación, y un modelo local para tareas de exploración, optimizando coste sin sacrificar calidad en las decisiones críticas.

La **mayor fricción** es que el modelo single-process de OpenCode es fundamentalmente diferente al modelo tmux multi-proceso de Claude Code — todo funciona más rápido pero pierde la visibilidad de "ver a los workers trabajar" en panes separados.
