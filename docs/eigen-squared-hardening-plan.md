# Eigen-squared hardening plan

> Plan de parches para cerrar el bug de re-ejecución de `create_issues_from_plan_swarm` tras convergencia (incidente 2026-04-22) y los gaps estructurales detectados en la auditoría de 9 lanes paralelas.

## Contexto e incidente origen

El 2026-04-22 ~02:20 local, el watchdog disparó `create_issues_from_plan_swarm P2.E1` **después** de que `review_swarm_pr` iter 3 había convergido (PR #98 squash-merged como `723fa20` a `origin/dev` a las 02:10:54). Tras eso, 4× `orchestrate_swarm` abortaron con discrepancy report (circuit breaker funcionando).

**Causa raíz**: Stage 7 de `review_swarm_pr` no atómico — el commit de convergencia `d799cb8` quedó solo en `feat/P2.E1`, el squash lo colapsó, `dev` local nunca hizo `git pull`, y `pipeline_state.json` local siguió con `swarm_execution.status: "not_started"`. El watchdog (sin git sync) + `cmd_next` (sin auto-sync) + `determine_next` (gate binario JSON-only) re-lanzaron la cascada.

Auditoría posterior (9 agentes paralelos) detectó ~60 issues distintos, agrupados en 8 patrones estructurales. Tras iteración con el usuario (P1, P2, P4, P7 matizados), el plan quedó en 4 capas.

## Convenciones de trabajo

- **Rama**: `dev` (no `master`). PR al final.
- **Commits**: atómicos, uno por parche, prefijo `eigen-squared: <parche#> <título>` o `eigen-core: ...` según corresponda.
- **Edits**: solo en source (`plugins/eigen-core/eigen_core/` o `plugins/eigen-squared/`). Nunca tocar `_vendored/`.
- **Vendored regen**: automático vía `.githooks/pre-commit` + `tools/vendor-core.sh`. Cubre tanto `eigen-squared/_vendored/` como `eigen-lite/_vendored/`.
- **Watchdog redeploy**: tras cambios en `cli/eigen-watchdog.sh`, correr `/eigen_start` completo o `cp` manual a `~/.local/bin/eigen-watchdog`.
- **eigen-lite**: queda fuera del alcance de este batch. Los parches a eigen-core se le propagan automáticamente via vendor; los parches específicos de eigen-squared no.

## Pre-requisito antes de empezar

- Leer el diff de `79b3e42 feat(review_swarm_pr): allow convergence with residual P3 findings` antes de aplicar **1.6** — modifica el mismo archivo que vamos a tocar.

## Orden de ejecución confirmado

**Capa 1.5 → Capa 1 → Capa 2** (en una sesión de ~7h30min).
Capa 3 diferida (post Phase 3 del proyecto forge).
Capa 4 como tech-debt (ticket, no urgente).

---

## Capa 1 — CRÍTICA (cierra el camino exacto del bug)

| # | Parche | Archivo : líneas | Descripción | Coste |
|---|---|---|---|---|
| 1.1 | Atomic state write | **eigen-squared** `cli/state.py:40-48` | `tempfile.NamedTemporaryFile(dir=parent) + os.replace()` en lugar de `path.write_text`. Elimina JSON corrupto por crash mid-write. | 15min |
| 1.2 | Watchdog pre-tick sync | **eigen-squared** `cli/eigen-watchdog.sh:~50` | `git fetch --quiet origin $EIGEN_BRANCH` + `git pull --ff-only --quiet` antes de `eigen-squared next`. Loguea WARN si ff-only falla. | 15min |
| 1.3 | `cmd_next` auto-sync | **eigen-squared** `cli/subcommands/__init__.py:192-214` | Replicar bloque de `cmd_get_context:220-230` (resolve_branch → sync → reload). Cierra gap del path del watchdog. | 15min |
| 1.4 | `commit_state` empty-branch guard | **eigen-core** `eigen_core/cli/git_ops.py:116-121` | Si `current_branch()` retorna `""` o `"HEAD"` → abort con stderr explícito, return False. | 10min |
| 1.5 | `sync` ff-only + propagar fallo | **eigen-core** `eigen_core/cli/git_ops.py:25-34` + **eigen-squared** `cli/subcommands/__init__.py:1001-1009` | Añadir `--ff-only` al pull. `cmd_sync` retorna exit 1 en fallo (hoy retorna 0 "non-fatal"). | 20min |
| 1.6 | Stage 7.2 fail-fast | **eigen-squared** `commands/review_swarm_pr.md:435-444` | Precondición working tree clean; merge con `\|\| exit 1`; `pull --ff-only` con check; verificación post-pull `status == "converged"` en dev; `branch -D`. ⚠ Revisar vs `79b3e42`. | 30min |

**Total Capa 1: ~1h45min.**

---

## Capa 1.5 — PROPAGACIÓN DE ERRORES (hace visibles los silent failures)

Objetivo: convertir fallos silentes en exit ≠ 0 con stderr útil, para que el LLM que ejecuta los comandos MD pueda reaccionar.

| # | Parche | Archivo : líneas | Descripción | Coste |
|---|---|---|---|---|
| 1.7 | `run_git` emite stderr en fallos | **eigen-core** `eigen_core/cli/git_ops.py:13-22` | Tras `subprocess.run`, si `returncode != 0`: `sys.stderr.write(f"[git {args}] {result.stderr}")`. Hace visible al LLM lo que git ya reportó. | 10min |
| 1.8 | Timeouts en `run_git` | **eigen-core** `eigen_core/cli/git_ops.py:13-22` | `timeout=30` por defecto; `timeout=120` para pull/push. Timeout levanta excepción propagada como error visible. | 15min |
| 1.9 | `cmd_commit_state` propaga exit ≠ 0 | **eigen-squared** `cli/subcommands/__init__.py:983-998` | Si `git_ops.commit_state` retorna False → `return 1` (hoy retorna 0 con print genérico). | 10min |
| 1.10 | `checkout_branch` distingue errores | **eigen-core** `eigen_core/cli/git_ops.py:46-73` | Clean-tree precondition (`git status --porcelain`); si falla `-b` por collision → abort loudly "branch exists, delete or resume"; si falla checkout → `rev-parse --verify origin/<branch>` para distinguir "no existe" de "network/auth"; mensajes distintivos. | 1h |

**Total Capa 1.5: ~1h35min.**

---

## Capa 2 — ALTA (guards cross-sistema)

Guards que el LLM no puede recrear por sí solo (requieren consultas a gh/disco).

| # | Parche | Archivo : líneas | Descripción | Coste |
|---|---|---|---|---|
| 2.1 | Reality-check disco en `determine_next` | **eigen-squared** `cli/transitions.py:176-185` | Antes de devolver `create_issues_from_plan_swarm`, si `manifest_path is None` pero `eigen_initiative/.../epic_M/swarm-manifest.json` existe en disco → tratar como manifest_path presente (reconcilia JSON silenciosamente con realidad). | 30min |
| 2.2 | Guard C en `create_issues_from_plan_swarm` | **eigen-squared** `cli/subcommands/__init__.py:557-573` | `gh pr list --state merged --head feat/P<n>.E<m> --json number --limit 1`. Si devuelve ≥1 → abort con exit 3 (idempotent-noop). No-op si `gh` falta. | 30min |
| 2.3 | Guard `status==pr_created` en orchestrate | **eigen-squared** `cli/subcommands/__init__.py:593-599` | Abort con exit 3 si `sw.status == "pr_created"` Y no es fixup re-run (distinguir via `sw.review_iteration > 0`). | 15min |
| 2.4 | Guard `converged/merged/closed` en review_swarm_pr | **eigen-squared** `cli/subcommands/__init__.py:593-599` | Abort con exit 3 si `sw.convergence.converged == True`. Si `sw.pr_number` existe, `gh pr view <n> --json state` y abort si `MERGED`/`CLOSED`. | 45min |
| 2.5 | Exit code 3 = idempotent-noop | **eigen-squared** watchdog + `cli/subcommands/*` | Convención: exit 3 = "ya hecho, avanza". `eigen-watchdog` trata 3 como "no retry, continue". Distingue guard legítimo de error. | 1h |
| 2.6 | `review_iteration` bump guard | **eigen-squared** `cli/subcommands/__init__.py:773-787` | En `cmd_complete review_swarm_pr`: no incrementar si `sw.convergence.converged == True`. Evita drift entre contador JSON y file names. | 10min |
| 2.7 | `eigen_continue` pre-approval check | **eigen-squared** `commands/eigen_continue.md` + `cli/subcommands/__init__.py` | Antes de `set-phase-review approved`, iterar `pr_number` de la phase y verificar `gh pr view --json state` = `MERGED`. Abort con error si alguno no mergeado. | 45min |

**Total Capa 2: ~4h.**

---

## Capa 3 — MEDIA (defensa en profundidad; diferida)

Post Phase 3 del proyecto forge.

| # | Parche | Archivo : líneas | Descripción | Coste |
|---|---|---|---|---|
| 3.2 | Fix lazy-init TOCTOU plan_epic_converge | **eigen-squared** `cli/subcommands/__init__.py:494-516` | Crear `state.phases[pk].plans[ek] = EpicPlan()` en `cmd_get_context` (hoy lo hace `cmd_complete` al final). Cierra ventana de doble-arranque paralelo. | 20min |
| 3.3 | Fix orden `sync → checkout` | **eigen-squared** `cli/subcommands/__init__.py:222-230` | Hoy: sync de `resolve_branch(...)` ANTES del checkout → puede pullear rama equivocada. Fix: checkout primero, después sync. | 30min |
| 3.4 | Pre-POST dedup + idempotency key | **eigen-core** `eigen_core/cli/scheduler.py:173-245` | Antes de POST: `GET /api/v1/tasks?name=<n>&working_dir=<wd>&enabled=true` y abortar si existe. Añadir `client_request_id = sha256(f"{eigen_root}:{cmd}:{context_key}:{attempt}")` al payload (future-proof aunque claude-tasks lo ignore hoy). | 1h |
| 3.5 | Signal handlers | **eigen-squared** `cli/main.py` | `signal.signal(SIGTERM/SIGINT, handler)` con `try/finally` que hace `save_state({..., interrupted_at: now})`. Post-mortem distingue kill de exit natural. | 1h |
| 3.6 | `.gitattributes` para state.json | **forge** (repo consumer) | `eigen_initiative/phases/pipeline_state.json merge=union`. Evita que conflict markers corrompan JSON en merges. | 15min |

**Quitados respecto al plan original** (tras iteración con usuario):
- `fcntl.flock` universal — argumento P1: watchdog + comando autónomo simultáneos tienen riesgo efectivo bajo.
- "Running state universal" — argumento P2: working notes + git log + PR state cubren parcialmente crash-recovery. El único gap real (entre 7.1 y 7.2) lo cubre el fail-fast de **1.6**.
- "Atomic multi-step wrap" — argumento P4: el LLM que ejecuta el MD puede reaccionar a errores si no son silentes (cubierto por **1.7–1.10**).
- `crash-recovery markers` — argumento del usuario: las working notes por worker + `swarm_execution.{status,review_iteration,pr_number,manifest_path}` + `review_report_iteration_N.md` ya proveen información suficiente para reconstrucción.

**Total Capa 3: ~3h05min.**

---

## Capa 4 — ESTRATÉGICA (tech-debt, no urgente)

| # | Parche | Descripción | Coste |
|---|---|---|---|
| 4.1 | `eigen-squared repair [--dry-run]` | Reconcilia gh PR state ↔ sw.status, detecta PRs mergeadas y marca converged, limpia ramas huérfanas. Elimina rescate manual tras desyncs. | 1 día |
| 4.2 | `GitResult` dataclass | Reemplaza bool returns por enum tipado (UP_TO_DATE, FAST_FORWARDED, DIVERGED, NETWORK_ERROR, ...). Cierra silent failures por tipos. | 1 día |
| 4.3 | Tests ampliados para `git_ops.py` | Hoy existen 77 líneas (`plugins/eigen-core/eigen_core/cli/tests/test_git_ops.py`). Ampliar con fixture `tmp_path` + bare-repo: dirty tree, detached HEAD, diverged branch, missing remote, network timeout. | 4h |
| 4.4 | Invariantes cruzados en `validate_state` | `converged ⇒ status ∈ {converged, completed}`; `pr_number != None ↔ status != not_started`; `manifest_path != None ⇒ file exists on disk`. | 2h |
| 4.5 | Observability estructurada | `run_git` loguea duración; `watchdog.log` como JSONL; `hook_log` captura respuesta HTTP completa. | 3h |

---

## Resumen de horas

| Capa | Tiempo | Cuándo |
|---|---|---|
| 1 — Crítica | 1h45min | **Ahora (sesión actual)** |
| 1.5 — Propagación errores | 1h35min | **Ahora (sesión actual)** |
| 2 — Alta (guards) | 4h | **Ahora (sesión actual)** |
| 3 — Media (defensa) | 3h05min | Post Phase 3 de forge |
| 4 — Estratégica | ~3 días | Tech-debt ticket |

**Sesión actual (Capas 1 + 1.5 + 2)**: ~7h20min, 19 parches atómicos.

## Secuencia de ejecución en la sesión actual

Orden: **1.5 → 1 → 2** (primero visibilidad, después fix del bug, después guards cross-sistema).

**Dentro de Capa 1.5**: 1.7 → 1.8 → 1.10 → 1.9 (core primero, squared después).
**Dentro de Capa 1**: 1.4 → 1.5 → 1.1 → 1.3 → 1.2 → 1.6 (core → state.py → cmd_next → watchdog → MD).
**Dentro de Capa 2**: 2.5 (convención exit 3) → 2.1 → 2.2 → 2.3 → 2.4 → 2.6 → 2.7.

Razón del orden: permite verificar cada parche con los efectos propagados del anterior. El primero (1.7) da stderr visible en git, que ayuda a verificar los parches siguientes que usan git_ops.

## Riesgos conocidos

1. **Conflicto textual en 1.6** con `79b3e42` (residual P3 en review_swarm_pr) — revisar diff antes de aplicar.
2. **Regresión en eigen-lite** por cambios a eigen-core (parches 1.4, 1.5, 1.7, 1.8, 1.10, 3.4). Mitigación: CI de eigen-lite debería detectarlo. Validar tras el primer commit de core.
3. **Exit code 3 (2.5)** cambia contrato del CLI. Revisar cualquier caller no documentado que consuma exit codes.

## Recuperación del incidente 2026-04-22 (ortogonal al plan)

Antes o después de aplicar los parches, el worktree de forge necesita reconciliarse con `origin/dev`:

```bash
crontab -l | grep -v eigen-watchdog | crontab -
atrm 8
cd /home/diegosc-wsl/Projects/misc/forge
git fetch origin
git checkout dev && git reset --hard origin/dev
git branch -D feat/P2.E1
git push origin --delete feat/P2.E1
```

Después: correr `/eigen_start` para redesplegar watchdog actualizado (si aplicado 1.2) o re-añadir cron manualmente.

---

_Documento generado tras auditoría 2026-04-22. Actualizar si el plan cambia._
