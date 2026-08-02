# BioMesh Project Standards (STANDARDS.md)

**Purpose**

This document is the single source of truth for BioMesh. All contributors, AI models, and automation must follow these standards. If another document conflicts with this file, **STANDARDS.md takes precedence** unless explicitly superseded.

---

# 1. Project Goals

BioMesh is a scientifically grounded microbial simulation platform.

Primary priorities:

1. Scientific correctness
2. Reproducibility
3. Maintainability
4. Verification
5. Performance
6. User experience

No feature should compromise a higher priority.

---

# 2. Development Rules

* Complete only the requested work package.
* Never implement future phases.
* Never silently change scientific assumptions.
* Never invent biological constants.
* Prefer modifying existing modules over rewriting them.
* Stop immediately after acceptance criteria are satisfied.
* Do not automatically commit, push, merge, tag, or release.

---

# 3. Phase Names

Always use these exact names.

| ID  | Name                        |
| --- | --------------------------- |
| M0  | Repository Bootstrap        |
| P1  | Phase 1 – Core Model        |
| P1A | Phase 1 Audit               |
| P2  | Phase 2 – Colony System     |
| P2A | Phase 2 Audit               |
| P3  | Phase 3 – Desktop GUI       |
| P3A | Phase 3 Audit               |
| P4  | Phase 4 – Research Platform |
| P4A | Phase 4 Audit               |

Never invent alternate names.

---

# 4. Branch Names

| Phase | Branch                    |
| ----- | ------------------------- |
| M0    | m0-repository-bootstrap   |
| P1    | phase-1-core-model        |
| P1A   | audit-phase-1             |
| P2    | phase-2-colony-system     |
| P2A   | audit-phase-2             |
| P3    | phase-3-desktop-gui       |
| P3A   | audit-phase-3             |
| P4    | phase-4-research-platform |
| P4A   | audit-phase-4             |

---

# 5. Version Tags

| Phase | Tag          |
| ----- | ------------ |
| M0    | v0.0.0-m0    |
| P1    | v0.1.0       |
| P1A   | v0.1.1-audit |
| P2    | v0.2.0       |
| P2A   | v0.2.1-audit |
| P3    | v0.3.0       |
| P3A   | v0.3.1-audit |
| P4    | v0.4.0       |
| P4A   | v0.4.1-audit |

---

# 6. Commit Prefixes

Use:

* M0:
* P1:
* P1A:
* P2:
* P2A:
* P3:
* P3A:
* P4:
* P4A:

---

# 7. Repository Layout

```text
docs/
src/
tests/
experiments/
validation/
parameters/
outputs/
references/
.github/
```

Do not create duplicate top-level folders.

---

# 8. Python Version Policy

BioMesh targets **the newest stable Python version fully supported by all required runtime dependencies**.

If the configured version is unavailable or unsupported:

1. Stop.
2. Report the compatibility issue.
3. Recommend the newest fully supported version.
4. Do not silently change the version.

---

# 9. Required Checks

Before a phase is accepted:

* tests pass
* lint passes
* type checking passes
* documentation updated
* acceptance criteria satisfied

---

# 10. Audit Rules

Audits:

* verify only the requested phase
* report evidence
* classify findings
* recommend fixes
* never introduce features

---

# 11. Git Rules

AI must never:

* commit
* push
* merge
* tag
* create releases

unless explicitly instructed.

---

# 12. Token Efficiency

* Read only relevant files.
* Edit only affected files.
* Prefer diffs over rewrites.
* Keep summaries concise.
* Avoid repeating repository context.
* Avoid regenerating unchanged code.

---

# 13. Scientific Standards

Every scientific assumption must be:

* documented
* unit-aware
* reproducible
* testable

Unknown values must be identified as configurable parameters.

---

# 14. Documentation Authority

Read in this order:

1. STANDARDS.md
2. AGENTS.md
3. Current phase document
4. Current audit document (if applicable)

Ignore later phase documents unless explicitly instructed.

---

# 15. Acceptance Gate

A phase is complete only when:

* implementation finished
* tests passed
* audit passed (if applicable)
* documentation updated
* remaining risks documented

Only then should work proceed to the next phase.

