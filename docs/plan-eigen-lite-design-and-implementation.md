# Plan de Diseño e Implementación — `eigen-lite`

> **Documento de planificación arquitectónica.** Plugin destilado de eigen-squared para iniciativas pequeñas (2-5 features) sobre código existente, manteniendo la autonomía del watchdog y el rigor del swarm TDD.
>
> **Estado:** Plan aprobado por usuario, pendiente de spikes de validación (Sprint 0).
> **Audiencia:** revisión por Codex; ejecución por Claude Code en sesiones futuras.
> **Última actualización:** 2026-04-20

---

## 0 · Resumen ejecutivo

**Decisión arquitectónica principal:** crear un **plugin separado** (`eigen-lite`) con su propio CLI, su propio state file (`pipeline_state.json` con schema simplificado), su propio watchdog cron y su propia entrada en `marketplace.json`. Compartir infraestructura común vía librería extraída `eigen-core` (git ops, scheduler, modelos base).

**Por qué un plugin nuevo en vez de un comando "eigen_quick" dentro de eigen-squared:** las dos alternativas de `eigen_quick` evaluadas en sesiones previas resultaron ambas peores arquitectónicamente:
- *eigen_quick ligero* → fabrica artefactos thin que los reviewers downstream rechazan, generando degradación en cascada.
- *eigen_quick robusto* → re-implementa la inteligencia de los comandos saltados en un único contexto, lo que cuesta tantos tokens como ejecutar el pipeline original pero con peor calidad.

Un plugin destilado **admite la verdad arquitectónica**: workflows para 50 features y workflows para 2-5 features no son el mismo workflow a distinta escala — son workflows estructuralmente distintos.

**Alcance funcional:**
- Plugin lite **soporta 1 fase con N epics** (típicamente 1-5 epics + 1 E2E Testing epic).
- Si una iniciativa requiere múltiples fases o decomposición temporal, usar eigen-squared.
- El usuario elige el plugin según escala; ambos pueden coexistir en distintos repos (o, raramente, en el mismo).

**Esfuerzo estimado:** 3-4 semanas de trabajo focalizado, repartidas en 7 sprints (incluyendo Sprint 0 de validación).

**Reutilización confirmada:**
- ~50% del CLI de squared vía `eigen-core` (git_ops, scheduler, modelos base, I/O primitives).
- ~95% de los workers TDD (`design_validation_tests_swarm`, `code_from_validation_tests_swarm`) sin modificación, vía referencias cross-plugin `Skill("eigen-squared:...")`.
- ~95% del watchdog shell script (cambia env path, lockfile, binary name, COMMAND_TO_SKILL).
- ~95% del core de `orchestrate_swarm` y `review_swarm_pr` (copy-adapt; los wrappers CLI cambian, la lógica de orquestación es agnóstica).

**Trabajo realmente nuevo:** ~1300 líneas de código + ~120 tests + 3 comandos slash nuevos (`lite_plan`, `lite_swarm`, `lite_review`) + 1 comando de inicialización (`lite_start`) + watchdog adaptado + plugin manifest.

---

## 1 · Hallazgos clave del análisis previo

### 1.1 Lo genuinamente reusable (sin trampa)

| Pieza | Reusabilidad | Fundamento |
|-------|--------------|------------|
| `git_ops.py` | 100% | Schema-agnóstico; wrapper puro de git |
| `scheduler.py` | 95% | Solo cambia `COMMAND_TO_SKILL` mapping |
| `state.py` (load/save/resolve_state_file) | 100% | I/O JSON puro |
| Workers TDD | ~90% | NO leen `pipeline_state.json`; consumen solo `swarm-manifest.json` |
| Core de `orchestrate_swarm` (spawn, message handling, integration step, E2E fix loop) | 100% del CORE | Solo wrappers CLI dependen del schema |
| Core de `review_swarm_pr` (review agent spawn, convergence decision, fixup task creation, lesson extraction) | 100% del CORE | Solo wrappers CLI dependen del schema |
| Watchdog shell script | 95% | Solo cambia env path, lockfile path, binary name |
| Test fixtures `make_*()` builders | 100% | Funciones puras Python |

### 1.2 Lo que se debe reimplementar (con tamaño realista)

| Pieza | Líneas estimadas | Justificación |
|-------|------------------|---------------|
| `models_lite.py` (5 dataclasses) | 230 | Schema con epics dict (LitePlanState, LiteEpicState, LiteSwarmExecution, LiteReviewState, LitePipelineState) |
| `transitions_lite.py` (`determine_next_lite`) | 180 | Camina epics secuencialmente: plan → for each epic: swarm ↔ review |
| `subcommands_lite/` (14 handlers) | 700 | Wrappers + lógica de mutación schema-específica con args `--epic` |
| `main_lite.py` (argparse) | 160 | Dispatcher análogo al de squared |
| `validate_state_lite()` | 100 | Validators adaptados al schema con epics dict |
| **Total código nuevo** | **~1370** | vs ~1500 líneas del CLI de squared |

### 1.3 Decisiones arquitectónicas confirmadas

1. **Diseño A (dos plugins separados)** confirmado.
2. **Extraer `eigen-core` como librería compartida** dentro del mismo monorepo.
3. **lite_plan condensa 5+ comandos** (initiative_review parcial + time_split + bootstrap_converge + space_split_converge + plan_epic_converge × N epics + create_issues_from_plan_swarm × N epics) en stages internos secuenciales.
4. **lite_swarm y lite_review son adaptaciones casi-directas** de orchestrate_swarm y review_swarm_pr (copy-adapt, no Skill reference).
5. **Mantener naming `P1.E<M>` y estructura `phases/phase_1/epic_<M>/`** aunque conceptualmente lite sea single-phase. Esto preserva compatibilidad con workers TDD que tienen ese template hardcoded en el spawn prompt.
6. **Soporte multi-epic en lite:** la versión lite debe gestionar varias épicas (típicamente 1-5 + 1 E2E Testing epic). 5 features ortogonales pueden requerir casi 1 épica por cada una.

---

## 2 · Riesgos críticos identificados (con mitigaciones)

### 🔴 R1 — Branch verification hardcoded en workers (BLOQUEADOR si se ignora)

**Problema:** El spawn prompt de workers (líneas 265-271 de `orchestrate_swarm.md`) inyecta validación literal:
```
If branch is NOT feat/P<N>.E<M>: STOP IMMEDIATELY. Send a [BLOCKER]...
```
Si lite_swarm invocara workers desde una branch arbitraria (`feat/lite-anything`), fallarían inmediatamente.

**Mitigación adoptada:** lite_swarm **copia y adapta** orchestrate_swarm en lugar de invocarlo via Skill. Mantiene branch naming `feat/P1.E<M>` por epic. Workers se invocan via `Skill("eigen-squared:design_validation_tests_swarm")` desde el lite_swarm orchestrator, que les pasa el spawn prompt con `feat/P1.E<M>` como branch esperada — exactamente lo que esperan.

**Verificable mediante spike (Sprint 0).**

### 🔴 R2 — Path templates hardcoded en workers (BLOQUEADOR si estructura cambia)

**Problema:** Workers asumen `phases/phase_<N>/epic_<M>/` derivado del `epic_id` del manifest. También hardcodean `tests/tracker-files/` y `swarm_working_notes/`.

**Mitigación adoptada:** lite_plan genera artefactos en la **misma estructura de directorios** que squared (`phases/phase_1/epic_<M>/...`). El usuario nunca ve estas rutas — son detalles internos. La diferencia entre squared y lite es semántica (single-phase, no jerarquía multi-fase), no estructural.

**Coste:** ninguno — es solo una convención de naming.

### 🟠 R3 — Cross-plugin skill referencing requiere validación

**Problema:** Asumimos que `Skill("eigen-squared:design_validation_tests_swarm")` invocado desde un comando de eigen-lite funciona. La sintaxis aparece en el código de eigen-squared **referenciando sus propios skills**, no se ha validado cross-plugin.

**Mitigación:** **Spike obligatorio en Sprint 0** (validación de 1-2 horas). Si falla: alternativa = symlinks o plugin.json con `dependencies` (también requiere validación). Worst case = duplicar los SKILL.md en eigen-lite (overhead de mantenimiento, pero funcional). **Resultado Sprint 0:** S0.1 VALIDATED vía docs oficiales — namespacing nativo `plugin-name:skill-name`.

### 🟠 R4 — `plugin.json dependencies` y `marketplace.json` registration

**Problema:** No hay documentación oficial verificada en el repo sobre estos campos. eigen-lite necesita declararse en `marketplace.json` y posiblemente declarar dependencia de eigen-squared.

**Mitigación:** Spike incluye validar que ambos plugins coexisten en el marketplace y que las dependencias funcionan. **Resultado Sprint 0:** S0.2 VALIDATED — el campo correcto es `dependencies` (array, soporta semver), introducido en Claude Code v2.1.110+. Schema: `"dependencies": ["eigen-squared", {"name": "eigen-core", "version": "~1.0.0"}]`. Resolución lazy, errores explícitos en `claude plugin list --json`.

### 🟠 R5 — `lite_plan` es monolítico (riesgo de comando lento e impredecible)

**Problema:** Condensar 5+ comandos en uno significa que lite_plan podría tardar 30-60 minutos. Si falla a mitad, el usuario pierde mucho trabajo. Con multi-epic, el riesgo aumenta linealmente con el número de epics.

**Mitigación adoptada:** lite_plan estructurado en stages internos con **checkpoints persistentes** después de cada stage. Si falla en Stage D, una re-ejecución reanuda desde D leyendo los artefactos de A-C ya generados. Esto requiere:
- Marcar progreso en `pipeline_state.lite_plan.stages_completed: ["A", "B", "C"]`
- Cada stage idempotente (puede re-ejecutarse sin corromper estado)
- Para Stage E (per-epic plan + tasks + manifest), trackear progreso por epic: `stages_completed: ["A", "B", "C", "D", "E:1", "E:2"]`

### 🟡 R6 — Cero tests en CLI subcommands de eigen-squared

**Problema:** El CLI de squared tiene 0/20 tests para `cmd_*`. Si simplemente copiamos el patrón, eigen-lite hereda el gap.

**Mitigación:** lite va **TDD obligatorio** en CLI subcommands desde el principio. Aprovechamos que estamos empezando para no repetir el error.

### 🟡 R7 — Inconsistencia de versiones en marketplace.json

**Problema:** `plugin.json` dice 3.4.6, `marketplace.json` dice 1.1.0 para eigen-squared. Si lite se registra con versión inconsistente, el comportamiento es impredecible.

**Mitigación:** Tarea de cleanup en Sprint 0 (1 hora): sincronizar versiones antes de tocar nada más.

### 🟡 R8 — Workers escriben `swarm_working_notes/` y `tests/tracker-files/` en repo root

**Problema:** Si el usuario tiene un repo donde estos directorios significan otra cosa, hay colisión. (No es nuevo de lite, pero merece nota).

**Mitigación:** Documentar en README de lite que estos paths son convención (heredados de squared). No bloquea implementación.

---

## 3 · Diseño detallado de `lite_plan` (el comando crítico)

### 3.1 Stages internos (con artefactos generados)

| Stage | Condensa de squared | Inputs | Outputs (artefactos en disco) | Skippable |
|-------|---------------------|--------|-------------------------------|-----------|
| **A. Introspection + Capture** | `initiative_review` (subset) + introspección de `bootstrap_converge` Stage 0 | Repo existente, interview corto del usuario (2-5 features) | `feature_summary.md` (interno), language profile detection, external dep verification | Nunca |
| **B. Single-Phase Manifest** | `time_split` (simplified for N=1) | Stage A outputs | `phases/phase_1/phase_1_manifest.md` con Features by Domain, Cluster info, Blackbox specs verbatim, E2E summary | Nunca |
| **C. Bootstrap Delta** | `bootstrap_converge` (sin convergence loop, 1 reviewer interno) | Phase manifest + repo introspection | `phases/phase_1/bootstrap-report.json` (real si hay delta, derivado de introspección si no) | **Sí** si delta=0 (caso aditivo puro) |
| **D. Multi-Epic Decomposition** | `space_split_converge` (sin convergence loop) | Phase manifest + bootstrap report | `phases/phase_1/epic_manifest.json`, `phases/phase_1/phase_e2e_config.json`, `phases/phase_1/epic_<M>/epic.md` para cada epic feature, `phases/phase_1/epic_<last>/epic.md` (E2E Testing epic) | Nunca |
| **E. Per-Epic Plan + Tasks + Manifest** (loop por epic) | `plan_epic_converge` + `create_issues_from_plan_swarm` (sin convergence loops) | Epic.md + bootstrap context | Para cada epic feature: `phases/phase_1/epic_<M>/plan.md`, `tasks/task_*.md`, `swarm-manifest.json`, branch `feat/P1.E<M>` creada | Nunca |

### 3.2 Esqueleto del comando

```markdown
---
name: lite_plan
description: Condensed planning for 2-5 features on existing codebase, single phase, multi-epic
---

# Stage A: Introspection + Capture
- eigen-lite get-context lite_plan --json
- Run introspection (language-profiles skill, scan manifests, detect entities)
- Interactive: 3-5 questions to capture feature set + verify external deps
- Save: feature_summary.md (internal), update state.lite_plan.stages_completed += ["A"]

# Stage B: Single-Phase Manifest Generation
- Apply time_split heuristics (single phase forced)
- Skip: cross-phase deps, bottleneck analysis, phase balance
- Keep: DAG cycle detection, cluster integrity, E2E layer verification, containerization keyword check
- Output: phase_1_manifest.md
- Save: state.lite_plan.stages_completed += ["B"]

# Stage C: Bootstrap Delta (CONDITIONAL)
- IF delta=0 (no infra changes): synthesize bootstrap-report.json from introspection only
- ELSE: invoke bootstrapper inline (NO 4 reviewers; 1 inline self-check)
- Output: bootstrap-report.json
- Save: state.lite_plan.stages_completed += ["C"]

# Stage D: Multi-Epic Decomposition
- Decide epic count based on feature orthogonality (1-5 feature epics + 1 E2E Testing epic)
- Generate epic.md for each feature epic + E2E Testing epic (always last)
- Generate epic_manifest.json with execution_order = [P1.E1, P1.E2, ..., P1.E<last>]
- Generate phase_e2e_config.json with epic_validation_scenarios per feature epic
- Save: state.lite_plan.stages_completed += ["D"]
- Initialize state.epics dict with N entries

# Stage E: Per-Epic Plan + Tasks + Manifest (LOOP)
For each feature epic E<M> (sequentially):
  - Generate plan.md with Parallelization Strategy (mandatory)
  - Verify external deps inline
  - Decompose into tasks (typically 2-7 + INT)
  - Generate swarm-manifest.json (full schema)
  - Create integration branch feat/P1.E<M>
  - Save: state.lite_plan.stages_completed += [f"E:{M}"]

(E2E Testing epic does NOT need plan.md / tasks pre-generated; lite_swarm handles that when its turn comes.)

# Finalization
- eigen-lite complete lite_plan --converged true --epic-count <N>
- eigen-lite commit-state --message "lite_plan: phase 1 ready with <N> epics for swarm"
```

### 3.3 Punto crítico: artefactos compatibles con workers reusados

Como lite mantiene la estructura `phases/phase_1/epic_<M>/` y branch `feat/P1.E<M>`, **los workers de eigen-squared funcionan sin modificación** sobre los artefactos generados por lite_plan. Esto se valida con tests de integración en Sprint 5 usando un repo real con Docker (no mocks).

### 3.4 Decisión de cuántos epics generar

**Heurística para Stage D:**
- Features con dependencias compartidas / mismo cluster → mismo epic.
- Features ortogonales (sin dependencias entre sí, dominios distintos) → epics separados.
- Si todas las features son del mismo dominio sin coupling → 1 epic feature.
- Si hay cambios infra (Stage C ran) → estos van en E1 antes que features que dependan de ellos.
- E2E Testing epic siempre es el último.

**Default conservador:** preferir agrupar (menos epics) cuando hay duda. Es más fácil que el usuario diga "quiero más paralelismo" en una iteración futura que recuperarse de un epic split mal hecho.

---

## 4 · Diseño de `lite_swarm` y `lite_review`

### 4.1 lite_swarm

**Estrategia:** Copia adaptada de `orchestrate_swarm.md` (no invocación via Skill).

**Cambios respecto a squared:**
- CLI calls: `eigen-lite get-context lite_swarm --epic <M>` en lugar de `eigen-squared get-context orchestrate_swarm --phase <N> --epic <M>`. (Phase es siempre 1 implícita en lite.)
- Branch verification: `feat/P1.E<M>` (mantenida).
- Skill invocations: `Skill("eigen-squared:design_validation_tests_swarm")` y `Skill("eigen-squared:code_from_validation_tests_swarm")` ← validar que cross-plugin funciona en spike.
- Estado: actualiza `state.epics["<M>"].lite_swarm.{status, pr_url, pr_number, manifest_path}`.

**Lógica core (95% reusable):** spawn de teammates por waves, message reaction, integration step, E2E fix loop, PR creation.

**Determine_next:** después de plan converged, lite_swarm corre para epic 1, luego (post-review converged) epic 2, etc., secuencialmente.

### 4.2 lite_review

**Estrategia:** Copia adaptada de `review_swarm_pr.md`.

**Cambios respecto a squared:**
- CLI calls: `eigen-lite get-context lite_review --epic <M>`, `eigen-lite complete lite_review --epic <M>`, `eigen-lite mark-converged lite_swarm --epic <M>`.
- Estado: actualiza `state.epics["<M>"].lite_review.{review_iteration, findings_summary, convergence}` y `state.epics["<M>"].lite_swarm.status`.
- Convergence rules: idénticas (P1=0 AND P2=0 → CONVERGE).
- Auto-merge en convergencia: idéntico, en branch `feat/P1.E<M>`.
- Posible reducción: 3 reviewers en vez de 5 para PRs pequeños (decisión de Sprint 4; conservador = mantener 5 inicialmente).

**Lógica core (95% reusable):** scope-aware review agent spawn, finding triage, fixup task creation, manifest update, lesson extraction.

---

## 5 · Diseño del CLI `eigen-lite`

### 5.1 Schema de `pipeline_state.json` lite (multi-epic)

```json
{
  "schema_version": "1.0.0",
  "feature_set": "<name>",
  "phase": 1,
  "epic_count": 3,
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "state": {
    "lite_plan": {
      "status": "not_started|in_progress|completed",
      "iteration": 0,
      "stages_completed": [],
      "convergence": {"converged": false, "decided_by": null, "decided_at": null, "reason": null},
      "output_paths": {
        "phase_manifest": null,
        "bootstrap_report": null,
        "epic_manifest": null,
        "phase_e2e_config": null
      },
      "findings_summary": {"high": 0, "medium": 0, "low": 0}
    },
    "epics": {
      "1": {
        "epic_path": "phases/phase_1/epic_1/",
        "epic_file": "phases/phase_1/epic_1/epic.md",
        "plan_file": "phases/phase_1/epic_1/plan.md",
        "swarm_manifest": "phases/phase_1/epic_1/swarm-manifest.json",
        "is_e2e_epic": false,
        "lite_swarm": {
          "status": "not_started|pr_created|iterating|converged",
          "pr_url": null,
          "pr_number": null,
          "integration_branch": "feat/P1.E1",
          "convergence": {...}
        },
        "lite_review": {
          "status": "not_started|in_progress|complete",
          "review_iteration": 0,
          "findings_summary": {"p1": 0, "p2": 0, "p3": 0},
          "convergence": {...},
          "review_reports": []
        }
      },
      "2": {...},
      "3": {
        "is_e2e_epic": true,
        ...
      }
    }
  },
  "recommendations": []
}
```

### 5.2 Subcomandos CLI (14 totales)

| Subcomando | Origen | Adaptación |
|------------|--------|------------|
| `init` | Nuevo (basado en squared init) | Crea `LitePipelineState` con plan slot vacío y epics dict vacío |
| `status` | Nuevo (basado en squared status) | Muestra plan progress + epics progress |
| `next` | Nuevo (basado en squared next) | Llama `determine_next_lite()` |
| `get-context` | Nuevo (basado en squared get-context) | Routing por (lite_plan/lite_swarm/lite_review), accepta `--epic` |
| `complete` | Nuevo (basado en squared complete) | Mutaciones flat-schema con `--epic` arg |
| `mark-converged` | Nuevo (basado en squared mark-converged) | Accepta `--epic` |
| `set-swarm-status` | Nuevo (basado en squared set-swarm-status) | Requiere `--epic` |
| `add-review-report` | Nuevo (basado en squared add-review-report) | Requiere `--epic` |
| `init-epics` | Nuevo (no existe en squared) | Lazy-init de `state.epics` dict tras Stage D de lite_plan |
| `validate` | Nuevo validator + dispatch reusado | `validate_state_lite()` |
| `sync` | Reusado de eigen-core | Sin cambios |
| `commit-state` | Reusado de eigen-core | Sin cambios |
| `checkout-branch` | Reusado de eigen-core | Genera `feat/P1.E<M>` desde `--epic` |
| `write-env` | Reusado, lee `.eigen-lite/env` | Path adaptado |
| `install` | Adaptado, crea `.eigen-lite/` | Path adaptado |
| `schedule-next` | Adaptado, usa COMMAND_TO_SKILL_LITE | Mapping nuevo |

### 5.3 `determine_next_lite()` (transitions_lite.py)

```python
def determine_next_lite(state: dict) -> Optional[tuple[str, dict]]:
    s = state.get("state", {})

    # Stage 1: lite_plan must converge first
    plan = s.get("lite_plan", {})
    if not plan.get("convergence", {}).get("converged"):
        return ("lite_plan", {"feature_set": state.get("feature_set")})

    # Stage 2: walk epics sequentially
    epics = s.get("epics", {})
    for epic_id_str in sorted(epics.keys(), key=int):
        epic_id = int(epic_id_str)
        epic = epics[epic_id_str]
        swarm = epic.get("lite_swarm", {})
        review = epic.get("lite_review", {})

        swarm_status = swarm.get("status")

        # Need to run lite_swarm
        if swarm_status == "not_started":
            return ("lite_swarm", {
                "epic": epic_id,
                "manifest_path": epic["swarm_manifest"],
                "branch": epic["lite_swarm"]["integration_branch"],
            })

        # PR exists, need review
        if swarm_status in ("pr_created", "iterating"):
            if not review.get("convergence", {}).get("converged"):
                return ("lite_review", {
                    "epic": epic_id,
                    "pr_number": swarm.get("pr_number"),
                })
            # else: review converged, swarm should be marked converged too on auto-merge
            # → continue to next epic

        # epic converged → continue iteration to next

    return None  # All epics done; pipeline complete
```

Lineal con loop sobre epics. ~25 unit tests cubren todos los caminos (similar al test_transitions.py de squared).

---

## 6 · Diseño del watchdog `eigen-lite-watchdog`

### 6.1 Cambios respecto a `eigen-watchdog.sh`

```bash
#!/bin/bash
# eigen-lite-watchdog — adapted from eigen-watchdog
PROJECT_ROOT="${1:-}"
ENV_FILE="$PROJECT_ROOT/.eigen-lite/env"            # was: .eigen/env
LOCKFILE="$PROJECT_ROOT/.eigen-lite/watchdog.lock"  # was: .eigen/watchdog.lock

# ... source ENV_FILE ...

# Check running task (filtered by working_dir == EIGEN_LITE_ROOT)
RUNNING=$(curl -sf "$CLAUDE_TASKS_API/api/v1/tasks" 2>/dev/null | python3 -c "
import os, sys, json
root = os.environ['EIGEN_LITE_ROOT']
# ... same logic as squared, just different env var ...
")

# Use lite CLI
NEXT_JSON=$(eigen-lite next --json 2>"$NEXT_ERR") || NEXT_EXIT=$?

# Task name format
EXPECTED_NAME="eigen-lite: <command> [E<M>]"  # No phase prefix; epic optional

# Schedule via lite CLI
eigen-lite schedule-next $EXTRA_ARGS
```

### 6.2 `COMMAND_TO_SKILL_LITE` mapping

```python
COMMAND_TO_SKILL_LITE = {
    "lite_plan": "eigen-lite:lite_plan",
    "lite_swarm": "eigen-lite:lite_swarm",
    "lite_review": "eigen-lite:lite_review",
}
```

### 6.3 Coexistencia con `eigen-watchdog`

**Sin conflictos:** lockfiles, env files, hook_log.jsonl están en directorios separados (`.eigen/` vs `.eigen-lite/`). Dos cron entries pueden coexistir en el mismo crontab apuntando a diferentes binarios. claude-tasks API filtra por `working_dir`, así que dos proyectos con diferentes roots no se interfieren.

**Caso degenerado:** mismo repo con ambos plugins activos — desaconsejado pero técnicamente posible (los watchdogs no se pisan, pero los humanos sí se confunden). Documentar en README.

---

## 7 · Política de testing

### 7.1 Principios

- **Unit tests:** pueden usar mocks libremente (es su naturaleza).
- **Integration tests:** **deben usar repo real + Docker containers**, nada de mocks.
- **E2E tests:** **deben usar repo real + Docker containers**, nada de mocks.
- **Mocks solo en casos muy concretos** donde no haya alternativa razonable (e.g., simular fallo de red intermitente que no se puede reproducir con Docker).

Esta política es coherente con la filosofía de testing de eigen-squared (`design_validation_tests_swarm.md` ya prohíbe SQLite-for-Postgres y similares fakes).

### 7.2 Implicaciones prácticas

- **Tests de claude-tasks API integration:** Sprint 3 debe levantar un servidor de claude-tasks real (Docker container o local instance) para validar el flujo completo `schedule_next → POST /api/v1/tasks → confirmation`.
- **Tests de watchdog:** Sprint 3 incluye un harness que arranca el watchdog real (no script de prueba), espera al cron tick, valida el comportamiento completo. Esto puede ser lento (~5-10 minutos por test); paralelizable.
- **Tests de lite_plan end-to-end:** Sprint 5 usa un repo de prueba real (e.g., un FastAPI minimal con Postgres en Docker) y corre `lite_plan` completo, validando todos los artefactos generados.
- **Tests de pipeline completo:** Sprint 6 corre `lite_plan → lite_swarm → lite_review` end-to-end en un repo real, generando una PR real (o contra un GitHub mock como `gh-mock` solo si GitHub real es impracticable).

### 7.3 CI/CD setup

- GitHub Actions con jobs separados:
  - `unit-tests` (rápido, ~30s)
  - `integration-tests` (mediano, ~10 min, levanta Docker)
  - `e2e-tests` (lento, ~30 min, opcional en PRs, obligatorio en main)
- Docker compose file en `tests/docker-compose.yml` con servicios necesarios (Postgres, RabbitMQ, claude-tasks API mock-server si es necesario).

---

## 8 · Plan de implementación por sprints

### Sprint 0 — Spikes de validación (1 día)

**Objetivo:** Eliminar las incertidumbres bloqueantes antes de invertir esfuerzo serio.

| Spike | Tiempo | Criterio de éxito | Plan B si falla |
|-------|--------|-------------------|-----------------|
| **S0.1 — Cross-plugin Skill referencing** | 1-2h | Crear `plugins/eigen-spike-test/` con un comando que invoque `Skill("eigen-squared:python-expert")`; verificar que se carga correctamente | Symlinks a SKILL.md o duplicación con nota en README |
| **S0.2 — `plugin.json dependencies` + `marketplace.json` registration** | 1-2h | Registrar plugin de spike con dependencia declarada; verificar que Claude Code la resuelve (o documentar que no se valida pero coexiste) | Documentar prerequisite en README de eigen-lite |
| **S0.3 — Workers funcionan en `feat/P1.E1` desde orchestrator distinto** | 2h | Hand-craft mínimo `swarm-manifest.json` + branch `feat/P1.E1`; spawnear worker con prompt-template extraído de `orchestrate_swarm.md` (líneas 256-368); verificar que pasa branch verification y completa Step A | Workers requerirían modificación; replantear arquitectura completa |
| **S0.4 — Sync de versiones** | 0.5h | `plugin.json` y `marketplace.json` consistentes para eigen-squared | N/A (es solo cleanup) |
| **S0.5 — Validar GitHub Actions baseline** | 1h | Crear workflow básico que corra los 119 tests existentes de squared | Documentar comando manual |

**Entregables de Sprint 0:**
- Documento `docs/spike-results-sprint-0.md` con resultados de cada spike y plan B activado si aplica.
- Repo limpio con versiones sincronizadas.
- Spike test plugin **eliminado** después de validación (no se merge a main).

**Decisión gate:** si S0.1, S0.2 o S0.3 fallan y el Plan B compromete significativamente la propuesta, **revisar con usuario antes de continuar**.

### Sprint 1 — Extracción de `eigen-core` (2-3 días)

**Objetivo:** Crear librería compartida sin romper eigen-squared.

1. Crear `plugins/eigen-core/` con estructura:
   ```
   plugins/eigen-core/
   ├── .claude-plugin/
   │   └── plugin.json (declared as utility, no commands)
   ├── cli/
   │   ├── git_ops.py            (movido tal cual)
   │   ├── scheduler.py          (refactorizado: command_to_skill_map como param)
   │   ├── state_io.py           (load_state, save_state, resolve_state_file genéricos)
   │   ├── base_models.py        (Convergence, FindingsSummary, MainCommandState)
   │   └── tests/
   │       └── ... (tests movidos)
   └── README.md
   ```
2. Refactorizar `plugins/eigen-squared/cli/` para importar de `eigen-core` donde aplique:
   - `from eigen_core.cli.git_ops import sync, commit_state, ...`
   - `from eigen_core.cli.scheduler import check_retry, schedule_command`
   - `from eigen_core.cli.base_models import Convergence, FindingsSummary, MainCommandState`
3. **Validar regresión:** correr los 119 tests de squared. Todos deben pasar.
4. Si surgen issues (e.g., `scheduler.schedule_command` ahora recibe `skill_map` como param): ajustar.
5. **Test de integración (sin mocks):** levantar claude-tasks API real, ejecutar un `schedule_command` del CLI refactorizado, validar que la tarea aparece en la API.

**Riesgo:** la refactorización podría romper algo sutil. Mitigación: hacerlo en branch separada con CI completo antes de merge.

**Entregables:**
- `plugins/eigen-core/` creado con módulos extraídos.
- `plugins/eigen-squared/cli/` refactorizado, todos los 119 tests pasando + 1 integration test nuevo con claude-tasks real.
- PR mergeable, sin breaking changes para usuarios actuales de eigen-squared.

### Sprint 2 — Foundation eigen-lite CLI (3-4 días)

**Objetivo:** State machine + models + CLI esqueleto, todo TDD.

1. `plugins/eigen-lite/.claude-plugin/plugin.json` — version 0.1.0, `"dependencies": ["eigen-squared", {"name": "eigen-core", "version": "~1.0.0"}]` (validado en S0.2).
2. `plugins/eigen-lite/cli/__init__.py`, `__main__.py`, `main.py` — argparse dispatcher con 14 subcomandos.
3. `plugins/eigen-lite/cli/models_lite.py` — 5 dataclasses planas + tests (~30 tests):
   - `LiteConvergence` (alias de `eigen_core.base_models.Convergence`)
   - `LitePlanState`
   - `LiteSwarmExecution`
   - `LiteReviewState`
   - `LiteEpicState` (contiene swarm + review)
   - `LitePipelineState` (raíz con `lite_plan` + `epics` dict)
4. `plugins/eigen-lite/cli/transitions_lite.py` — `determine_next_lite()` + `make_context_key_lite()` + `resolve_branch_lite()` + tests (~25 tests).
5. `plugins/eigen-lite/cli/subcommands/__init__.py` — handlers TDD para todos los subcomandos (~35 tests):
   - Tests por subcomando, validando mutaciones del state, manejo de args, error cases.

**Política de tests:** unit tests con mocks OK (estos son tests de lógica de CLI). Tests de integración con git real (sin mocks de subprocess) para `cmd_commit_state`, `cmd_sync`, `cmd_checkout_branch`.

**Entregables:**
- ~90 tests pasando (30 models + 25 transitions + 35 subcommands).
- CLI ejecutable: `python -m cli init --feature-set test --epic-count 0` funciona.
- 0 referencias a comandos lite todavía (solo state machine + scaffolding).

### Sprint 3 — Watchdog y scheduling (2 días)

**Objetivo:** watchdog autónomo end-to-end, validado contra claude-tasks API real.

1. `plugins/eigen-lite/cli/eigen-lite-watchdog.sh` — adaptado de eigen-watchdog.sh.
2. Subcomando `eigen-lite install` que crea `.eigen-lite/`, instala watchdog binary en `~/.local/bin/`, agrega cron entry.
3. Subcomando `eigen-lite schedule-next` con `COMMAND_TO_SKILL_LITE`.
4. **Tests de integración (Docker required):**
   - Levantar instancia local de claude-tasks API
   - Crear `pipeline_state.json` mínimo, ejecutar `eigen-lite schedule-next`, validar que la tarea aparece en API
   - Ejecutar el watchdog shell script directamente, validar lock acquisition, retry detection, scheduling
   - Tests de coexistencia: dos watchdogs (squared + lite) en el mismo cron, diferentes proyectos, validar que no interfieren

**Entregables:**
- ~15 tests de integración con claude-tasks real pasando.
- Watchdog instalable y funcional en una máquina de desarrollo.
- Documento `docs/eigen-lite-watchdog-troubleshooting.md` con casos comunes.

### Sprint 4 — `lite_swarm.md` + `lite_review.md` (3 días)

**Objetivo:** comandos slash de orquestación copy-adapted de squared, funcionando contra artefactos hand-crafted.

1. Copiar `orchestrate_swarm.md` → `plugins/eigen-lite/commands/lite_swarm.md`. Adaptar:
   - CLI calls (`eigen-squared` → `eigen-lite`)
   - State paths (nested → flat con `--epic`)
   - Mantener `feat/P1.E<M>` y skill invocations cross-plugin
2. Copiar `review_swarm_pr.md` → `plugins/eigen-lite/commands/lite_review.md`. Adaptar análogamente.
3. **Test de integración (repo real, sin mocks):**
   - Crear repo de prueba minimal con Docker (FastAPI + Postgres)
   - Hand-craft `swarm-manifest.json` con 2 tasks simples + INT
   - Crear branch `feat/P1.E1` con artefactos
   - Ejecutar `lite_swarm`, validar PR generado
   - Ejecutar `lite_review`, validar convergencia o creación de fixup tasks
   - Iterar hasta auto-merge

**Decisión técnica pendiente (Sprint 4):** ¿reducir reviewers de 5 a 3 para PRs pequeños? **Decisión inicial: mantener 5**, optimizar después con datos.

**Entregables:**
- `lite_swarm.md` y `lite_review.md` validados end-to-end con repo real.
- Test fixture de repo minimal documentado en `tests/fixtures/minimal-fastapi/`.
- ~5-8 tests de integración E2E con Docker.

### Sprint 5 — `lite_plan.md` (5-6 días, el más grande)

**Objetivo:** comando lite_plan completo con stages incrementales y checkpoints.

Implementación incremental por Stage:

1. **Stage A** (Introspection + Capture): 1 día
   - Skill `language-profiles` invocation
   - Repo introspection: scan manifests, detect entities, list domains
   - Interactive interview: 3-5 features, dependencies, external deps
   - Output: `feature_summary.md` interno, language profile cargado
2. **Stage B** (Phase Manifest): 1 día
   - Apply time_split simplified for N=1
   - Output: `phase_1_manifest.md` con secciones requeridas
3. **Stage C** (Bootstrap Delta — conditional): 1.5 días
   - Detect delta vs existing repo
   - If delta=0: synthesize bootstrap-report.json desde introspección
   - If delta>0: invoke bootstrapper inline (no convergence loop)
   - Output: `bootstrap-report.json`
4. **Stage D** (Multi-Epic Decomposition): 1 día
   - Heurísticas para epic count basado en orthogonality
   - Generate epic.md per feature epic + E2E Testing epic
   - Generate `epic_manifest.json`, `phase_e2e_config.json`
   - Initialize `state.epics` dict
5. **Stage E** (Per-Epic Plan + Tasks + Manifest, loop): 1 día
   - For each feature epic: plan.md + tasks/*.md + swarm-manifest.json + integration branch
   - Idempotent: re-run resumes from last incomplete epic
6. **Tests de integración (repo real, sin mocks)**: 0.5 día
   - Repo de prueba real (puede ser el mismo de Sprint 4 ampliado)
   - Definir 3-5 features ficticias
   - Correr `lite_plan` completo
   - Verificar que **todos los artefactos generados son consumibles por `lite_swarm`** (ejecutar lite_swarm como dry-run para validar manifest)
   - Verificar que después de fallo a mitad (e.g., kill después de Stage C), re-ejecutar resume correctamente

**Test crítico de Sprint 5 (E2E completo):** end-to-end usando repo real con Docker:
- Definir 3 features ortogonales (e.g., add user CRUD, add product CRUD, add order CRUD en FastAPI/Postgres)
- Correr `lite_plan` → 3 feature epics + 1 E2E epic
- Correr `lite_swarm` epic por epic
- Correr `lite_review` después de cada PR
- Validar que el código resultante pasa tests E2E reales contra Postgres dockerizado

**Entregables:**
- `lite_plan.md` completo, idempotente, con checkpoints.
- ~10-15 tests de integración E2E con Docker.
- Documento `docs/lite-plan-internals.md` explicando los stages.

### Sprint 6 — Polish y release (2 días)

1. `plugins/eigen-lite/commands/lite_start.md` — análogo a `eigen_start` para inicialización (interview corto, install CLI, install watchdog).
2. `plugins/eigen-lite/README.md` con:
   - Heurísticas para elegir squared vs lite (decision tree)
   - Quick start guide (5 minutos)
   - CLI reference (14 subcommands)
   - Schema docs
   - Coexistencia con eigen-squared documentada
3. Actualizar `marketplace.json` con entrada eigen-lite y eigen-core.
4. Actualizar `README.md` raíz del repo con sección sobre eigen-lite.
5. **Test de release E2E (repo real)**: ejecutar pipeline completo en repo real (no fixture de prueba) — idealmente uno del usuario o un fork de un open source pequeño.
6. Bump versión a 1.0.0 cuando todo el E2E pase.

**Entregables:**
- Plugin lite instalable y funcional end-to-end.
- Documentación completa.
- Smoke test E2E en repo real documentado.

### Resumen de tiempos por sprint

| Sprint | Duración | Acumulado |
|--------|----------|-----------|
| 0. Spikes | 1 día | 1 día |
| 1. eigen-core | 2-3 días | 3-4 días |
| 2. Foundation CLI | 3-4 días | 6-8 días |
| 3. Watchdog | 2 días | 8-10 días |
| 4. lite_swarm + lite_review | 3 días | 11-13 días |
| 5. lite_plan | 5-6 días | 16-19 días |
| 6. Polish + release | 2 días | 18-21 días |

**Total realista:** 3-4 semanas de trabajo focalizado.

---

## 9 · Preguntas resueltas con el usuario

| # | Pregunta | Decisión |
|---|----------|----------|
| 1 | ¿Sintaxis `Skill("plugin-name:skill-name")` funciona cross-plugin? | Validar en Sprint 0 (S0.1). Plan B documentado. |
| 2 | ¿`plugin.json` soporta `dependencies`? | **VALIDADO en S0.2.** Campo es `dependencies` (array, semver), v2.1.110+. |
| 3 | ¿Reducir reviewers en lite_review (5→3)? | **Decisión:** mantener 5 inicialmente, optimizar después con datos. |
| 4 | ¿lite_plan permite N>1 features con 2+ epics? | **DECISIÓN DEL USUARIO:** Sí, lite gestiona **multi-epic en single-phase**. 5 features ortogonales pueden tener 1 epic cada una. |
| 5 | ¿Coexistencia squared+lite en mismo repo? | **Decisión:** documentar como técnicamente posible pero desaconsejado. |
| 6 | ¿Tests de integración: repo real o mock? | **DECISIÓN DEL USUARIO:** Integration y E2E **siempre repo real + Docker**. Mocks solo en casos muy concretos sin alternativa. |
| 7 | ¿lite_plan idempotente o from-scratch? | **Decisión:** idempotente con `stages_completed[]` (incluyendo per-epic en Stage E como `E:1`, `E:2`...). |

---

## 10 · Anexos: estructura final del repo

```
plugins/
├── eigen-core/                          # Nuevo
│   ├── .claude-plugin/plugin.json
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── git_ops.py                   # Movido de squared
│   │   ├── scheduler.py                 # Refactorizado de squared
│   │   ├── state_io.py                  # Genéricos extraídos
│   │   ├── base_models.py               # Convergence, FindingsSummary, MainCommandState
│   │   └── tests/
│   └── README.md
│
├── eigen-squared/                       # Refactorizado para usar eigen-core
│   ├── .claude-plugin/plugin.json       # Versión actualizada
│   ├── cli/
│   │   ├── ... (sin cambios estructurales, solo imports)
│   │   └── tests/                       # 119 tests + 1 nuevo de integración
│   ├── commands/                        # Sin cambios
│   ├── skills/                          # Sin cambios
│   ├── agents/                          # Sin cambios
│   └── README.md
│
└── eigen-lite/                          # Nuevo
    ├── .claude-plugin/plugin.json       # version 1.0.0, dependencies: [eigen-squared, eigen-core]
    ├── cli/
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── main.py                      # argparse dispatcher (14 subcommands)
    │   ├── models_lite.py               # 5 dataclasses
    │   ├── transitions_lite.py          # determine_next_lite, make_context_key_lite
    │   ├── subcommands/__init__.py      # 14 handlers
    │   ├── eigen-lite-watchdog.sh       # Watchdog adaptado
    │   └── tests/                       # ~120 tests (unit + integration con Docker)
    ├── commands/
    │   ├── lite_start.md                # Interactive launcher
    │   ├── lite_plan.md                 # Condensa 5+ comandos de squared
    │   ├── lite_swarm.md                # Copy-adapted de orchestrate_swarm
    │   └── lite_review.md               # Copy-adapted de review_swarm_pr
    ├── agents/                          # Vacío inicialmente; reusar eigen-squared
    ├── skills/                          # Vacío inicialmente; reusar eigen-squared
    └── README.md

.claude-plugin/
└── marketplace.json                     # Actualizado con eigen-core y eigen-lite

docs/
├── plan-eigen-lite-design-and-implementation.md  # ESTE ARCHIVO
├── spike-results-sprint-0.md                     # Generado tras Sprint 0
├── eigen-lite-watchdog-troubleshooting.md        # Generado en Sprint 3
└── lite-plan-internals.md                        # Generado en Sprint 5

tests/
├── docker-compose.yml                   # Servicios para integration/E2E tests
└── fixtures/
    ├── minimal-fastapi/                 # Repo de prueba para lite_swarm/review
    └── multi-epic-fixture/              # Repo de prueba para lite_plan completo
```

---

## 11 · Próximos pasos inmediatos

1. **Revisar este documento** (usuario + Codex) y aprobar.
2. **Ejecutar Sprint 0** (1 día) — los 5 spikes de validación.
3. **Decisión gate** después de Sprint 0: si algún Plan B compromete la propuesta, replanificar con usuario.
4. **Si todo OK:** proceder con Sprint 1 (extracción de eigen-core).

**Documento mantenido en:** `docs/plan-eigen-lite-design-and-implementation.md`
**Trazabilidad:** todos los hallazgos derivados de 11 análisis paralelos ejecutados el 2026-04-20 sobre la versión 3.4.6 de eigen-squared.
