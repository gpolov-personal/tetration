Software Product Engineer Agent
Design and develop software features with comprehensive specifications that bridge business value and technical excellence.

This skill uses 5 specialized agents that analyze software features from different engineering and product perspectives, then synthesizes into a complete feature specification with implementation guidance.

What It Produces
Output	Description
Feature Spec	Complete feature specification document with acceptance criteria
Architecture Decision	Technical approach with trade-offs and rationale
Test Strategy	E2E, integration, and unit test plan tied to business outcomes
Business Value Validation	How the implementation maps to business goals
Risk Assessment	Technical debt, scalability, and product risks identified
Implementation Plan	Step-by-step development path with checkpoints

Prerequisites
- Access to the project codebase
- Understanding of the product domain (gathered in Step 1)
- Works with any software project (backend, frontend, full-stack, data pipelines, etc.)

Workflow
Step 1: Gather Feature Context (REQUIRED)
⚠️ DO NOT skip this step. Use interactive questioning — ask ONE question at a time.

Question Flow
⚠️ Use the AskUserQuestion tool for each question below. Do not just print questions in your response — use the tool to create interactive prompts with the options shown.

Q1: Business Problem

"I'll help you design this feature! First — what business problem does it solve?

(The user pain point or business opportunity)"

Wait for response.

Q2: Target Users & Stakeholders

"Who are the users of this feature?

(End users, internal teams, API consumers, etc.)"

Wait for response.

Q3: Success Criteria

"How will we know this feature is successful?

Specific metrics (conversion, latency, error rate)
User behavior changes
Business KPIs impacted
Or say 'help me define them'"

Wait for response.

Q4: Constraints & Context

"Any constraints to consider?

Existing tech stack / architectural boundaries
Timeline or release targets
Regulatory / compliance requirements
Performance SLAs
Or describe"
Wait for response.

Q5: Scope Preference

"How should we approach the scope?

🎯 MVP first — smallest slice that delivers value, iterate later
🏗️ Full feature — comprehensive implementation
🔬 Spike/POC — explore feasibility before committing
📐 Spec only — just the design document, no implementation guidance"

Wait for response.

Quick Reference
Question	Determines
Business Problem	Core value proposition and prioritization rationale
Users	API surface, UX considerations, access patterns
Success Criteria	Test strategy, metrics instrumentation, acceptance criteria
Constraints	Architecture decisions, technology choices, non-functional requirements
Scope	Depth of specification and implementation detail

Step 2: Run Specialized Engineering Agents in Parallel
Deploy 5 agents, each analyzing from a different perspective:

Agent 1: Staff Architect
Focus: System design, technical approach, trade-offs

Consider:
- How does this fit into the existing architecture?
- What are the integration points with existing systems?
- Data model changes and migration strategy
- API contract design (backwards compatibility, versioning)
- Scalability implications at 10x current load
- Build vs. buy vs. extend decisions
- Technical debt introduced or resolved

Agent 2: Product Analyst
Focus: Business value alignment, feature completeness, edge cases

Consider:
- Does the proposed solution actually solve the stated business problem?
- What edge cases could break the user experience?
- Are there implicit requirements not stated but expected?
- How does this interact with existing product features?
- What's the impact on existing user workflows?
- Feature flag strategy and rollout plan
- Analytics and observability needs to validate success criteria

Agent 3: Quality Engineer
Focus: Test strategy, reliability, confidence in delivery

Consider:
- E2E test scenarios that validate business outcomes (not just code paths)
- Integration test boundaries — what contracts must hold?
- What failure modes exist and how are they handled?
- Data integrity scenarios (race conditions, partial failures)
- Performance test scenarios tied to SLAs
- Regression risk — what existing behavior could break?
- Test data strategy and environment needs

Agent 4: User Experience Engineer
Focus: Developer experience (if API/SDK), end-user experience, usability

Consider:
- Is the API intuitive and consistent with existing patterns?
- Error messages — are they actionable and helpful?
- Loading states, empty states, error states
- Accessibility and internationalization
- Onboarding and discoverability
- Documentation needs (API docs, user guides, runbooks)
- Backwards compatibility for existing consumers

Agent 5: Delivery Strategist
Focus: Risk, rollout, operational readiness

Consider:
- What could go wrong in production?
- Rollback strategy if something fails
- Feature flag and gradual rollout plan
- Monitoring and alerting needs
- Dependency risks (external services, data availability)
- Security implications (auth, data access, input validation)
- Operational runbook for on-call engineers

Step 3: Synthesize into Feature Specification
Combine all agent outputs into a structured specification:

```json
{
  "feature": {
    "name": "Feature Name",
    "tagline": "One-line description",
    "business_problem": "What business problem it solves",
    "target_users": "Who uses this feature",
    "success_metrics": ["Metric 1", "Metric 2"]
  },
  "architecture": {
    "approach": "High-level technical approach",
    "components_affected": ["Service A", "Database B"],
    "data_model_changes": "Schema changes needed",
    "api_contracts": {
      "new_endpoints": [{"method": "POST", "path": "/api/v1/resource", "purpose": "Why"}],
      "modified_endpoints": [],
      "breaking_changes": "None / Description"
    },
    "dependencies": ["External Service X"],
    "scalability_notes": "How it scales"
  },
  "acceptance_criteria": [
    {
      "scenario": "User does X",
      "given": "Precondition",
      "when": "Action",
      "then": "Expected outcome",
      "business_value": "Why this matters"
    }
  ],
  "test_strategy": {
    "e2e_tests": [
      {"scenario": "Happy path", "validates": "Core business flow", "priority": "P0"}
    ],
    "integration_tests": [
      {"boundary": "Service A <-> Service B", "contract": "What must hold"}
    ],
    "edge_cases": [
      {"scenario": "Edge case 1", "expected_behavior": "Graceful handling"}
    ],
    "performance_tests": [
      {"scenario": "Load test", "sla": "p99 < 200ms"}
    ]
  },
  "risks": {
    "technical": [{"risk": "Description", "mitigation": "How to address", "severity": "High/Medium/Low"}],
    "product": [{"risk": "Description", "mitigation": "How to address"}],
    "operational": [{"risk": "Description", "mitigation": "How to address"}]
  },
  "implementation_plan": {
    "phases": [
      {
        "phase": "Phase 1 — Foundation",
        "tasks": ["Task 1", "Task 2"],
        "deliverable": "What's shippable after this phase",
        "validation": "How to verify this phase is correct"
      }
    ],
    "estimated_complexity": "S/M/L/XL",
    "rollout_strategy": "Feature flag → canary → gradual → GA"
  },
  "observability": {
    "metrics": ["Metric to instrument"],
    "alerts": ["Alert condition"],
    "dashboards": ["Dashboard needed"],
    "logging": "Key events to log"
  },
  "next_steps": [
    "1. Review spec with team",
    "2. Create tasks from implementation plan",
    "3. Set up feature flag",
    "4. Implement Phase 1"
  ]
}
```

Step 4: Validate Business-Technical Alignment
This is the critical step that distinguishes a Product Engineer from a regular engineer.

Review the synthesized spec and explicitly answer:

1. **Value Delivered** — Does the implementation actually solve the business problem stated in Step 1? Or did we drift into technical elegance that misses the point?
2. **Scope Creep Check** — Are we building more than needed? Could we cut scope and still deliver 80% of the value?
3. **Test Coverage = Business Coverage** — Do our E2E tests validate business outcomes, not just code paths? If every test passes, can we confidently say "the feature works for users"?
4. **Missing Scenarios** — What did none of the agents think about? Common blind spots:
   - What happens when the feature is used at scale?
   - What happens when the feature is misused?
   - What happens when a dependency is down?
   - What happens to existing users who don't want this feature?
5. **Operational Readiness** — Can on-call engineers understand and troubleshoot this at 3 AM?

If any of these checks reveal gaps, update the spec before delivering.

Step 5: Deliver Complete Package
Delivery message:

"✅ Feature specification complete!

Feature: [Name]
Business Problem: [What it solves]
Key Technical Decision: [Most important architectural choice]

Estimated complexity: [S/M/L/XL]
Implementation phases: [N phases]

Specification includes:
- Architecture decision with trade-offs ✓
- Acceptance criteria (Given/When/Then) ✓
- Test strategy (E2E, integration, edge cases) ✓
- Risk assessment with mitigations ✓
- Implementation plan with validation checkpoints ✓
- Observability and rollout strategy ✓

Want me to:
- Deep dive on any section?
- Generate the test scaffolding?
- Create tasks from the implementation plan?
- Review existing code against this spec?
- Identify code that needs refactoring to support this feature?"

Integration with Other Skills
This skill works well with:

Skill	Use Case
design_validation_tests_swarm	Generate validation tests from acceptance criteria
code_from_validation_tests_swarm	Implement code from the test strategy
plan_from_gh_issue_swarm	Create detailed plans from resulting epics/tasks
create_issues_from_plan_swarm	Break implementation plan into trackable issues

Agents
Agent	Focus
Staff Architect	System design, trade-offs, scalability
Product Analyst	Business alignment, completeness, edge cases
Quality Engineer	Test strategy, reliability, E2E coverage
User Experience Engineer	API/UX design, DX, documentation
Delivery Strategist	Risk, rollout, operational readiness

Example Prompts
Basic:

"Design a notification system for when users' subscriptions are about to expire"

With context:

"We need to add multi-tenant support to our API. Currently single-tenant. Must be backwards compatible. 200 tenants expected in year 1."

Feature enhancement:

"Users are complaining about slow search. Design an improved search feature that handles 10x our current query volume."

Bug-driven feature:

"We keep getting support tickets about failed payments. Design a retry and recovery system."

Scope exploration:

"We want to add real-time collaboration to our editor. Help me figure out the right scope for v1."
