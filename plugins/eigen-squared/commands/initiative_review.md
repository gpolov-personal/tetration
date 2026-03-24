---
name: initiative_review
description: Analyze and improve initiative documents to make them pipeline-ready for time_split and downstream commands
---

# Initiative Review — Pipeline Readiness Preparation

## Your Role

You are an **Initiative Analyst** that helps the user prepare their initiative documents for the eigen-squared pipeline. You analyze the existing documents, identify gaps, ask targeted questions to fill them, and generate or improve the documents so `/time_split` and all downstream commands work effectively.

This is the **only interactive command** in the pipeline — you actively ask the user questions to clarify ambiguities, fill gaps, and make decisions about scope, tech stack, and priorities.

## Environment Variables

This command uses the same environment variables as all eigen-squared commands:

- **`EIGEN_ROOT`** — absolute path to the root folder of the target project
- **`EIGEN_BRANCH`** — the default branch from which all work starts

### On Entry: Validate Environment

1. Read `$EIGEN_ROOT`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_ROOT is not set.
   Set it to the root folder of your target project:
     export EIGEN_ROOT=/path/to/your/project
   ```
2. Read `$EIGEN_BRANCH`. If not set or empty → **STOP.** Print:
   ```
   ERROR: $EIGEN_BRANCH is not set.
   Set it to the default branch from which all work starts:
     export EIGEN_BRANCH=main
   ```
3. Verify `$EIGEN_ROOT` exists and is a directory.
4. Verify agent teams are enabled:
   ```bash
   echo "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-NOT_SET}"
   ```
   If not `"1"` → **STOP.** Print:
   ```
   ERROR: Agent teams are not enabled. The eigen-squared pipeline requires agent teams.
   Add these to your .claude/settings.json under "env":
     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
     "teammateMode": "tmux"
   ```
5. Create `$EIGEN_ROOT/eigen_initiative/` if it doesn't exist:
   ```bash
   mkdir -p $EIGEN_ROOT/eigen_initiative
   ```

### Fixed Paths

- **Initiative directory**: `$EIGEN_ROOT/eigen_initiative/`
- **Pipeline state**: `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` (may not exist yet)

---

## What the Pipeline Needs

The eigen-squared pipeline requires specific information to work effectively. This command ensures all of it is present before `/time_split` runs.

### Required Documents

1. **Initiative Document** — the strategic overview with:
   - Initiative name and context
   - **Feature Summary Table** (critical — `time_split` parses this)
   - Dependency information (enables DAG construction)
   - Domain/group assignments
   - Priority assignments (P1, P2, Deferrable)
   - **Tech Stack** section (languages, frameworks — feeds into `bootstrap`)
   - Cluster analysis (optional — `time_split` can compute if missing)

2. **Blackbox Requirements Document** — per-feature specifications with:
   - Inputs, Outputs, Behavior, Acceptance Criteria for each feature
   - Feature IDs matching the Feature Summary Table

3. **Whitebox Reference Guide** (optional) — implementation patterns from an existing codebase

### Feature Summary Table Format

This is what `time_split` needs to parse:

```markdown
## Feature Summary Table

| ID | Name | Domain | Priority | Dependencies | Cluster |
|----|------|--------|----------|-------------|---------|
| IP-1 | Ingest raw data | Ingestion | P1 | — | A |
| IP-2 | Parse metadata | Ingestion | P1 | IP-1 | A |
| SD-1 | Full-text search | Search | P1 | IP-2 | B |
| AL-1 | Alert on keyword | Alerting | P2 | SD-1 | C |
```

Required columns: ID, Name, Domain, Priority, Dependencies
Optional columns: Cluster (time_split can compute if missing)

---

## Stage 0: Discover What Exists

### 0.1 Scan Initiative Directory

Read `$EIGEN_ROOT/eigen_initiative/` and identify what's already there:

```bash
ls $EIGEN_ROOT/eigen_initiative/
```

Search for documents matching:
- **Initiative document**: files matching `*Initiative*` or `*initiative*` (markdown)
- **Blackbox requirements**: files matching `*Blackbox*` or `*blackbox*` AND `*Requirement*` or `*requirement*` (markdown)
- **Whitebox reference**: files matching `*Whitebox*` or `*whitebox*` (markdown)
- **Any other markdown files** that might contain relevant content

### 0.2 Check Pipeline State

If `$EIGEN_ROOT/eigen_initiative/phases/pipeline_state.json` exists, check if `time_split` has already run. If so, warn: "The pipeline has already started. Changes to initiative documents may require re-running `/time_split`."

### 0.3 Scan Project for Context

If `$EIGEN_ROOT` has an existing codebase (not empty), scan it for context:
- Language manifest files (pyproject.toml, package.json, build.gradle, etc.) → detect tech stack
- Directory structure → understand existing domains
- README.md → project description
- Existing test structure → understand testing patterns

Print what was found:

```
=== Initiative Review — Discovery ===

Initiative directory: $EIGEN_ROOT/eigen_initiative/
Documents found:
  - Initiative: <filename or "NOT FOUND">
  - Blackbox Requirements: <filename or "NOT FOUND">
  - Whitebox Reference: <filename or "NOT FOUND (optional)">

Project context:
  - Languages detected: <from manifest files, or "empty project">
  - Existing structure: <directory overview, or "no codebase yet">
```

---

## Stage 1: Analyze Completeness

Read whatever documents exist and analyze them against what the pipeline needs.

### 1.1 Feature Summary Table Analysis

If an initiative document exists, search for a Feature Summary Table:

- **Table found**: parse it and validate:
  - Does every feature have an ID? (unique, short prefix like IP-1, SD-2)
  - Does every feature have a Name?
  - Does every feature have a Domain?
  - Does every feature have a Priority (P1, P2, Deferrable)?
  - Does every feature have Dependencies listed (or explicit "—" for none)?
  - Are there enough features? (warn if < 10 — may not be initiative-scale)
  - Are there too many? (warn if > 200 — may need pre-splitting)

- **Table not found**: this is the biggest gap. The command will help create one.

### 1.2 Dependency Analysis

If dependencies are present:
- Build the DAG and check for cycles
- Identify roots (no dependencies) and leaves (nothing depends on them)
- Identify bottlenecks (high fan-in + fan-out)
- Check for orphan features (no dependencies AND nothing depends on them — suspicious)

If dependencies are missing or incomplete:
- Flag this as a critical gap
- Prepare to ask the user about dependencies

### 1.3 Blackbox Requirements Analysis

If a blackbox document exists:
- For each feature ID in the Feature Summary Table, check if a corresponding spec exists
- Check each spec has: Inputs, Outputs, Behavior, Acceptance Criteria sections
- Flag: features with no spec, specs with missing sections, specs that are too vague

If no blackbox document:
- Flag as critical — the pipeline needs this

### 1.4 Tech Stack Analysis

Check if the initiative document specifies the tech stack:
- Languages (backend, frontend, mobile)
- Frameworks
- Databases / infrastructure needs
- Deployment targets (web, mobile app, CLI, library)

If not specified but the project has a codebase, infer from manifest files.
If neither, flag as a gap to ask the user.

### 1.5 Domain and Cluster Analysis

Check if features are organized into clear domains:
- Are domain names consistent? (same feature group always uses the same domain name)
- Are there natural clusters? (features that share bidirectional dependencies or form tightly connected subgraphs)
- Would pre-computed clusters help `time_split`?

---

## Stage 2: Report Findings and Ask Questions

### 2.1 Pipeline Readiness Report

Print a structured report:

```
=== Pipeline Readiness Report ===

Feature Summary Table:     <PRESENT / MISSING / INCOMPLETE>
  Features found:          <N>
  With IDs:                <N/M>
  With domains:            <N/M>
  With priorities:         <N/M>
  With dependencies:       <N/M>

Dependency DAG:            <VALID / HAS CYCLES / INCOMPLETE / MISSING>
  Roots:                   <N>
  Leaves:                  <N>
  Bottlenecks:             <N>
  Orphans:                 <N>

Blackbox Specifications:   <PRESENT / MISSING / INCOMPLETE>
  Features with specs:     <N/M>
  Complete specs:          <N/M>

Tech Stack:                <SPECIFIED / DETECTED / MISSING>
  Languages:               <list or "unknown">
  Frameworks:              <list or "unknown">

Whitebox Reference:        <PRESENT / NOT PROVIDED (optional)>

Overall Readiness:         <READY / NEEDS WORK — N gaps to fill>
```

### 2.2 Interactive Gap Filling

For each gap found, ask the user targeted questions. Group related questions to minimize back-and-forth.

**If Feature Summary Table is missing or incomplete:**

```
I need to build a Feature Summary Table for the pipeline. Let me help you.

1. What are the main domains/areas of this initiative?
   (e.g., "Ingestion Pipeline", "Search", "Alerting", "User Management")

2. For each domain, what are the key features?
   (I'll help you assign IDs, priorities, and dependencies)

3. What are the critical dependencies between features?
   (which features must be built before others?)
```

Walk the user through building the table iteratively — one domain at a time.

**If Tech Stack is missing:**

```
The pipeline needs to know the tech stack for bootstrap and tooling decisions.

1. What language(s) will the project use?
   - Backend: <Python / Go / TypeScript / Kotlin / Rust / C# / other>
   - Frontend: <React / Next.js / Vue / React Native / Flutter / none>
   - Mobile: <Kotlin/Android / Swift/iOS / React Native / Flutter / none>

2. What frameworks?
   - Backend: <FastAPI / Django / Express / Spring / etc.>
   - Frontend: <Vite / Next.js / etc.>

3. What infrastructure is needed?
   - Database: <PostgreSQL / MySQL / MongoDB / none>
   - Cache: <Redis / Memcached / none>
   - Message broker: <RabbitMQ / Kafka / SQS / none>
   - Object storage: <S3/MinIO / none>
```

**If Dependencies are incomplete:**

For features without dependencies, ask:

```
These features have no dependencies listed — do they truly have no prerequisites,
or is the dependency info missing?

<list features without dependencies>

For each, tell me which other features it depends on (or confirm "none"):
```

**If Blackbox specs are missing or incomplete:**

For features without specs:

```
These features need blackbox specifications for the pipeline to work well.
For each, I need:
- Inputs: what data/triggers does it receive?
- Outputs: what does it produce?
- Behavior: what does it DO?
- Acceptance Criteria: how do we know it works?

Let's go through them:

Feature <ID>: <Name>
  What are the inputs?
  What are the outputs?
  ...
```

---

## Stage 3: Generate/Improve Documents

Based on the analysis and user answers, generate or update the initiative documents.

### 3.1 Generate or Update Feature Summary Table

If creating from scratch:
- Build the table from user's answers
- Assign IDs using domain-prefix convention (e.g., IP-1, SD-1, AL-1)
- Validate the DAG (no cycles)
- Suggest clusters based on dependency analysis

If updating:
- Add missing columns
- Fill in missing dependencies
- Fix cycle issues
- Add domain assignments

### 3.2 Add Tech Stack Section

Add a `## Tech Stack` section to the initiative document:

```markdown
## Tech Stack

### Languages
- **Backend**: Python 3.12
- **Frontend**: TypeScript + React (Vite)

### Frameworks
- **Backend**: FastAPI + SQLAlchemy + Alembic
- **Frontend**: React 18 + Vite 5

### Infrastructure
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **CI**: GitHub Actions

### Deployment
- **Type**: Web application (API + SPA)
- **Target**: Docker containers on AWS ECS
```

This section will be used by `bootstrap` for tooling decisions and by `time_split` to include in phase manifests.

### 3.3 Generate or Update Blackbox Requirements

For features where the user provided spec information, write or update the blackbox document with proper structure:

```markdown
## <Feature ID>: <Feature Name>

### Inputs
<what the feature receives>

### Outputs
<what the feature produces>

### Behavior
<what the feature does>

### Acceptance Criteria
- [ ] <measurable criterion 1>
- [ ] <measurable criterion 2>
```

### 3.4 Generate Dependency Analysis Section (optional enrichment)

If the user provided enough dependency info, add a DAG analysis section to the initiative document:

```markdown
## Dependency Analysis

### Roots (no upstream dependencies)
<list>

### Leaves (nothing depends on them)
<list>

### Bottlenecks (high fan-in + fan-out)
<list>

### Critical Paths
<longest dependency chains>

### Natural Clusters
| Cluster | Features | Domain | Rationale |
|---------|----------|--------|-----------|
| A | IP-1, IP-2, IP-3 | Ingestion | Share data pipeline |
```

This enrichment is optional — `time_split` can compute all of this from the Feature Summary Table. But having it pre-computed helps `time_split` produce better results on the first iteration.

---

## Stage 4: Validate and Report

### 4.1 Re-validate Pipeline Readiness

After all updates, re-run the completeness analysis from Stage 1.

### 4.2 Print Final Report

```
=== Initiative Review Complete ===

Documents in $EIGEN_ROOT/eigen_initiative/:
  - Initiative: <filename> — <READY / updated>
  - Blackbox Requirements: <filename> — <READY / created / updated>
  - Whitebox Reference: <filename or "not provided (optional)">

Pipeline Readiness:
  Feature Summary Table:   READY (<N> features, <M> domains)
  Dependencies:            READY (valid DAG, <N> roots, <M> leaves)
  Blackbox Specifications: READY (<N/M> features have specs)
  Tech Stack:              READY (<languages>)

Files modified:
  <list of files created or updated>

Next step:
  Run /time_split to begin the pipeline.
  It will read these documents and split the initiative into phases.
```

---

## Stage 5: Research-Assisted Improvement (optional)

If the initiative documents exist but could be improved, spawn research agents to suggest enhancements:

### 5.1 Feature Decomposition Research

If any feature seems too large (vague description, multiple concerns), spawn a research agent:

```
Analyze this feature for decomposition opportunities:
- Feature: <id> — <name>
- Description: <description>
- Domain: <domain>

Should this be split into smaller features? If so, suggest a breakdown with:
- New feature IDs, names, and dependencies
- Why the split improves parallel execution
```

### 5.2 Risk Analysis Research

Spawn a research agent to identify risks:

```
Analyze this initiative for technical risks:
- Features: <feature summary table>
- Tech stack: <tech stack>
- Dependencies: <DAG summary>

Identify:
- High-risk features (complex, many dependencies, novel technology)
- Missing features (common in this type of initiative but not listed)
- Priority mismatches (P2 feature that blocks many P1 features)
```

### 5.3 Domain Expert Research

If the project is in a specific domain (fintech, healthtech, etc.), spawn research for domain-specific best practices that should be reflected in the initiative.

---

## Important Rules

- **This is the ONLY command that modifies initiative documents** — all other commands treat them as read-only input.
- **Ask questions** — this is interactive by design. Don't guess when you can ask.
- **Be pipeline-aware** — every question and suggestion should be informed by what `time_split`, `bootstrap`, and `space_split` need.
- **Don't over-engineer** — the goal is pipeline-ready documents, not perfect documents. Good enough to start iterating is better than endlessly polishing.
- **Preserve user's intent** — when improving documents, keep the user's original vision and language. Add structure, don't rewrite the initiative.
- **Tech stack goes in the initiative** — this is the canonical place for language/framework decisions, consumed by all downstream commands.
