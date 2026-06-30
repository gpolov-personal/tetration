# eigen-small — Análisis y diseño: review de specs/goals + ejecución multi-fase no supervisada

> **Estado:** propuesta de diseño (Fork A), pendiente de aprobación antes de implementar.
> **Base:** extiende [`eigen_small_design.md`](./eigen_small_design.md). No modifica los tres comandos existentes (`small_route` · `small_plan` · `small_build`); añade comandos hermanos.
> **Origen:** análisis con 8 subagentes (Opus) sobre la maquinaria de autonomía de `eigen-squared` + evaluación crítica del encaje en `eigen-small`.

---

## 1. Propósito

Evaluar y aterrizar dos capacidades propuestas para eigen-small:

- **(A) Un comando de review interactivo** que ayude a un humano a **entender y validar rápido**, fase a fase, las *specs* y los *goals* (con sus ACs) de un plan — sin leer el super-detalle.
- **(B) Un modo de ejecución secuencial no supervisado** que, *una vez el humano ha validado todas las fases por adelantado*, ejecute `small_build` sobre fase 1 → 2 → 3 de forma secuencial y desatendida, deteniéndose si un build no alcanza su goal tras N intentos.

La tesis central de la propuesta: **reubicar el checkpoint humano al frente** (validar todas las fases antes de construir nada) hace que la ejecución secuencial desatendida sea segura, porque el humano ya confirmó que cada goal es un oráculo fiel de su fase.

---

## 2. La propuesta original (del usuario)

1. Comando de review que recorre las fases, sintetiza specs + goals, y permite validar que están bien planteados (que el goal agrega todas las ACs).
2. Tras validar, "pistoletazo de salida": `small_build` intenta el goal de cada fase hasta N veces; al lograrlo deja **feedback** en un artefacto tipo `pipeline_state`; un **watchdog** lanza la siguiente fase teniendo en cuenta el feedback de la anterior.
3. El enfoque no supervisado es **opt-in** y **se rompe** si un build no alcanza el goal tras N intentos.

---

## 3. Qué hace eigen-squared para la autonomía (hallazgos del análisis)

Condensado de la disección de `plugins/eigen-squared`. Sirve para saber qué reutilizar y qué **no** copiar.

| Mecanismo | Cómo funciona | Veredicto para small |
|---|---|---|
| **Watchdog** (`cli/eigen-watchdog.sh`, `cli/scheduler.py`) | **Cron** (no daemon) cada N min → `flock` por proyecto → git pull `--ff-only` → ¿algo `running`? → `eigen-squared next` → `schedule-next` que hace **POST a un servidor claude-tasks** (no `claude -p`). Requiere `.eigen/env`. | **NO copiar.** Ceremonia que small descartó explícitamente. Innecesario si la ejecución es in-session secuencial. |
| **Máquina de estados** (`cli/transitions.py:77` `determine_next`) | Walk descendente con **gate de orden estricto**: cada nivel hace `return` antes de alcanzar el siguiente; `get-context` rechaza cualquier comando que no sea el "next" calculado. | **NO copiar el gate estricto.** small es permisivo por diseño (`determine_next_small`). |
| **pipeline_state + feedback** (`skills/pipeline-state-schema`, `cli/state.py`) | Árbol de 4 niveles (initiative→phases→epics→swarm). El feedback estructurado vive **fuera** del state (ficheros por comando + `findings_history` del swarm). `feedback_consumed` es **vestigial**. | Tomar solo un **objeto feedback mínimo** si se necesita; evitar el esquema pesado y la matriz de recomendaciones. |
| **Bucles de convergencia** (`*_converge.md`) | Skeleton `draft → [gate ejecutado] → crítica → decidir(converged\|revise) → revise → re-crítica ≤ N`. **N = 2** ("una cota de 2 pasadas no puede oscilar"). Criterio: cero findings high/medium, o gate ejecutado (build real) que **vetar** la convergencia. | El **goal-oracle** de small ya es el gate ejecutado; un re-crítica pass es **redundante** con re-ejecutar el goal. |
| **Transición de fase** (`commands/eigen_continue.md`) | **Gate humano obligatorio.** Resume la fase, emite testing recipe, y solo avanza con confirmación explícita (`APPROVE-DEGRADED` tecleado para fases degradadas). `determine_next` devuelve `None` (stall) hasta `phase_review.status == "approved"`. | **Hallazgo clave** (abajo). |
| **Carry cross-fase** | Seams declarados en `epic_manifest.json` (backward-only DAG). `testing_notes.md` pretende llevar feedback de comportamiento entre fases pero **ningún comando lo lee** → *cable suelto*. | small ya tiene algo **mejor**: el `freeze_ledger.json` (con `kind: frozen\|hook`), explícito y queryable. |

### 3.1 El hallazgo más decisivo

> **Incluso eigen-squared —que sí tiene watchdog— mantiene el salto entre fases como un gate humano obligatorio.** La ejecución es autónoma *dentro* de una fase, nunca *entre* fases (`eigen_continue.md`: *"the pipeline MUST NOT cross phase boundaries without human approval"*).

Esto es el ancla de todo el análisis: automatizar el avance entre fases sin humano es lo único que squared se negó a automatizar. La propuesta original (watchdog que auto-avanza fases) iba justo contra esa decisión.

---

## 4. Evaluación crítica de la propuesta original

| Pieza | Veredicto | Razón |
|---|---|---|
| (A) Comando de review | 🟡 Redundante *como reviewer automático* | Ya existen 3 gates: STOP plan→build, epic-readiness check, cross-cutting critique. El único hueco genuino: **cobertura AC→goal**. |
| (B) "N intentos hasta verde" | 🟢 Ya es implícito | `goal-as-stop-condition` + regression gate ya son "itera hasta verde". Lo único nuevo: un **circuit-breaker** (cota + fallo ruidoso). |
| (B) Feedback artifact | 🔴 No justificado intra-fase | El orquestador es in-session y ya tiene el output rojo; freeze ledger + git lo cubren. (⚠️ y `testing_notes.md` de squared demuestra el anti-patrón: feedback escrito que nadie lee.) |
| (B) Watchdog + auto-advance | 🔴 Reintroduce ceremonia descartada | Cron + claude-tasks + `.eigen/env`; cruza la regla "≥3 fases → defer to squared". |

**Riesgos del auto-advance sin humano entre fases:** envenenamiento de contrato congelado (la fase 1 congela un seam sutilmente mal y la 2 lo hereda read-only), goal que pasa-pero-es-incorrecto propagado, coste desbocado sin gate de degradado, oscilación sin breaker.

---

## 5. La reformulación que cambia el análisis

Las precisiones del usuario resolvieron las objeciones de fondo:

1. **El review no es un reviewer automático**, sino un **gate de comprensión humana**: sintetiza specs + goals para entenderlos rápido y validarlos.
2. **El checkpoint humano no se elimina — se reubica al frente**: validar las specs+goals de *todas* las fases antes de construir. Eso convierte cada goal en un **oráculo de confianza** → mata el riesgo "passes-but-is-wrong".
3. **"No supervisado" ≠ watchdog**: si todo está validado al frente, la ejecución 1→2→3 puede ser un **driver secuencial in-session** (un `--auto` extendido a fases), sin cron ni claude-tasks. Elimina la ceremonia.
4. **No se modifica `small_plan`**: se crea un **comando hermano** con guidelines de horizonte largo (hasta 3 fases).
5. El review es **interactivo y sintetizado**: el usuario entiende todo sin ir al super-detalle; igual para los goals.

### 5.1 El insight que ata el diseño

> **El review interactivo es el sustituto de la convergencia que squared aplica al plan.**

Squared hace su `time_split` como comando *convergido* (≤2 pasadas de autocrítica) porque cortar fases y congelar seams es lo de mayor blast-radius. eigen-small planifica en **una sola pasada** (su credo "one pass, no convergence loops") y pone al **humano como crítico** vía el review. Es coherente y *in-philosophy*: small siempre prefiere un gate humano barato a un loop de convergencia de máquina.

---

## 6. Fork A — diseño propuesto

### 6.1 Visión general

Tres componentes nuevos, **ningún cambio en los tres comandos existentes**, sin watchdog/daemon:

```
small_plan_horizon   →   small_review        →   small_build --unsupervised
(corta hasta 3 fases,    (interactivo:            (driver secuencial in-session:
 reutiliza el núcleo      sintetiza + chequeos     fase 1→2→3, goal-oracle gate,
 de small_plan por        mecánicos; el humano     circuit-breaker --max-attempts N,
 fase, freezes upfront)   valida y aprueba)        halt-and-surface si falla)
```

Condición de activación del modo no supervisado: **opt-in explícito** + **todas las fases con `review_approved == true`**.

### 6.2 Componente 1 — `small_plan_horizon` (planificación de horizonte largo)

Comando **hermano** de `small_plan` (no lo muta). Función nueva = **solo el corte en fases** (un `time_split`-lite); la planificación *por fase* **reutiliza el núcleo de `small_plan`** invocado N veces.

- **Corte en fases** (≤3): DAG de dependencias backward-only, clusters atómicos (no se parten entre fases), fase 1 = fundación, E2E **acumulativo** (fase N testea 1..N).
- **Feed-forward de seams en sesión**: la fase 2 se planifica contra los contratos **congelados** de la fase 1 (no contra el ledger *realizado* — la fase 1 aún no se construyó). Cada fase congela sus seams cross-fase upfront en el `freeze_ledger.json`.
- **Reutiliza** la emisión de `phase_<N>_manifest.md` + `epic_manifest.json` + `epic_<M>/epic.md` + goals `test/waves/<id>/` de small_plan, por fase.
- **Change-hygiene:** extraer la lógica de planificación-por-fase a una sección/skill compartida que ambos comandos invocan, para evitar dos planificadores que divergen.

> ⚠️ **Decisión (resuelta):** el comando **soporta hasta 3 fases**, pero **emite un warning recomendando un máximo de 2**. 2 fases es el techo seguro (una dependencia hacia atrás, compounding mínimo); 3 es **modo experimental** donde el review-humano-como-crítico carga mucho más peso y el blast-radius crece no-linealmente. El warning aparece en `small_plan_horizon` al cortar 3 fases y se repite en `small_build --unsupervised` en runtime. Ver §8.

### 6.3 Componente 2 — `small_review` (review interactivo y sintetizado)

Comando **solo-lectura** sobre los artefactos que `small_plan_horizon` ya escribió. Recorre fase a fase. Su valor es la **comprensión consolidada cross-fase + validación**, no re-chequear.

**Contrato de la capa de síntesis (requisito de diseño, no nice-to-have):**

1. **Sintetizado por defecto, drill-down a un golpe.** Resumen legible de specs y goals; el humano abre la assertion real del goal / la AC verbatim cuando algo le chirría. La síntesis **indexa** el artefacto, nunca lo reemplaza.
2. **Chequeos load-bearing computados, no narrados.** El "¿el goal cubre todas las ACs?" es una **comprobación mecánica** (mapa AC→assertion, marca huérfanas), no una frase que el LLM afirma. Igual con contradicciones entre contratos de épicas y dependencias cross-fase.
3. **Surfacea por riesgo, no por orden.** Lo primero de cada fase: los seams congelados que la fase siguiente hereda read-only.
4. **Marca de aprobación por fase:** al validar, escribe `review_approved` (por fase) vía un nuevo verbo del CLI.

Por qué no es redundante con los gates existentes: estos asumen que el humano *lee los artefactos*; `small_review` los hace **comprensibles en minutos a través de N fases** y respalda la validación con chequeos deterministas.

### 6.4 Componente 3 — `small_build --unsupervised` (driver secuencial in-session)

Extiende el `--auto` actual de "una fase" a "fases secuenciales". **In-session, sin cron.** Es un **flag** de `small_build`, no un comando aparte.

**Arquitectura clave — progressive disclosure para no contaminar la ruta supervisada:**

`small_build` es, en su forma normal, **supervised + single-phase-focused** — esa es la hot-path y debe quedarse limpia. Toda la lógica adicional que el modo no supervisado necesita (driver secuencial de fases, gating por `review_approved`, circuit-breaker, halt-and-surface, escalado de modelo, warning de 3 fases) **vive en un markdown separado** (p. ej. `references/unsupervised-multiphase.md` o un skill hermano) que `small_build` **solo lee cuando se pasa `--unsupervised`**. Así la ejecución supervisada de una sola fase no carga en contexto instrucciones multi-fase que no le aplican. (Es el mismo patrón de progressive disclosure que usan Superpowers/gstack: ficheros de referencia cargados bajo demanda.)

**Comportamiento con `--unsupervised`:**

- **Descubre las fases leyendo el disco** (`phases/phase_*/`) — sin campo `total_phases` en estado. Las recorre en orden.
- Por fase, ejecuta el `small_build` existente (waves, goal-oracle, /code-review por wave).
- **Circuit-breaker `--max-attempts N`** por goal: si un goal sigue rojo tras N round-trips del implementador → **PARAR y surfacear** (no avanzar, no marcar verde). Opción in-philosophy: **escalar el modelo** en el reintento (el `model_plan.yaml` ya es prompt-level en small).
- **Gating:** arranca solo con opt-in explícito (`--unsupervised`) + `review_approved` de **todas** las fases en disco.
- **Multi-fase por diseño:** el modo solo tiene sentido con ≥2 fases. Sobre una sola fase degenera al `--auto` actual (y debería avisar de que la ruta normal es la supervisada). Con 3 fases, repite el **warning de modo experimental**.
- **Halt-and-surface** deja el estado en la fase con su goal rojo, listo para que el humano retome.

### 6.5 Cambios de estado / CLI (mínimos)

| Cambio | Dónde | Para |
|---|---|---|
| *(ninguno — descubrir por disco)* | `small_build --unsupervised` y `small_review` globean `phases/phase_*/` | Evita un campo `total_phases` en estado; las fases se descubren leyendo el disco. |
| `review_approved` (por fase) | estado + verbo `set-review --phase N --status approved` | Gating del modo no supervisado. |
| `goal_attempts` (por épica/goal) | `Wave` + verbo `record-goal-attempt <wave> <epic> --result green\|red` | El circuit-breaker `--max-attempts N`. |
| Invariante AC→goal | dentro del epic-readiness check / `small_review` | El chequeo mecánico de cobertura. |
| E2E acumulativo | `small_plan_horizon` | Oráculo de integración cross-fase. |

Reutiliza el `state_io` atómico vendorizado y el guard `SquaredSchemaDetected` (bump de `SCHEMA` + defaults en `from_dict`). **No** se cablea el `scheduler.py` vendorizado (sigue sin usar).

---

## 7. Las dos piezas pequeñas que valen aunque NO se construya Fork A

Independientes de todo el aparato multi-fase, cierran huecos reales con ~pocas líneas:

1. **Invariante AC→goal coverage**, dentro del epic-readiness check actual de `small_plan`: *"toda AC mapea a ≥1 assertion de goal; marca huérfanas"*. Es el tercer invariante que falta (junto a feature-coverage y concrete-files-resolution). Cierra el vector "passes-but-is-wrong".
2. **Circuit-breaker de reintentos** en `small_build`: cota `--max-attempts N` → PARAR-y-avisar. Convierte el "itera hasta verde" implícito en "itera hasta verde *o* falla acotado y ruidoso".

Ninguna necesita comando nuevo, watchdog, cron ni feedback artifact.

---

## 8. Riesgos residuales y posicionamiento honesto

### 8.1 Riesgos que persisten incluso en el mejor caso

- **Planificación multi-fase en una pasada = alto blast-radius, sin red de convergencia.** Todo el peso recae en la pasada de review humana; si el usuario hace rubber-stamp, nada caza un corte de fases malo. Mitigación: el review respaldado mecánicamente (§6.3) — su calidad es ahora la pieza crítica del sistema.
- **Se pierde el bucle "aprende de la fase 1 antes de planificar la 2"** — la razón de ser del modelo de dos runs. Aceptable para trabajo **predecible** + opt-in; el usuario que elige no-supervisado afirma *"esto es lo bastante predecible para planificarlo entero a priori"*. Debe explicitarse en el propio comando.
- **Validación point-in-time:** el humano valida en T0; la fase 1 construye en T1 y puede revelar que una suposición de la fase 2 era falsa. El goal de la fase 1 no caza un error de *planificación* de la fase 2 → de ahí el requisito de **E2E acumulativo**.
- **Drift del contrato realizado:** mitigado —no eliminado— por la disciplina "frozen = read-only". Si la fase 1 descubre que el contrato congelado es inconstruible, lo correcto es que **pare** (goal no verde → breaker), no que el implementador lo deforme.
- **Riesgo de la capa de síntesis:** el humano podría validar el *resumen* en vez del *artefacto*. Mitigado por divulgación por capas + chequeos mecánicos (§6.3).

### 8.2 Posicionamiento estratégico: "squared ligero"

Con planificación multi-fase upfront + ejecución secuencial, **eigen-small se convierte en un "squared ligero"**: alcance de planificación de squared + gate-humano-en-vez-de-convergencia + ejecución goal-oracle de small, **sin daemon ni swarm**. Es una posición de producto **defendible** si se asume conscientemente. El diferenciador no es la planificación (será parecida a `time_split`); es la **ejecución ligera** y el **humano como crítico**.

| Nº fases | Recomendación |
|---|---|
| 1 | El flujo actual de eigen-small. No hace falta nada nuevo. |
| 2 | **Punto dulce de Fork A.** Una dependencia hacia atrás, compounding mínimo. |
| 3 | **Stretch.** Feasible, pero el review carga mucho peso y el blast-radius crece no-linealmente. |
| ≥4 | **Usar eigen-squared.** Ahí necesitas lo que squared ya pagó (breakers de oscilación, gate de degradado, secuenciación endurecida). |

> La regla honesta: en cuanto quieras que una **máquina** avance de fase N→N+1 *sin* un humano, quieres eigen-squared. Fork A no hace eso — pone al humano al frente validando todas las fases, y luego ejecuta lo ya validado. Esa es la distinción que lo mantiene legítimo.

---

## 9. Recomendación y fases de construcción

**Estado: Fork A IMPLEMENTADO** en `feat/eigen-small` (commits `4ee95ea`→`fb8294c`). Los cuatro
pasos están construidos y pusheados; el cap quedó en 2 fases recomendado / 3 experimental (warn) /
≥4 → squared. No se construyó watchdog/cron/claude-tasks/feedback-artifact (decisión sostenida).

1. ✅ **Paso 0 (independiente, alto ROI):** invariante AC→goal coverage (Invariant #3 en `small_plan`)
   + circuit-breaker `--max-attempts N` en `small_build`. *(commit `51b8524`)*
2. ✅ **Paso 1:** `small_review` (comando) + `cli/review_ledger.py` + verbos `set-review`/`review-list`
   + tests. Descubre fases por disco; síntesis por capas + chequeo mecánico AC→goal. *(commit `f58cf22`)*
3. ✅ **Paso 2:** `small_plan_horizon` (corte ≤3 fases, reutiliza núcleo small_plan, freezes upfront,
   E2E acumulativo) + routing en `small_route` + README. Markdown-only. *(commit `b97fad1`)*
4. ✅ **Paso 3:** `small_build --unsupervised` + `skills/unsupervised-multiphase` (progressive
   disclosure). State-file por fase (`--state-file`) en vez de un campo `total_phases`; gate por
   `review-list` (todas aprobadas). Markdown-only. *(commit `fb8294c`)*

**Notas de implementación que se desviaron del plan original:** (a) las aprobaciones por fase viven
en un **`review_ledger.json`** cross-fase (espejo del freeze ledger), no en el estado plano — más
consistente con "descubrir por disco"; (b) el driver no usa `total_phases`: usa un **state-file
aislado por fase** (`phases/phase_<N>/pipeline_state_small.json`), lo que evita re-apuntar/sobrescribir
un estado compartido y da resumibilidad gratis; (c) el circuit-breaker es prompt-level (in-session),
sin persistir `goal_attempts` — suficiente para la seguridad dentro de un run (persistir entre
resumes queda como follow-up opcional).

---

## 10. Decisiones (resueltas)

- ✅ **Fases:** soportar **hasta 3** pero con **warning recomendando máximo 2**; 3 = modo experimental.
- ✅ **`--unsupervised` es un flag de `small_build`** (no un comando aparte), con **progressive disclosure**: la lógica multi-fase vive en un markdown separado que solo se lee con el flag, para no contaminar la ruta supervisada single-phase.
- ✅ **Descubrir fases leyendo el disco** (`phases/phase_*/`); sin campo `total_phases` en estado.
- ✅ **`small_review` descubre fases por disco igual** → funciona con 1 fase hoy y con N en cuanto exista `small_plan_horizon`, sin acoplarse a él. **Recomendado construirlo primero** (Paso 1, valor inmediato single-phase). *(Pendiente de confirmación final.)*

### Notas de alcance derivadas

- `small_review` **no** se restringe a multi-fase: revisa las fases que haya en disco (1 o N). El modo **`--unsupervised` sí** es multi-fase por diseño (sobre 1 fase degenera al `--auto` actual).
