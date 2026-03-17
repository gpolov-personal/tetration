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
2. Verify `<plugin_source_path>/commands/bootstrap.md` exists
3. Verify `<plugin_source_path>/commands/space_split.md` exists
4. Verify `<plugin_source_path>/commands/plan_phase_epic.md` exists
5. Verify `<plugin_source_path>/.claude-plugin/plugin.json` exists

If any check fails → **STOP** with specific error.

### Lesson Sources

Lessons are read from `$EIGEN_ROOT/eigen_initiative/eigen_lessons/` with one subdirectory per command:

| Lesson Directory | Written By | Improves Command |
|-----------------|-----------|-----------------|
| `eigen_lessons/time_split/` | `/deepen_time_split` | `time_split.md` |
| `eigen_lessons/bootstrap/` | `/deepen_bootstrap` | `bootstrap.md` |
| `eigen_lessons/space_split/` | `/deepen_space_split` | `space_split.md` |
| `eigen_lessons/plan_phase_epic/` | `/deepen_plan_phase_epic` | `plan_phase_epic.md` |
| `eigen_lessons/review_swarm_pr/` | `/review_swarm_pr` | `review_swarm_pr.md` |

---

## Phase 0: Load & Analyze Lessons

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

bootstrap:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

space_split:
  Pending: <N>  (high: <N>, medium: <N>, low: <N>)
  Already applied: <N>

plan_phase_epic:
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
- `<plugin_source_path>/commands/bootstrap.md`
- `<plugin_source_path>/commands/space_split.md`
- `<plugin_source_path>/commands/plan_phase_epic.md`
- `<plugin_source_path>/commands/review_swarm_pr.md`

Only read files that have pending lessons — skip commands with zero pending.

---

## Phase 1: Pattern Analysis

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

## Phase 2: Rewrite Commands

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

## Phase 3: Update Metadata

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

**bootstrap.md:**
- <pattern 1 title> (from <N> lessons)

**space_split.md:**
- <pattern 1 title> (from <N> lessons)

**plan_phase_epic.md:**
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

## Phase 4: Summary & Next Steps

Print:

```
=== Compound Improvement Complete ===

Lessons read from: $EIGEN_ROOT/eigen_initiative/eigen_lessons/
Commands modified in: <plugin_source_path>/commands/

Changes:
  time_split.md:       <N> patterns applied (<M> lines changed)
  bootstrap.md:        <N> patterns applied (<M> lines changed)
  space_split.md:      <N> patterns applied (<M> lines changed)
  plan_phase_epic.md:  <N> patterns applied (<M> lines changed)
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
