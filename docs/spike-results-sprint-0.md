# Sprint 0 — Resultados de spikes de validación

> **Fecha:** 2026-04-20
> **Plan referenciado:** [`plan-eigen-lite-design-and-implementation.md`](./plan-eigen-lite-design-and-implementation.md)
> **Resultado global:** ✅ **GREEN** — todos los spikes resueltos sin activar Plan B. Sprint 1 (extracción de `eigen-core`) puede comenzar.
> **Caveat:** S0.1, S0.2 y S0.3 quedan **documentalmente validados**. La verificación runtime end-to-end requiere ejecutar el plugin de spike (`eigen-spike-test`) en una sesión interactiva de Claude Code antes de cerrar Sprint 0 con confianza completa.

---

## S0.1 — Cross-plugin `Skill()` referencing

**Estado:** ✅ VALIDATED (vía documentación oficial; pendiente verificación runtime con `eigen-spike-test`).

**Hallazgo:** Claude Code soporta `Skill("plugin-name:skill-name", args: "...")` cross-plugin. Los skills se namespacian automáticamente como `plugin-name:skill-name`, eliminando colisiones. La sintaxis ya está en uso productivo dentro de `eigen-squared` (ver `commands/orchestrate_swarm.md:311,315,322,323`).

**Fuente:** [code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md), [plugins-reference.md](https://code.claude.com/docs/en/plugins-reference.md).

**Implicación para eigen-lite:** `lite_swarm.md` puede invocar `Skill("eigen-squared:design_validation_tests_swarm")` y `Skill("eigen-squared:code_from_validation_tests_swarm")` directamente, sin duplicar SKILL.md.

**Plan B (no activado):** duplicación de SKILL.md o symlinks. Documentado en plan §R3 por si la verificación runtime falla.

**Artefacto entregado:** `plugins/eigen-spike-test/commands/spike_validate.md` — comando interactivo que ejecuta `Skill("eigen-squared:python-expert")` y reporta PASS/FAIL.

---

## S0.2 — Declaración de dependencias entre plugins

**Estado:** ✅ VALIDATED — con **corrección importante** al plan original.

**Hallazgo:** El campo correcto NO es `depends_on` (como asumía el plan), es **`dependencies`**, introducido en Claude Code v2.1.110+. Schema:

```json
{
  "name": "eigen-lite",
  "dependencies": [
    "eigen-squared",
    { "name": "eigen-core", "version": "~1.0.0" }
  ]
}
```

Soporta semver ranges (`~1.0.0`, `^1.0`, `>=1.4`). Sin constraint, trackea `latest`.

**Comportamiento:**
- Resolución lazy: plugins cargan al primer uso (skill invocado, comando ejecutado).
- Si A es dependencia de B, A se garantiza resuelto antes de que B esté disponible.
- Errores explícitos disponibles en `claude plugin list --json` (`range-conflict`, `dependency-version-unsatisfied`, `no-matching-tag`).

**Fuente:** [code.claude.com/docs/en/plugin-dependencies.md](https://code.claude.com/docs/en/plugin-dependencies.md).

**Acción requerida en plan:** actualizar todas las referencias `depends_on` → `dependencies` en `plan-eigen-lite-design-and-implementation.md` (Sprint 2 §Foundation, anexo §10, tabla §9).

**Artefacto entregado:** `plugins/eigen-spike-test/.claude-plugin/plugin.json` declara `"dependencies": ["eigen-squared"]`.

**Plan B (no activado):** README warning indicando prerequisite. Innecesario porque `dependencies` está documentado y soportado.

---

## S0.3 — Workers funcionan desde orchestrator no-`orchestrate_swarm`

**Estado:** ✅ VALIDATED por análisis estático del spawn template; pendiente verificación runtime.

**Hallazgo:** El spawn prompt de workers (`orchestrate_swarm.md:261-367`) es una **plantilla totalmente parametrizada** — workers no tienen awareness del comando que los spawnea. Solo verifican `git rev-parse --abbrev-ref HEAD` contra el valor literal `feat/P<N>.E<M>` substituido en su prompt.

**Conclusión:** mientras `lite_swarm` substituya `<N>=1` y `<M>=<epic>` correctamente, los workers verán branch esperada `feat/P1.E<M>` y pasarán verificación. **No hay riesgo arquitectónico**; el riesgo era solo aparente.

**Mitigación de diseño confirmada:** mantener naming `feat/P1.E<M>` y estructura `phases/phase_1/epic_<M>/`. Coherente con plan §R1, §R2.

**Artefacto entregado:** `plugins/eigen-spike-test/fixtures/spike-s03/` — fixture mínima con:
- `swarm-manifest.json` con 1 task (`P1.E1.T1: implement add(a,b)`)
- Task spec en `eigen_initiative/phases/phase_1/epic_1/tasks/P1.E1.T1.md`
- README con procedimiento manual paso a paso para que el usuario verifique en sesión Claude Code.

**Plan B (no activado):** modificar workers para aceptar branch como parámetro, o duplicar SKILL.md. Innecesario por análisis del template.

**Caveat de runtime:** la verificación full-stack (worker spawnea, ejecuta Step A + Step B, escribe working notes, respeta file ownership) requiere agent teams habilitado (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, `teammateMode=tmux`). El usuario debe correr el README de `fixtures/spike-s03/` antes de cerrar el spike con confianza completa.

---

## S0.4 — Sync de versiones eigen-squared

**Estado:** ✅ DONE.

**Hallazgo:** `plugin.json` declaraba `3.4.6`, `marketplace.json` declaraba `1.1.0` para la misma entrada `eigen-squared`. Causa de comportamiento impredecible si Claude Code consulta una u otra fuente.

**Acción ejecutada:** `marketplace.json:eigen-squared.version` actualizado a `3.4.6` (commit pendiente).

**Verificación:** `python3 -c "import json; print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'])"` → `3.4.6`.

---

## S0.5 — GitHub Actions baseline

**Estado:** ✅ DONE — workflow creado, validado contra suite local.

**Acción ejecutada:**
- Creado `.github/workflows/eigen-squared-tests.yml`.
- Matrix sobre Python 3.11 / 3.12 / 3.13.
- Trigger en push/PR sobre `master` / `dev` cuando cambian `plugins/eigen-squared/cli/**`.
- Job `unit-tests`: corre `pytest cli/tests/ -v --tb=short`.
- Guard rail: falla si el conteo de tests cae por debajo de 119 (baseline) — protege contra borrado accidental de tests.

**Verificación local (baseline):**
```
.venv/bin/python -m pytest cli/tests/ -q
............................................................................. [ 60%]
...............................................                                [100%]
119 passed in 0.26s
```

**Próximo paso opcional:** push del workflow al remoto y validar primer run en GitHub UI. No bloqueante para Sprint 1.

---

## Decisión gate

| Spike | Resultado | Plan B activado | Compromete propuesta |
|-------|-----------|-----------------|----------------------|
| S0.1 | VALIDATED | No | No |
| S0.2 | VALIDATED (con corrección de campo) | No | No |
| S0.3 | VALIDATED | No | No |
| S0.4 | DONE | N/A | No |
| S0.5 | DONE | N/A | No |

**Decisión:** **GREEN — proceder con Sprint 1 (extracción de eigen-core)** sin replan con usuario.

**Acciones de cleanup pendientes (al cerrar Sprint 0 después de verificación runtime):**

1. Validar runtime de S0.1, S0.2, S0.3 ejecutando el plugin `eigen-spike-test` en sesión interactiva (instrucciones en `plugins/eigen-spike-test/commands/spike_validate.md` y `plugins/eigen-spike-test/fixtures/spike-s03/README.md`).
2. Eliminar `plugins/eigen-spike-test/` completo.
3. Eliminar entrada `eigen-spike-test` de `marketplace.json`.
4. Actualizar `plan-eigen-lite-design-and-implementation.md` reemplazando `depends_on` → `dependencies` (S0.2 finding).

---

## Lecciones aprendidas (para Sprint 1+)

- **Documentación oficial primero:** dos de cuatro asunciones del plan (`depends_on`, comportamiento de `Skill()`) eran corregibles via 30 minutos de research. Antes de cualquier sprint, validar con docs oficiales para campos exactos y comportamientos.
- **Análisis estático suficiente para riesgos R1/R2:** el spawn prompt template ya es parametrizado; no era un riesgo arquitectónico real, solo apariencia. Mejor leer el código concreto antes de reservar tiempo de spike runtime.
- **Guard rails en CI desde el inicio:** el check de "test count >= baseline" en `eigen-squared-tests.yml` evita regresiones silenciosas durante la extracción de `eigen-core` en Sprint 1.
