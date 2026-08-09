# BioMesh Git Workflow for Linux

`docs/STANDARDS.md` Section 11 is the canonical BioMesh Git policy. This guide
is its operational companion. Codex follows the completion workflows
automatically when their gates are met; future work-package prompts do not need
to repeat Git instructions.

## 1. Branch and tag names

Use the branch and version-tag tables in `docs/STANDARDS.md` Sections 4 and 5.
Commit messages begin with the phase or audit prefix in Section 6. A
work-package commit also includes its work-package ID, for example:

```bash
git commit -m "P2: P2-WP01 implement quorum signal"
```

An audit-evidence commit uses the corresponding audit prefix, for example:

```bash
git commit -m "P2A: record accepted Phase 2 Audit evidence"
```

## 2. Work-package completion

When and only when a work package satisfies every acceptance criterion, run all
required verification commands:

```bash
pytest -q
ruff check .
mypy src
git diff --check
python -m biomesh --help
```

If any command fails, do not commit or push. Report the failed command and
preserve the worktree for repair.

If every command passes, review the worktree before changing Git state:

```bash
git status
git diff
```

Confirm only expected files changed. Stage only the files relevant to the work
package, inspect the staged diff, then commit and push the current branch:

```bash
git add src/biomesh/example.py tests/test_example.py CHANGELOG.md docs/PHASE_STATUS.md
git diff --staged
git commit -m "P2: P2-WP01 implement quorum signal"
git push
```

Never use `git add .` or `git add -A` for routine work-package completion in a
dirty worktree. Report the resulting commit SHA, branch, and files committed.

## 3. Accepted phase-audit completion

Perform this workflow only after the applicable phase audit is accepted. The
phase branch below means the branch containing the accepted audit evidence.

First, inspect and commit only the audit-related changes, then push that branch:

```bash
git status
git add docs/PHASE_STATUS.md CHANGELOG.md docs/02_PHASE_ONE_AUDIT.md
git diff --staged
git commit -m "P1A: record accepted Phase 1 Audit evidence"
git push
```

Then merge the accepted phase branch into `main` with a merge commit, push it,
create the canonical tag for the accepted audit from `docs/STANDARDS.md` Section
5, and push the tag:

```bash
git switch main
git merge --no-ff <phase-branch> -m "P1A: merge accepted Phase 1 Audit"
git push origin main
git tag -a v0.1.1-audit -m "P1A: Phase 1 Audit"
git push origin v0.1.1-audit
```

Report the merge commit SHA, tag, and current branch. Do not merge a phase that
has not passed its audit.

## 4. Safety rules

Never automatically execute any of the following:

```text
git push --force
git reset --hard
interactive rebase
history rewrite
branch deletion
tag deletion
GitHub repository-setting changes
```

Do not bypass failed verification. Do not automatically create releases or pull
requests; those actions require separate authorization.

## 5. Routine inspection and recovery

Inspect before changing Git state:

```bash
git status
git diff
git log --oneline --decorate -10
```

To remove a file from the index without discarding its edits:

```bash
git restore --staged path/to/file
```

If a merge conflict occurs, inspect it, resolve only the indicated files, stage
those files, and create the merge commit. If the merge must be abandoned, use
`git merge --abort`. Do not use destructive reset or rewrite commands as
conflict recovery.

## 6. Repository setup reference

Install Git and the GitHub CLI on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git gh
```

Set identity and authenticate before a workflow needs to push:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
gh auth login
```

For a new clone, set up the current phase branch from `main` before beginning a
new phase. The automated completion workflow never creates, deletes, rewrites,
or force-pushes branches.

## 7. Data hygiene

Do not commit generated runs. Commit only small reference fixtures. If large
datasets become necessary, add their tracking policy in a separately approved
work package.
