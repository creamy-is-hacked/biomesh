# BioMesh Phase 2 — Communication, Matrix, and Competition

## Goal
Extend the audited Phase 1 model with quorum sensing, EPS-mediated biofilm behavior, resource competition, physiological states, and shear-driven detachment.

## Completion Gate
Phase 2 is complete only when all new mechanisms are independently verified, competition experiments are reproducible across replicates, sensitivity analysis is complete, and the Phase 2 audit passes.

## Scope
Implement:
- Diffusing quorum signal.
- Hill-response activation and optional positive feedback.
- EPS production with explicit metabolic cost.
- Producer and nonproducer strains.
- EPS-dependent adhesion and detachment resistance.
- Active, slow, dormant, dead, and detached states.
- Waste field.
- Simplified shear erosion.
- Replicated experiments and sensitivity analysis.

Do not implement:
- Organism-specific gene networks beyond the chosen abstraction.
- Host infection models.
- Horizontal gene transfer unless separately validated.
- 3D or GPU acceleration before the audit passes.

## Scientific Extensions
Signal field:

\[
\frac{\partial A}{\partial t}=D_A\nabla^2A+q_A-k_AA
\]

Quorum response:

\[
Q(A)=\frac{A^n}{K_A^n+A^n}
\]

Optional feedback:

\[
q_A=q_{basal}+q_{induced}Q(A)
\]

EPS allocation:

\[
r_{EPS}=f_{EPS}Q(A)\mu X
\]

Growth after allocation:

\[
r_{growth}=[1-f_{EPS}Q(A)]\mu X
\]

All state transitions must use explicit thresholds, delays, and units.

## Work Packages

### P2.1 Quorum signal
- Add production, diffusion, decay, and cell-local sensing.
- Support basal and induced production.
- Record signal exposure and activation history.

Acceptance:
- Diffusion-decay benchmark passes.
- Uniform concentration reproduces the Hill curve.
- Activation changes with geometry and transport, not cell count alone.

### P2.2 EPS model
- Add EPS density field or explicit local matrix representation.
- Couple EPS production to quorum state.
- Charge producers a configurable growth cost.
- Increase local cohesion and attachment strength.

Acceptance:
- EPS production conserves allocated substrate or biomass-equivalent mass.
- Higher allocation reduces producer growth in isolation.
- Adhesion changes monotonically with EPS in controlled tests.

### P2.3 Competition
- Add producer and nonproducer strains sharing resources.
- Allow nonproducers to benefit from nearby matrix without paying production cost.
- Track frequencies, spatial segregation, lineage, and local fitness.

Acceptance:
- Identical strains remain neutral within stochastic variation.
- A configured production cost is measurable in well-mixed controls.
- Mixed outcomes reproduce from fixed seeds.

### P2.4 Physiological states
- Add active, slow, dormant, dead, and detached states.
- Base transitions on recent nutrient/oxygen history and configurable delay.
- Let dead biomass persist or recycle according to an explicit rule.

Acceptance:
- State transitions pass threshold and delay tests.
- Dormant cells consume less than active cells.
- State totals reconcile with the population ledger.

### P2.5 Waste and shear
- Add a diffusing waste field with production and decay/removal.
- Add simplified surface-parallel shear.
- Detachment probability or force must depend on exposure, attachment, and EPS.

Acceptance:
- Zero shear causes no shear-driven detachment.
- Increasing shear increases detachment in controlled tests.
- Stronger EPS lowers detachment under otherwise identical conditions.

### P2.6 Experiments
Required experiments:
- Producer monoculture.
- Nonproducer monoculture.
- 50:50 competition.
- Multiple inoculation patterns.
- Constitutive versus quorum-controlled EPS.
- Quorum threshold sweep.
- Nutrient and oxygen sweep.
- EPS cost sweep.
- Shear sweep.

Run multiple seeds per condition. Save summary statistics and raw run manifests.

## Required Outputs
- Producer frequency over time.
- Total biomass and EPS.
- Quorum-active fraction.
- Signal, nutrient, oxygen, EPS, and waste maps.
- Active, dormant, dead, and detached biomass.
- Biofilm thickness, roughness, and footprint.
- Penetration depths.
- Detachment rate.
- Replicate mean, variance, and confidence intervals.
- Sensitivity ranking.

## Codex Execution Prompt
```text
Implement BioMesh Phase 2 only after confirming the audited Phase 1 tag.
Read AGENTS.md, this file, and the Phase 1 audit result first.
Add one mechanism per work package with isolated tests and benchmark cases.
Do not alter audited Phase 1 behavior without a regression test and a
recorded reason.

For every new mechanism:
1. State equations, units, assumptions, and unknown parameters.
2. Add unit and integration tests.
3. Add one controlled validation experiment.
4. Run the affected tests, then the full suite.
5. Update CHANGELOG.md, LIMITATIONS.md, and PHASE_STATUS.md.

Prefer compact diffs. Do not paste full logs unless a test fails.
Stop when the Phase 2 audit can be executed.
```

## Token-Efficient Codex Workflow
- Provide only this file, AGENTS.md, the audit result, and current work-package files.
- Keep each request limited to one mechanism and its tests.
- Ask Codex to inspect before editing.
- Reuse shared numerical operators from Phase 1.
- Store experiment definitions as parameter files rather than long prompts.
- Summarize changed files, test results, assumptions, and next action in under 250 words.

## End-of-Phase Update
1. Freeze a release candidate branch.
2. Run all tests, experiments, and sensitivity workflows.
3. Update README, CHANGELOG, parameter sources, and limitations.
4. Push the release candidate.
5. Run `04_PHASE_TWO_AUDIT.md`.
6. Fix findings before tagging the release.
