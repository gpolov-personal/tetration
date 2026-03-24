# Consolidated Lesson Recommendations for eigen-squared v1.3.0

**Date**: 2026-03-22
**Source**: 88 lessons from the Simulacros P1 pipeline run (time_split: 3, bootstrap: 7, space_split: 3, plan_phase_epic: 60, review_swarm_pr: 15)
**Purpose**: Concise, actionable changes to each command prompt for the v1.3.0 release. Abstracted from project-specific details into general principles.

---

## Executive Summary

Across 88 lessons, **5 systemic failure modes** emerged:

1. **Plans assume preconditions without verification** — schema counts, SDK behavior, platform quirks are stated as fact without grepping/auditing the actual codebase
2. **Primary flow bias** — commands audit read paths but miss write operations, privileged execution contexts, and internal service call chains
3. **Specs condensed to the point of information loss** — large blackbox specs truncated, interface contracts written as prose instead of exact signatures
4. **Configuration drift** — CI commands diverge from project scripts, test runner configs not cross-referenced with CI steps, untracked dependencies
5. **Speculative design in swarm workers** — helpers with zero consumers, static analysis masquerading as behavioral tests, mock stubs that fail silently

---

## Note on Whitebox

The whitebox reference guide is **optional** — it exists when refactoring or replicating an existing system, not for greenfield projects. Throughout this document:

- "whitebox or actual source" means: if whitebox exists, use it; otherwise, read the actual codebase (schema files, migration files, model definitions, existing code)
- The principle is always: **verify against reality**, not against upstream documents. Whitebox is one form of reality; the codebase itself is another
- No recommendation should break if whitebox doesn't exist — the fallback is always "read the code"

---

## Changes by Command

### 1. `time_split` (3 lessons)

| # | Change | Rationale |
|---|--------|-----------|
| T1 | **Never condense blackbox specs** — include in full. If >30 lines, keep verbatim rather than summarizing | Condensed specs lost field-level inputs and behavior details needed by downstream commands |
| T2 | **Verify domain coverage for all features** — after selecting content for a phase, iterate ALL features (including P2/Deferrable) and confirm each feature's domain has relevant guidance. If whitebox exists, verify sections cover all domains; if not, flag gaps | Secondary features were missed because selection focused on primary domains |
| T3 | **Add "Downstream Notes" section** — scan all available documentation (whitebox, Initiative, blackbox) for binding decisions or anti-patterns requiring work not captured as features. Surface as actionable notes | Implicit requirements (migrations, system transitions) fell between features |

**Prompt addition**:
```
After generating each phase manifest:
1. Include ALL blackbox specs verbatim — never condense or summarize
2. For each feature in the phase, verify its domain has relevant guidance (from whitebox if available, or from Initiative/blackbox)
3. Scan all documentation for architectural decisions requiring work not owned by any feature — list in "Downstream Notes"
```

---

### 2. `bootstrap` (7 lessons)

| # | Change | Rationale |
|---|--------|-----------|
| B1 | **Use the most authoritative schema source for entity stubs** — prefer (in order): actual schema/migration files > whitebox schema section > blackbox specs. Never use blackbox alone for field names/types | Entity fields diverged from actual DB schema when derived from blackbox specs alone |
| B2 | **Detect language-specific module system before creating configs** — for JS/TS: check `package.json "type"` field (ESM vs CJS patterns); for Python: check if project uses `src/` layout vs flat; for Go: check module path. Apply appropriate patterns for the detected system | Config files used wrong module patterns for the project's setup |
| B3 | **CI commands must delegate to project scripts** — use `npm run lint` / `uv run pytest` / `make test`, never hardcoded tool invocations with flags | CI hardcoded commands diverged from project scripts, causing different behavior |
| B4 | **Handle existing codebases honestly** — run full-repo verification, report actual warning/error counts, set realistic baselines. Don't claim "passed" when legacy issues exist | Verification claimed success while hundreds of legacy warnings existed |
| B5 | **Create stubs for cross-cutting feature dependencies** — if a feature touches ALL entities (e.g., access control, validation), create minimal stubs for later-phase entities too | Missing entity stubs for tables needed by cross-cutting features |
| B6 | **Extract ALL enum-like values as named constants uniformly** — don't apply the pattern to some enums but leave others inline | Inconsistent: some enums as constants, others left inline in the same codebase |
| B7 | **Stub ALL access patterns described in documentation** — if docs describe multiple access tiers (admin + user, read + write, public + private), create stubs for ALL of them | Only one access pattern stubbed; others omitted, leading to ad-hoc implementations |

**Prompt addition**:
```
Entity stub generation:
1. Use most authoritative schema source: actual schema files > whitebox > blackbox
2. For cross-cutting features, create minimal stubs for ALL referenced entities (even later-phase ones)
3. Extract ALL enum-like values as named constants uniformly
4. Stub ALL access patterns described in documentation, not just the primary one

Config generation:
5. Detect project's module system / layout conventions before creating config files
6. CI workflow MUST delegate to project scripts, never hardcode tool commands
7. For existing codebases: run full-repo verification, report actual counts, set honest baselines
```

---

### 3. `space_split` (3 lessons)

| # | Change | Rationale |
|---|--------|-----------|
| S1 | **Distinguish shared infrastructure from API contracts** — types/utils/constants files are imports, not negotiated interfaces. Only declare actual API contracts as inter-epic interfaces | Shared types treated as formal interfaces created false coupling |
| S2 | **Enforce provider-consumer symmetry** — consumer's concrete_files must be subset of provider's concrete_files | Consumer files omitted from structural definition despite narrative mention |
| S3 | **Detect file-level overlap in parallel epics** — for same-wave epics, compute file overlap and add `shared_files_warning` | Parallel epics modifying many overlapping files with no merge conflict warning |

**Prompt addition**:
```
Interface classification:
1. Shared Infrastructure (types, utils, constants) = any epic imports directly. NOT an inter-epic interface
2. API Contracts (clients, middleware, services) = requires provider/consumer agreement. IS an interface

After forming epics:
3. For each interface: verify consumer.concrete_files ⊆ provider.concrete_files
4. For same-wave epics: compute file overlap. If >0 files shared, add shared_files_warning to wave definition
```

---

### 4. `plan_phase_epic` (60 lessons — grouped into 6 categories)

This command had the most lessons by far. The changes below are distilled from 60 individual findings into general principles.

#### 4A. Schema & Codebase Verification

| # | Change | Rationale |
|---|--------|-----------|
| P1 | **Audit actual codebase before planning** — count entities, verify fields exist, check function/trigger/migration prerequisites against actual source files | Plans assumed wrong entity counts, referenced non-existent fields |
| P2 | **Build complete access control matrix** — for each entity, grep for all CRUD operations by role. Every non-empty cell needs an access rule | Access control plans covered read paths but missed write operations |
| P3 | **Trace cross-entity queries** — list all API routes/services with multi-entity queries, verify that access rules compose correctly across joins | Per-entity access rules didn't account for join/query patterns |

#### 4B. Interface & Dependency Precision

| # | Change | Rationale |
|---|--------|-----------|
| P4 | **Use exact function signatures** for interface contracts, not prose descriptions | Parameter order inverted when described in prose |
| P5 | **Trace internal service call chains** — grep for internal API calls to find service-to-service dependencies | Auth enforcement on routes with internal calls broke without credential forwarding |
| P6 | **Track API contract changes** — grep all callers before changing method, path, or content type of any endpoint | Callers broken by undocumented endpoint contract changes |
| P7 | **Specify module relocation strategy** — add both source AND destination to shared files map with backward-compatibility plan | Exports relocated without updating consumers |

#### 4C. Security Specification

| # | Change | Rationale |
|---|--------|-----------|
| P8 | **No conditional language in security requirements** — "if present" → "MUST verify"; "should" → "MUST" | Conditional wording creates implementer bypass |
| P9 | **Assign every security mitigation to a task** — no "paper mitigations" described but unassigned | Security requirements described in prose but never assigned to implementation tasks |
| P10 | **Analyze all execution contexts** — user-authenticated, privileged/admin, background/migration, unauthenticated. Every security rule must specify behavior in each context | Code using auth-context functions crashed when running under privileged/background contexts |
| P11 | **Use structured validation, not string checks** — for URLs, use parsed comparison; for inputs, use schema validation; never rely on string prefix/suffix matching | String-based validation bypassable via encoding/normalization |

#### 4D. Technology Verification

| # | Change | Rationale |
|---|--------|-----------|
| P12 | **Verify library/framework behavior in actual context** — browser vs server, bundled vs unbundled, different runtime versions | Documented behavior only applied in one context (e.g., browser) but was assumed universal |
| P13 | **Grep for actual imports before architectural decisions** — which SDK methods/modules are actually used in the codebase? | Plan chose wrong approach because nobody checked what the codebase actually imports |

#### 4E. Test Strategy

| # | Change | Rationale |
|---|--------|-----------|
| P14 | **Re-audit test coverage before planning** — read actual test files, don't inherit gap claims from upstream docs | Stale coverage claims led to redundant or misaligned test plans |
| P15 | **Include both positive and negative test cases** — every access rule needs "allowed" AND "rejected" scenarios | Tests verified allowed paths but never tested rejection |
| P16 | **Verify test runner config before proposing test locations** — check include/exclude patterns, test directory conventions | Tests placed in directories excluded by test runner config |
| P17 | **Verify test framework conventions** — assertion counts must match actual assertions; seed data must survive the test framework's isolation model (transactions, teardown) | Test framework conventions violated → suites blocked or data silently lost |

#### 4F. Plan Internal Consistency

| # | Change | Rationale |
|---|--------|-----------|
| P18 | **Update ALL sections when applying feedback** — summary tables, component descriptions, E2E scenarios, risk tables must all reflect changes | Feedback updated one section but left others stale |
| P19 | **Flag overrides of upstream specs explicitly** — "OVERRIDING epic.md: [reason]" | Plan silently contradicted upstream spec without flagging the discrepancy |
| P20 | **Specify single approach, not alternatives** — "use X" not "use X or Y" | "or" language leaves implementation ambiguous for swarm workers |

**Prompt addition (summary)**:
```
Before writing the plan:
1. Audit actual codebase — count entities, verify fields, check prerequisites against source files
2. Build access control matrix: entity × role × operation → every cell needs a rule
3. Grep for internal service calls to trace dependencies
4. Verify library/framework behavior in actual runtime context
5. Re-audit existing test coverage — read actual test files, don't inherit claims

In the plan:
6. Interface contracts: exact signatures, consumer file list, edge cases
7. Security requirements: no conditional language, every mitigation assigned to a task
8. All execution contexts analyzed: authenticated, privileged, background, unauthenticated
9. Single approach per decision — no "or" alternatives
10. Flag any override of upstream specs explicitly

Before delivering:
11. Cross-reference all sections — summary tables, components, E2E scenarios must be consistent
12. Verify test file locations against test runner config include/exclude patterns
```

---

### 5. `review_swarm_pr` (15 lessons)

| # | Change | Rationale |
|---|--------|-----------|
| R1 | **Require behavioral testing** — tests must execute code, not perform static source analysis (parsing files with regex) | Swarm workers wrote "tests" that parsed source files instead of running the code |
| R2 | **Verify test framework assertion counts** — declared test counts must match actual assertions. If the framework requires explicit counts, verify after review | Declared more tests than existed → entire suite blocked |
| R3 | **Verify test framework API usage** — parameter order, method signatures, assertion semantics must match the framework's actual API | Wrong parameter order → tests passed but didn't validate what they claimed |
| R4 | **Audit config/dependency file tracking** — every file referenced by CI must be tracked in version control | CI referenced config files that weren't committed |
| R5 | **Enforce YAGNI on exports** — grep for import statements; delete exports with zero consumers | Helper modules exported functions nobody imported |
| R6 | **Mocks must fail loudly** — throw on calls beyond expected count, never silently reuse last response | Silent mock fallback masked missing test expectations |
| R7 | **Consistent assertion depth** — same response type = same assertion pattern across all tests | Inconsistent: some error tests checked 3 fields, others checked 1 |
| R8 | **CI security hardening** — explicit permissions block, pin third-party actions to commit SHAs | No permissions block + mutable action tags = supply chain risk |
| R9 | **Cross-reference test runner with CI** — verify test config include/exclude patterns don't cause duplicate runs across CI steps | Multiple CI steps ran same tests due to overlapping config |
| R10 | **Flag test deduplication** — >40% overlap between test files targeting same scope = consolidate | Separate files duplicated 60%+ of tests and mocks |
| R11 | **Verify cross-layer response handling** — when middleware/interceptors create new response objects, verify they preserve headers/cookies set by upstream layers | New response objects dropped headers set by upstream middleware |

**Prompt addition**:
```
Test quality checks:
1. Every test file executes code under test (no static source analysis "tests")
2. Test framework assertion counts and API signatures are correct
3. Mocks throw on excess calls — never silently reuse
4. Same response type = same assertion depth across all test files
5. Every export has ≥1 import consumer (grep to verify)

CI & config checks:
6. All CI-referenced files tracked in version control
7. Test runner include patterns don't overlap across CI steps
8. Permissions block declared; third-party actions pinned to commit SHAs

Cross-layer checks:
9. Middleware/interceptor response handling preserves upstream headers/cookies
10. Flag >40% test duplication between files targeting same scope
```

---

## Cross-Cutting Recommendations

These affect multiple commands:

### CC1: "Verify, Don't Assume" Principle

Every command assumes things that should be verified:
- time_split assumes blackbox specs can be condensed (they can't)
- bootstrap assumes upstream docs have correct field names (they may not)
- plan_phase_epic assumes entity counts, SDK behavior, platform quirks
- review_swarm_pr assumes tests actually test things (some do static analysis)

**Add to all command preambles**:
> "Before stating any fact about the codebase (entity count, field name, SDK behavior, test coverage), verify it by reading the relevant source. Do not inherit claims from upstream documents without cross-referencing against actual source files."

### CC2: "Complete Matrix" Principle

Commands consistently audit primary flows and miss secondary ones:
- time_split covers primary domains, misses secondary features
- space_split forms interfaces for primary APIs, misses shared infrastructure classification
- plan_phase_epic plans read access, misses write operations
- review_swarm_pr checks test existence, misses assertion completeness

**Add to plan_phase_epic and review_swarm_pr**:
> "For every access control rule, interface contract, or test plan: build the complete matrix (all roles × all operations × all contexts). Empty cells are explicit decisions, not oversights."

### CC3: "Authoritative Source for Schema"

Multiple commands independently interpret the data model with different results:
- bootstrap may use blackbox specs (can have wrong field names)
- plan_phase_epic may use upstream docs (can have wrong counts)
- review_swarm_pr reviews whatever the swarm wrote (may be wrong)

**Resolution**: The authoritative source for schema is (in priority order):
1. Actual schema files in the codebase (migration files, model definitions, schema.sql)
2. Whitebox database schema section (if it exists)
3. Blackbox specs (least reliable for field-level details)

All commands must cross-reference against the highest-priority source available. If none exists (pure greenfield with no code yet), blackbox specs are acceptable but should be flagged as "unverified — will be validated at bootstrap."

---

## Priority for v1.3.0

**Must-have** (addresses systemic failures):
- B1: Authoritative schema source for entity stubs (schema files > whitebox > blackbox)
- B2: Language-specific module system detection
- B3: CI commands delegate to project scripts
- P1-P3: Codebase audit + access control matrix + cross-entity query tracing
- P8-P10: Security language precision + task assignment + execution context analysis
- R1-R3: Behavioral testing + framework API correctness
- R4-R6: Config tracking + YAGNI + loud mock failures
- CC1: "Verify, Don't Assume" preamble for all commands

**Should-have** (addresses recurring issues):
- T1-T3: Full specs + domain coverage + downstream notes
- S1-S3: Interface classification + symmetry + file overlap
- P4-P7: Interface precision + call chain tracing
- R7-R11: Assertion consistency + CI security + deduplication
- CC2-CC3: Complete matrix + authoritative schema source

**Nice-to-have** (prevents edge cases):
- B6-B7: Enum uniformity + all access patterns
- P18-P20: Plan internal consistency checks
