---
name: compound_improve
description: Read accumulated lessons and rewrite command prompts in the plugin source repo to permanently improve them
argument-hint: <path_to_local_plugin_source_repo>
---

# Compound Improve — Self-Improving Command Prompts

## Introduction

This command reads accumulated lessons (written by deepen commands to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/`) and uses them to **rewrite the command prompt files** in the plugin source repo to permanently incorporate what was learned. The commands get better with every iteration.

This is not runtime adaptation — it physically edits the markdown command files in the source repo. The user must then review the changes (`git diff`), commit, and update the plugin for the improvements to take effect.

## Environment Variables and Arguments

This command uses `$EIGEN_ROOT` (where lessons live) plus ONE argument (where the plugin source lives):

- **`EIGEN_ROOT`** — absolute path to the target project (lessons are at `$EIGEN_ROOT/eigen_initiative/eigen_lessons/`)
- **Argument**: `<plugin_source_path>` — path to the local eigen-squared plugin source repo (e.g., `/home/user/Projects/vs-da-plugin-lib/plugins/eigen-squared`)

### On Entry: Validate Environment

1. Read `$EIGEN_ROOT`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_ROOT is not set.
   Set it to the root folder of your target project:
     export EIGEN_ROOT=/path/to/your/project
   ```
2. Verify `$EIGEN_ROOT/eigen_initiative/eigen_lessons/` exists. If not → **STOP.** Print:
   ```
   ERROR: No lessons directory found at $EIGEN_ROOT/eigen_initiative/eigen_lessons/
   Run deepen commands first to generate lessons.
   ```

### Parse Argument

<compound_improve_arguments>
$ARGUMENTS
</compound_improve_arguments>

The argument is the path to the local plugin source repo. If empty → **STOP.** Print:

```
Usage: /compound_improve <path_to_local_plugin_source_repo>

Argument:
  - plugin_source_repo: Path to the local eigen-squared plugin source repo.
    Must contain commands/ and .claude-plugin/plugin.json.

Example:
  /compound_improve /home/user/Projects/vs-da-plugin-lib/plugins/eigen-squared
```

**Validate the plugin source path:**
1. Verify `<plugin_source_path>/commands/time_split.md` exists
2. Verify `<plugin_source_path>/commands/bootstrap_converge.md` exists
3. Verify `<plugin_source_path>/commands/space_split_converge.md` exists
4. Verify `<plugin_source_path>/commands/plan_epic_converge.md` exists
5. Verify `<plugin_source_path>/.claude-plugin/plugin.json` exists

If any check fails → **STOP** with specific error.

### Lesson Sources

Lessons are read from `$EIGEN_ROOT/eigen_initiative/eigen_lessons/` with one subdirectory per command:

| Lesson Directory | Written By | Improves Command |
|-----------------|-----------|-----------------|
| `eigen_lessons/time_split/` | `/deepen_time_split` | `time_split.md` |
| `eigen_lessons/bootstrap_converge/` | `/bootstrap_converge` | `bootstrap_converge.md` |
| `eigen_lessons/space_split_converge/` | `/space_split_converge` | `space_split_converge.md` |
| `eigen_lessons/plan_epic_converge/` | `/plan_epic_converge` | `plan_epic_converge.md` |
| `eigen_lessons/review_swarm_pr/` | `/review_swarm_pr` | `review_swarm_pr.md` |

---

## Stage 0: Load & Analyze Lessons

### 0.1 Read All Lessons

For each lesson directory, glob `$EIGEN_ROOT/eigen_initiative/eigen_lessons/<command_name>/*.json`. Parse each JSON. Filter out lessons with `"status": "applied"` — these have already been incorporated.

Count pending lessons per command.

If no pending lessons exist across all directories → **STOP.** Print: "No pending lessons found. Run deepen commands first to generate lessons."

### 0.2 Present Lesson Summary

Print:

```
=== Compound Improve — Lesson Analysis ===

Lessons from $EIGEN_ROOT/eigen_initiative/eigen_lessons/:

time_split:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

bootstrap_converge:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

space_split_converge:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

plan_epic_converge:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

review_swarm_pr:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

Total pending: <N>
```

### 0.3 Read Current Command Files

Read each command file from the plugin source repo that has pending lessons:
- `<plugin_source_path>/commands/time_split.md`
- `<plugin_source_path>/commands/bootstrap_converge.md`
- `<plugin_source_path>/commands/space_split_converge.md`
- `<plugin_source_path>/commands/plan_epic_converge.md`
- `<plugin_source_path>/commands/review_swarm_pr.md`

Only read files that have pending lessons — skip commands with zero pending.

---

## Stage 1: Pattern Analysis

### 1.1 Group Lessons by Command and Section

For each command, group pending lessons by `affected_phase` (or `affected_section`):

```
time_split:
  Phase 1.2 (Seed Phase 1): 3 lessons
    - ts-lesson-001: Cluster split [high]
    - ts-lesson-005: Missing foundation feature [medium]
    - ts-lesson-009: E2E chain broken [high]
  Phase 1.3 (Layer Remaining): 2 lessons
    - ts-lesson-003: Priority override needed [medium]
    - ts-lesson-007: Bottleneck placed too late [high]
```

### 1.2 Identify Recurring Patterns

A **pattern** is when 2+ lessons share the same `affected_phase` + `category`:

- **Strong pattern** (3+ lessons): high confidence systemic issue
- **Moderate pattern** (2 lessons): likely issue, worth addressing
- **Single lesson**: may be initiative-specific, lower confidence

For each pattern, synthesize a **merged recommendation** addressing all contributing lessons.

### 1.3 Detect Conflicts

Check for conflicting recommendations — two lessons targeting the same section with opposing advice. Flag conflicts for user resolution.

### 1.4 Present Patterns to User

Print the analysis:

```
=== Pattern Analysis ===

time_split — 3 patterns found:
  1. [STRONG] Phase 1.3: Cluster integrity violated during topological sort (3 lessons)
     Root cause: dependency depth computed before cluster membership check
     Recommendation: Check cluster membership BEFORE computing candidate_phase

  2. [MODERATE] Phase 1.2: First E2E chain incomplete in seeded Phase 1 (2 lessons)
     Root cause: Minimal output feature not pulled into Phase 1
     Recommendation: Add explicit check for output presence in Phase 1

  3. [SINGLE] Phase 1.4: Phase balance adjustment destroyed E2E continuity (1 lesson)
     Recommendation: Re-validate E2E after every merge/split

Conflicts: 0
```

### 1.5 User Confirmation

Ask the user which improvements to apply:

```
Which improvements should I apply to the command files?

Options:
  1. All patterns — Apply all strong and moderate patterns (Recommended)
  2. Strong only — Apply only patterns with 3+ supporting lessons
  3. Let me pick — I'll select which patterns to apply
  4. Show lessons first — Show me the full lesson details before deciding
```

Store the user's selection and approved patterns.

---

## Stage 1.6: Cross-Epic Pattern Aggregation

This stage runs **independently of the per-command lesson edits above** and produces a separate artifact at `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json`. The artifact is consumed at planning time by `bootstrap_converge` and `plan_epic_converge` to surface oscillation-prone patterns from prior epics into the next planning context.

The per-command lesson aggregation in Stages 0–1 looks at lessons (qualitative). This stage looks at the **convergence ledgers** (quantitative) — `review_convergence_state.json`, `swarm-manifest.json`, `pipeline_state.json.swarm_execution.findings_history` — and detects patterns that recurred across **3 or more epics**.

### 1.6.1 Walk Epics

Glob `$EIGEN_ROOT/eigen_initiative/phases/phase_*/epic_*/`. For each epic directory, attempt to read:

- `review_convergence_state.json` — if missing, skip this epic (legacy / pre-Tier-1)
- `swarm-manifest.json` — for `monotonicity.m1_firings`, `tasks[].architectural_escalation`, `tasks[].architectural_escalation_files`, `p3_sweep`
- `pipeline_state.json` — for `swarm_execution.findings_history` and `swarm_execution.convergence.reason`

Missing files are non-fatal: epics without ledgers are silently skipped. This keeps the aggregator forward-compatible with old initiatives.

### 1.6.2 Detect Three Pattern Kinds

Build three buckets keyed by a stable signature; each bucket records `supporting_epics: [<phase/epic id>]` and `occurrences: <int>`.

**Source of truth for per-finding metadata:** `findings_history[].entries[]` (each entry has `signature`, `severity`, `file`, `category`, `threat_class`, `title_normalized`). For pre-Tier-4 epics that lack `entries[]`, fall back to the per-iteration `review_convergence_state.json` sidecar — those epics will be missing `threat_class` and are excluded from Kind-2 evaluation (logged once per run, not fatal).

**Kind 1 — Cross-epic oscillation.** For each epic, walk `review_convergence_state.json.iterations[].file_iteration_counts` and pick files where the streak ≥ 2 (i.e., the file oscillated within the epic). Bucket key: `(category, normalized_path_basename)`. `category` comes from the matching `entries[]` payload looked up by `signature`. `normalized_path_basename` is the file's basename lowercased (`src/api/users.ts` → `users.ts`) — full paths differ across projects/epics, but basenames provide a useful cross-epic equivalence.

**Kind 2 — Cross-epic architectural escalation.** For each epic, scan `swarm-manifest.json.tasks[]` for `architectural_escalation == true`. Bucket key: `(category, threat_class)` read directly from the originating finding's `entries[]` payload. Skip entries where `threat_class == "other"` (excluded from Kind-2 promotion by definition). If an epic recorded an `m1_firings` count ≥ 1 OR a `convergence.reason` of `P1_REGRESSION_PERSISTENT` / `DIVERGING_LOOP`, also include the dominant `(category, threat_class)` pair from the epic's last review iteration's `entries[]`.

**Kind 3 — Cross-epic type escapes.** For each epic, scan `entries[]` whose `category == "type-safety"` OR `threat_class == "type-escape"`. The `threat_class` field is now authoritative — the Tier-4 ban (`code_from_validation_tests_swarm.md`) requires workers to tag every type-escape finding with `threat_class: "type-escape"`, so the title-regex fallback is only used for pre-Tier-4 entries. Bucket key: `(escape_pattern, normalized_path_basename)`.

### 1.6.3 Apply 3+ Epic Threshold

For each bucket across all three kinds: keep only entries where `len(unique supporting_epics) >= 3`. This matches the existing "3+ supporting lessons" gate used by Stage 1.2 above (strong-pattern threshold) and keeps the artifact terse.

### 1.6.4 Write Artifact

Write to `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json` (create the directory if needed):

```json
{
  "schema_version": 1,
  "generated_at": "<ISO 8601>",
  "eigen_root": "<absolute path>",
  "threshold": 3,
  "patterns": [
    {
      "kind": "oscillation" | "architectural_escalation" | "type_escape",
      "category": "<category>",
      "threat_class": "<threat_class or null>",
      "path_basename": "<basename or null>",
      "escape_pattern": "<pattern literal or null>",
      "supporting_epics": ["phase_1/epic_3", "phase_2/epic_1", "phase_3/epic_2"],
      "occurrences": 7,
      "first_seen": "<ISO 8601 of earliest supporting epic's convergence_state>",
      "last_seen": "<ISO 8601 of latest>",
      "recommendation": "<one-sentence guidance — e.g., 'Plan auth-middleware changes with explicit threat-class review; this category oscillated in 4 prior epics'>"
    }
  ]
}
```

**Atomic write contract.** This stage rewrites the file wholesale (the deterministic detector recomputes the patterns every run). Use the same POSIX-atomic pattern the CLI uses for `pipeline_state.json`: write to `<target>.tmp`, `fsync`, then `rename(<target>.tmp, <target>)`. A SIGKILL between the temp-write and rename leaves the prior `cross_epic_patterns.json` intact. Bash equivalent:

```bash
TMP="$ARTIFACT.tmp.$$"
cat > "$TMP" <<EOF
<JSON content>
EOF
sync "$TMP" 2>/dev/null || true
mv -f "$TMP" "$ARTIFACT"
```

**Acquire a state lock around the read-modify-write.** Other concurrent `compound_improve` runs (rare but possible if the user manually invokes the command while a watchdog also has it scheduled) MUST serialize. Reuse the CLI's flock pattern: `flock $EIGEN_ROOT/eigen_initiative/.compound_improve.lock <write sequence>`. If the lock is held, abort with a clear error rather than racing.

**`schema_version` field** identifies the artifact version. Future migrations (e.g. switching from `path_basename` to `parent_dir/basename` per Tier-4 Step B4) bump this and trigger a one-time recompute on the next `compound_improve` run. Consumers (`bootstrap_converge`, `plan_epic_converge`) MUST read `schema_version` first and skip the artifact entirely if version > current-known.

The `recommendation` is generated deterministically from the kind:
- `oscillation` → `"Files matching <basename> in category <category> oscillated in <N> prior epics — plan defensively (split task, pre-validate threat class, or scope-expand)."`
- `architectural_escalation` → `"Category <category> with threat class <threat_class> required architectural escalation in <N> prior epics — pre-flight a design_decision question in the plan."`
- `type_escape` → `"Pattern <escape_pattern> in <basename> was banned across <N> prior epics — plan native typing from the start."`

### 1.6.5 Print Summary

Print:

```
=== Cross-Epic Patterns ===

Walked: <N> epics (<M> with full ledgers)
Patterns detected (≥ 3 supporting epics): <K>
  Oscillation:               <a>
  Architectural escalation:  <b>
  Type escape:               <c>

Artifact: $EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json
```

If `K == 0`, write an empty `"patterns": []` array (still create the artifact so consumers see "no known patterns" rather than missing-file).

---

## Stage 1.7: Cross-Epic Pattern Promotion to Prompt Edits

Stage 1.6 produces `cross_epic_patterns.json` for **runtime advisory** consumption — `bootstrap_converge` and `plan_epic_converge` read it on every invocation to inject prior-epic warnings into planning context. But the patterns never make it into the prompt files themselves; every new initiative re-discovers the same threat classes, and the artifact dies when `EIGEN_ROOT` resets.

This stage promotes high-confidence cross-epic patterns from runtime advisory to **permanent prompt edits** in the plugin source repo. Promotion is a higher bar than runtime injection — a bad promotion affects every future initiative.

### 1.7.1 Promotion Threshold

Read `$EIGEN_ROOT/eigen_initiative/eigen_lessons/compound_improve/cross_epic_patterns.json`. Filter to entries where:
- `occurrences >= 5` (vs. the runtime-advisory threshold of 3 — promotion to permanent prompt content needs more evidence), AND
- `promoted_to_prompt != true` (skip patterns already promoted in a prior `compound_improve` run).

If no patterns survive the filter, skip Stage 1.7 entirely.

### 1.7.2 Generate Edit Per Pattern Kind

For each surviving pattern, produce a structured edit proposal. The edit content depends on `pattern.kind`:

**`oscillation`** → edit goes into `<plugin_source_path>/commands/plan_epic_converge.md` Strategic Overview / Risk Factors guidance (around the "Risk factors and mitigation strategies" bullet in Stage 2.3's planner prompt). Edit template:
```markdown
> **Cross-epic oscillation watch:** Files matching basename `<basename>` in category `<category>`
> have oscillated in <N> prior epics across this initiative. When this epic touches such files,
> plan defensively: split tasks earlier, pre-validate threat class, or scope-expand.
```

**`architectural_escalation`** → edit goes into `<plugin_source_path>/commands/orchestrate_swarm.md` ARCHITECTURAL ESCALATION REQUIRED block (the worker spawn prompt section added by Tier 2 Step 2). Edit template:
```markdown
> **Pre-flight architectural escalation (cross-epic confirmed):** Combination of
> category=`<category>` AND threat_class=`<threat_class>` triggered architectural
> escalation in <N> prior epics. Worker MUST raise `[QUESTION] type: design_decision`
> before any production-code change in this combination, regardless of file-iteration
> -streak count.
```

**`type_escape`** → edit goes into `<plugin_source_path>/commands/code_from_validation_tests_swarm.md` Code Quality Standards (the Stage 3 type-safety rules section). Edit template:
```markdown
> **Banned pattern (cross-epic confirmed):** `<escape_pattern>` in `<basename>` was banned
> across <N> prior epics. Native typing is mandatory from the first commit; raise
> `[QUESTION] type: type_escape_needed` only with strict justification.
```

### 1.7.3 Surface in Stage 1 User Confirmation

Promoted patterns appear in Stage 1.4's pattern listing prefixed with `[CROSS-EPIC]` to distinguish them from per-command lesson patterns:

```
=== Pattern Analysis ===

[per-command patterns above ...]

Cross-epic promotions (≥ 5 supporting epics):
  1. [CROSS-EPIC] [OSCILLATION] plan_epic_converge.md / Strategic Overview
     Pattern: files matching basename `users.ts` in category `data-integrity`
     oscillated in 6 prior epics
     Edit: append "Cross-epic oscillation watch" advisory note

  2. [CROSS-EPIC] [TYPE-ESCAPE] code_from_validation_tests_swarm.md / Code Quality Standards
     Pattern: `as any` in `auth-service.ts` banned across 5 prior epics
     Edit: append "Banned pattern (cross-epic confirmed)" reminder
```

Stage 1.5's user-confirmation prompt is extended with a fifth option:
```
  5. Skip cross-epic promotions — Apply per-command lesson patterns only
```

The user can decline specific cross-epic patterns from option 3 ("Let me pick").

### 1.7.4 Apply Edits and Mark as Promoted

When the user approves a cross-epic promotion, Stage 2.2 applies the edit using the Edit tool with the same surgical-edit rules (preserve structure, add comment marker). Comment marker for cross-epic edits:

```markdown
<!-- Compound improvement: cross-epic <kind> — promoted from cross_epic_patterns.json (<N> supporting epics) -->
```

**Transactional apply-edit + write-back.** The promotion path (apply git edits, then write `promoted_to_prompt: true` back to `cross_epic_patterns.json`) needs SIGKILL safety: if the process dies between applying the git edits and the writeback, the next run would re-apply the edits and double-write the prompt content. Solve with a write-pending-first, three-step ladder:

1. **Mark pending** (atomic write-1): set `promoted_to_prompt: false, pending_promotion: true, pending_at: <ISO 8601>` on the pattern entry. Use the same atomic write contract from 1.6.4 (tempfile + fsync + rename, under the state lock).
2. **Apply edits** (idempotent git operations): the per-pattern Edit-tool calls. Edit calls are idempotent because they include the unique comment marker `<!-- Compound improvement: cross-epic ... -->`; re-running them either no-ops (marker present) or applies the same edit again (marker absent).
3. **Mark complete** (atomic write-2): set `promoted_to_prompt: true, promoted_at: <ISO 8601>, promoted_in_version: <plugin version>, pending_promotion: false` on the pattern entry. Same atomic write.

If the process dies between step 1 and step 2, the next run sees `pending_promotion: true` and re-applies step 2 (which is idempotent) before step 3. If the process dies between step 2 and step 3, same recovery. The window where state can be inconsistent is the brief moment between a successful `rename()` and the same caller's next state read — well under a millisecond.

After applying, the pattern entry looks like:
```json
{
  "kind": "oscillation",
  "category": "data-integrity",
  ...,
  "promoted_to_prompt": true,
  "pending_promotion": false,
  "promoted_at": "<ISO 8601>",
  "promoted_in_version": "<plugin version after bump>"
}
```

This prevents re-promotion in the next `compound_improve` run.

### 1.7.5 CHANGELOG Entry

Stage 3.2's CHANGELOG section gets an additional sub-section for cross-epic promotions:

```markdown
**Cross-epic promotions:**
- [OSCILLATION] plan_epic_converge.md: `users.ts` / `data-integrity` (6 supporting epics)
- [TYPE-ESCAPE] code_from_validation_tests_swarm.md: `as any` / `auth-service.ts` (5 supporting epics)
```

### 1.7.6 Rollback Story

Cross-epic promotions land in the plugin source repo as ordinary commits (via the existing Stage 2.2 → Stage 3 → user-driven git commit flow). Rollback is via standard `git revert` on the compound-improvement commit. The `promoted_to_prompt` flag in `cross_epic_patterns.json` does NOT auto-reset — manual reset is required if the user wants the same pattern re-considered for promotion (this is conservative: a reverted promotion was a deliberate choice, and re-surfacing it would re-prompt the user unnecessarily).

---

## Stage 2: Rewrite Commands

### 2.1 Improvement Strategy

For each approved pattern, determine the edit type:

- **Add constraint**: insert a new validation check or guard condition
- **Reorder logic**: move a step earlier or later within a phase
- **Strengthen instruction**: make a soft guideline into a hard rule ("consider" → "MUST")
- **Add step**: insert a new sub-step into an existing phase
- **Add phase**: create a new validation phase (rare — only for systemic gaps)

### 2.2 Apply Edits Per Command

For each command with approved patterns:

1. Locate the `affected_phase` section by its heading
2. Apply the edit using the Edit tool
3. After each edit, add a comment at the end of the modified section:

```markdown
<!-- Compound improvement: <pattern title> — applied from <N> lessons (<lesson-ids>) -->
```

**Critical rules for edits:**
- NEVER delete existing logic unless a lesson explicitly identifies it as wrong
- PREFER adding constraints over replacing existing constraints
- PRESERVE the overall structure (phase numbering, headings, frontmatter)
- Each edit must be surgical — touch only the affected section
- If unsure about an edit, add as a `> **Note:**` block rather than rewriting

### 2.3 Validate Edits

After all edits:

1. Read each modified file
2. Verify YAML frontmatter is still valid
3. Verify all phase headings are intact
4. Verify no duplicate content was introduced
5. Count total lines changed per file

If validation fails, revert that specific edit and report.

---

## Stage 3: Update Metadata

### 3.1 Bump Plugin Version

1. Read `<plugin_source_path>/.claude-plugin/plugin.json`
2. Bump the **patch** version (e.g., `3.0.0` → `3.0.1`)
3. Write updated plugin.json

### 3.2 Update or Create CHANGELOG

Prepend a new entry to `<plugin_source_path>/CHANGELOG.md`:

```markdown
## [<new_version>] - <date>

### Compound Improvements

**time_split.md:**
- <pattern 1 title> (from <N> lessons)
- <pattern 2 title> (from <N> lessons)

**bootstrap_converge.md:**
- <pattern 1 title> (from <N> lessons)

**space_split_converge.md:**
- <pattern 1 title> (from <N> lessons)

**plan_epic_converge.md:**
- <pattern 1 title> (from <N> lessons)

**review_swarm_pr.md:**
- <pattern 1 title> (from <N> lessons)

**Lessons applied:** <total count>
**Lessons source:** $EIGEN_ROOT/eigen_initiative/eigen_lessons/
```

### 3.3 Mark Lessons as Applied

For each lesson that contributed to an approved pattern:

1. Read the lesson JSON from `$EIGEN_ROOT/eigen_initiative/eigen_lessons/<command>/`
2. Set `"status": "applied"`
3. Add `"applied_at": "<ISO 8601>"` and `"applied_in_version": "<new_version>"`
4. Write the updated JSON back

This ensures these lessons are skipped in future runs.

---

## Stage 4: Summary & Next Steps

Print:

```
=== Compound Improvement Complete ===

Lessons read from: $EIGEN_ROOT/eigen_initiative/eigen_lessons/
Commands modified in: <plugin_source_path>/commands/

Changes:
  time_split.md:       <N> patterns applied (<M> lines changed)
  bootstrap_converge.md: <N> patterns applied (<M> lines changed)
  space_split_converge.md: <N> patterns applied (<M> lines changed)
  plan_epic_converge.md:  <N> patterns applied (<M> lines changed)
  review_swarm_pr.md:  <N> patterns applied (<M> lines changed)

Version bumped: <old> → <new>
CHANGELOG updated
Lessons marked as applied: <N>

Next steps:
  1. Review changes:
     cd <plugin_source_path>
     git diff

  2. If satisfied, commit:
     git add .
     git commit -m "compound: apply <N> lessons from <initiative_name>"

  3. The improved commands are now active for your next initiative.
```

Offer to show the diff:

```
Would you like to:
  1. View diff — Show git diff of all changes
  2. Review a specific edit — See before/after of one pattern
  3. Revert all — Undo all changes
  4. Done — I'll review and commit manually
```

---

## Important Rules

- **Two sources**: lessons from `$EIGEN_ROOT` (the initiative), edits to `<plugin_source_path>` (the plugin source)
- **Surgical edits only**: never rewrite entire files — touch only the specific sections identified by lessons
- **Preserve structure**: phase numbering, headings, frontmatter must stay intact
- **User confirms before editing**: always show patterns and get approval before modifying command files
- **Mark lessons as applied**: prevents re-application on future runs
- **Version bump**: every compound improvement increments the patch version
