# BioMesh Start Here — M0 – Repository Bootstrap Prompt and Model Routing

Use this file first. Copy only the prompt below into a GPT or Codex coding session opened at the BioMesh repository root. The model must stop after M0 – Repository Bootstrap; P1 – Phase 1 – Core Model begins in `01_PHASE_ONE_CORE_MODEL.md` only after M0 satisfies its acceptance gate and is committed under the canonical Git workflow.

## Recommended Model for M0 – Repository Bootstrap

- **Default:** GPT-5.6 Terra, high effort. It balances code quality and token use.
- **Escalate to:** GPT-5.6 Sol, high effort, only for architecture/tooling failures Terra cannot resolve.
- **Fallback on other providers:** use a strong repository-aware coding model with tool access, tests, and patch editing.

## Copy/Paste Bootstrap Prompt

```text
You are the implementation agent for BioMesh, a scientifically grounded 2D bacterial biofilm simulator that will later become a Linux desktop research platform.

TASK
Complete M0 – Repository Bootstrap only: establish a clean, tested, documented Python repository. Do not implement diffusion, metabolism, cells, mechanics, quorum sensing, EPS, competition, simulation rendering, or GUI features.

CONTEXT TO READ
1. Read `docs/STANDARDS.md` first, then `AGENTS.md`.
2. Inspect the repository before editing.
3. Read only:
   - docs/00_PACKAGE_INDEX.md
   - docs/01_PHASE_ONE_CORE_MODEL.md: Goal, Scope, Repository Layout, and P1.1
   - docs/05_GITHUB_LINUX_WORKFLOW.md: setup and daily workflow sections
4. Open additional files only when directly needed for M0.
4. Do not restate these documents in your response.

DELIVERABLES
Create or minimally update:
- `pyproject.toml` with package metadata, the policy-resolved newest stable Python version fully supported by all required runtime dependencies, runtime dependencies named in P1 – Phase 1 – Core Model, and dev tools: pytest, ruff, and mypy.
- `src/biomesh/__init__.py`, `src/biomesh/__main__.py`, and a small typed CLI so `python -m biomesh --help` works.
- `tests/` with focused import, version, and CLI-help tests.
- `.github/workflows/ci.yml` running install, lint, type check, and tests on Linux.
- `.gitignore`, `README.md`, `AGENTS.md`, `CHANGELOG.md`, and `LIMITATIONS.md`.
- `docs/ARCHITECTURE.md`, `docs/BIOLOGICAL_ASSUMPTIONS.md`, `docs/PARAMETER_SOURCES.md`, and `docs/PHASE_STATUS.md`.
- Empty project directories only where needed: `parameters/`, `experiments/`, `validation/`, and `outputs/`; preserve empty directories with `.gitkeep` when appropriate.

DOCUMENTATION CONTRACT
- `AGENTS.md`: concise repository rules, commands, phase boundaries, SI-unit rule, no invented constants, tests before features, and explicit failure over silent correction.
- `ARCHITECTURE.md`: current M0 structure and dependency direction; mark future components as planned, not implemented.
- `BIOLOGICAL_ASSUMPTIONS.md`: state that no biological model is implemented at M0 and reserve a compact assumption-record format.
- `PARAMETER_SOURCES.md`: define fields for name, value, unit, source, uncertainty, notes, and calibration status; add no guessed values.
- `PHASE_STATUS.md`: M0 status, commands run, results, known blockers, and next work package; keep under 120 lines.
- Do not choose a software license unless the repository already specifies one. Record the decision as pending instead.

IMPLEMENTATION RULES
- Preserve correct existing work; patch instead of regenerating.
- Keep modules small and typed. Avoid frameworks and abstractions not required by M0.
- Do not add placeholder simulation classes or fake scientific behavior.
- Do not invent biological constants, citations, benchmark results, or test success.
- Use existing dependency versions unless they are broken; avoid unnecessary pinning.
- After every acceptance criterion and required check passes, follow the
  canonical work-package Git workflow in `docs/STANDARDS.md` Section 11.
- Do not create pull requests or releases automatically.
- Do not modify the planning files unless a path or command is objectively incorrect.

TOKEN DISCIPLINE
- Give a plan of at most 8 bullets, then act.
- Work from repository files; do not paste full files into chat.
- Prefer targeted patches and concise test output.
- Do not explain routine code line by line.
- Stop when acceptance checks pass or a concrete blocker prevents them.
- Final response: changed files, commands/results, blockers, and, when the
  work package passes, the commit SHA, branch, and files committed; maximum 20
  lines.

REQUIRED CHECKS
Run from a clean environment when feasible:
1. `python3.14 -m venv .venv`
2. `source .venv/bin/activate`
3. `python -m pip install --upgrade pip`
4. `python -m pip install -e ".[dev]"`
5. `python -m biomesh --help`
6. `ruff check .`
7. `mypy src`
8. `pytest -q`

If the policy-resolved Python version is unavailable or unsupported by a required runtime dependency, stop, report the compatibility issue, and recommend the newest fully supported version. Do not silently change the version.

ACCEPTANCE GATE
M0 passes only when:
- package installation succeeds;
- CLI help exits successfully;
- lint, typing, and tests pass;
- CI mirrors the local commands;
- documentation distinguishes implemented work from planned work;
- no P1 – Phase 1 – Core Model scientific behavior has been added;
- `git diff` is reviewable before the canonical work-package Git workflow is
  performed.

Begin by inspecting the repository and reporting only material conflicts with this task. Then implement M0.
```

## Model Routing for the Remaining Package

Use a fresh session per work package or audit. Prefer the lowest-cost model capable of passing the acceptance gate; escalate only after one focused repair attempt.

| Document / work | Recommended model | Effort | Notes |
|---|---|---:|---|
| M0 – Repository Bootstrap | GPT-5.6 Terra | High | Repository, tooling, docs, CLI, CI. |
| P1 – Phase 1 – Core Model (P1.1 and P1.6) | GPT-5.6 Terra | High | Configuration and outputs are bounded engineering tasks. |
| P1 – Phase 1 – Core Model (P1.2–P1.5) | GPT-5.6 Sol | High | Numerical methods, kinetics, geometry, and mechanics. Use max only for unresolved failures. |
| P1A – Phase 1 Audit | GPT-5.6 Sol | Max | Fresh reviewer session; do not reuse the builder's conclusions. |
| P2 – Phase 2 – Colony System (P2.1–P2.5) | GPT-5.6 Sol | High | Coupled scientific behavior and state transitions. |
| P2 – Phase 2 – Colony System (P2.6) | GPT-5.6 Terra | High | Experiment harnesses after scientific interfaces stabilize. |
| P2A – Phase 2 Audit | GPT-5.6 Sol | Max | Independent scientific and numerical audit. |
| P3 – Phase 3 – Desktop GUI (P3.1 and P3.5) | GPT-5.6 Sol | High | API boundaries, threading, checkpoints, and state integrity. |
| P3 – Phase 3 – Desktop GUI (P3.2–P3.4 and P3.6) | GPT-5.6 Terra | High | Desktop shell, viewer, editor, analytics, and exports. |
| P3A – Phase 3 Audit | GPT-5.6 Sol | High | Fresh reviewer session; verify GUI/CLI scientific equivalence. |
| P4 – Phase 4 – Research Platform (P4.1, P4.3, P4.5, P4.7) | GPT-5.6 Sol | High | Project schema, plugins, queue recovery, acceleration boundary. |
| P4 – Phase 4 – Research Platform (P4.2, P4.4, P4.6) | GPT-5.6 Terra | High | Reports, registry UI/data, portability, and packaging. |
| P4A – Phase 4 Audit | GPT-5.6 Sol | Max | Independent release and reproducibility audit. |
| P5 – Security and Distribution Hardening (P5-WP01, P5-WP02, P5-WP05) | GPT-5.6 Terra | High | Threat requirements, build provenance, and installer lifecycle. |
| P5 – Security and Distribution Hardening (P5-WP03, P5-WP04) | GPT-5.6 Sol | Max | Cryptographic archive policy and plugin isolation are security-critical. |
| P5A – Phase 5 Audit | GPT-5.6 Sol | Max | Fresh security-focused reviewer; challenge trust boundaries and failure isolation. |
| P6 – Portable Operations | GPT-5.6 Sol | High | Queue persistence, rebinding, recovery, and artifact separation. |
| P6A – Phase 6 Audit | GPT-5.6 Sol | Max | Fresh cross-install portability and recovery audit. |
| P7/P7A – Calibration and Validation | GPT-5.6 Sol plus qualified domain review | Max | Evidence, statistics, identifiability, held-out validation, and scientific claims. |
| P8/P8A – 3D and Accelerated Computing | GPT-5.6 Sol | Max | Numerical contracts, conservation, backend equivalence, failure isolation, and performance methodology. |
| P9 – Version 1 Release | GPT-5.6 Terra | High | Contract freeze, migrations, packaging, documentation, and rehearsal only. |
| P9A – Version 1 Release Audit | GPT-5.6 Sol | Max | Fresh independent release audit; sole authority for `v1.0.0`. |
| Mechanical formatting or typo fixes | GPT-5.6 Luna | Low/Medium | Never use Luna for scientific design or audit sign-off. |

### Capability Fallback

When these exact models are unavailable:
- **Sol role:** strongest available reasoning/coding model.
- **Terra role:** balanced coding model with repository tools.
- **Luna role:** low-cost model for deterministic, low-risk edits.

## Per-Work-Package Invocation

After M0 – Repository Bootstrap is accepted and committed under the canonical
workflow, begin each package with this compact wrapper:

```text
Execute only [WORK PACKAGE ID] from [DOCUMENT]. Read docs/STANDARDS.md,
then AGENTS.md, docs/PHASE_STATUS.md, that package section, and directly
affected code/tests.
Obey its acceptance criteria. Patch existing work; do not expand scope.
Run focused tests first, then required regression tests. Update PHASE_STATUS
and CHANGELOG with evidence. When all acceptance criteria and the required
verification commands pass, follow the canonical work-package Git workflow in
docs/STANDARDS.md Section 11. Final report <=20 lines.
```

For audits, replace it with:

```text
Act as an independent auditor. Execute [AUDIT DOCUMENT] against the current
repository. Do not trust prior summaries. Re-run evidence, identify PASS/FAIL
per gate, and make no code changes unless explicitly asked after the report.
Keep raw logs in repository artifacts; return only findings and blocking fixes.
```
