# BioMesh GitHub Workflow for Linux

## 1. Install Git and GitHub CLI
Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y git gh
```

Set identity:
```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Authenticate:
```bash
gh auth login
```
Choose GitHub.com, HTTPS, and browser authentication.

## 2. Create the local repository
```bash
mkdir -p ~/Projects/biomesh
cd ~/Projects/biomesh
git init -b main
```

Copy every Markdown file from the BioMesh planning package into `docs/`, then create the base structure:
```bash
mkdir -p docs src/biomesh tests experiments parameters validation outputs
printf "# BioMesh\n" > README.md
touch AGENTS.md CHANGELOG.md LIMITATIONS.md
```

Create `.gitignore`:
```bash
cat > .gitignore <<'GITIGNORE'
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
build/
dist/
*.egg-info/
outputs/*
!outputs/.gitkeep
.env
.DS_Store
GITIGNORE

touch outputs/.gitkeep
```

## 3. Create the GitHub repository
From the project directory:
```bash
gh repo create biomesh --public --source=. --remote=origin
```
Use `--private` instead of `--public` if preferred.

Initial commit:
```bash
git add README.md AGENTS.md CHANGELOG.md LIMITATIONS.md .gitignore docs src tests experiments parameters validation outputs/.gitkeep
git status
git commit -m "chore: initialize BioMesh repository"
git push -u origin main
```

## 4. Phase 1 branch
```bash
git switch -c phase/1-core-model
```

Normal update cycle:
```bash
git status
git diff
git add <specific-files>
git diff --staged
git commit -m "feat: implement carbon and oxygen diffusion"
git push -u origin phase/1-core-model
```

Prefer small commits:
- `feat:` new behavior.
- `fix:` bug correction.
- `test:` tests only.
- `docs:` documentation.
- `refactor:` behavior-preserving cleanup.
- `chore:` tooling or maintenance.

## 5. End of Phase 1
Run tests and audit:
```bash
pytest -q
```

Update status documents, then commit:
```bash
git add .
git diff --staged
git commit -m "docs: complete Phase 1 audit evidence"
git push
```

Create pull request:
```bash
gh pr create --base main --head phase/1-core-model \
  --title "Phase 1: audited core biofilm model" \
  --body "Implements and audits the Phase 1 reaction-diffusion and individual-cell foundation."
```

After the PR is reviewed and checks pass:
```bash
gh pr merge --squash --delete-branch

git switch main
git pull --ff-only

git tag -a v0.1.0-phase1 -m "BioMesh Phase 1 audited core model"
git push origin v0.1.0-phase1
```

Create release:
```bash
gh release create v0.1.0-phase1 --generate-notes --title "BioMesh Phase 1"
```

## 6. Phase 2 branch
```bash
git switch main
git pull --ff-only
git switch -c phase/2-colony-system
```

Use the same inspect, stage, commit, and push cycle:
```bash
git status
git diff
git add <specific-files>
git diff --staged
git commit -m "feat: add quorum signal diffusion and decay"
git push -u origin phase/2-colony-system
```

## 7. End of Phase 2
Run full validation and the Phase 2 audit, then:
```bash
git add .
git diff --staged
git commit -m "docs: complete Phase 2 audit evidence"
git push

gh pr create --base main --head phase/2-colony-system \
  --title "Phase 2: quorum, EPS, and competition" \
  --body "Adds and audits quorum sensing, EPS, competition, physiological states, and detachment."
```

After checks and review:
```bash
gh pr merge --squash --delete-branch

git switch main
git pull --ff-only

git tag -a v0.2.0 -m "BioMesh audited quorum, EPS, and competition model"
git push origin v0.2.0

gh release create v0.2.0 --generate-notes --title "BioMesh v0.2.0"
```

## 8. Safe daily commands
Inspect before changing Git state:
```bash
git status
git diff
git log --oneline --decorate -10
```

Undo unstaged edits to one file:
```bash
git restore path/to/file
```

Unstage a file without deleting edits:
```bash
git restore --staged path/to/file
```

Amend the latest local commit:
```bash
git add <files>
git commit --amend
```
Do not amend commits already shared unless you understand force-pushing.

## 9. Basic merge conflict recovery
After Git reports a conflict:
```bash
git status
```
Open conflicted files and resolve markers:
```text
<<<<<<< HEAD
current branch
=======
incoming branch
>>>>>>> other-branch
```
Then:
```bash
git add <resolved-files>
git commit
```
Abort the merge if needed:
```bash
git merge --abort
```

## 10. Issues and milestones
Create milestones in GitHub:
- Phase 1 — Core Model.
- Phase 1 Audit.
- Phase 2 — Colony System.
- Phase 2 Audit.
- Phase 3 — Desktop GUI.
- Phase 3 Audit.
- Phase 4 — Research Platform.
- Phase 4 Audit.

Create one issue per work package or audit failure. From the terminal:
```bash
gh issue create --title "P1.2: implement solute fields" --body "See docs/01_PHASE_ONE_CORE_MODEL.md"
```

## 11. Large data
Do not commit generated runs. Commit only small reference fixtures.

If large datasets later become necessary:
```bash
sudo apt install git-lfs
git lfs install
git lfs track "validation/data/*.parquet"
git add .gitattributes
git commit -m "chore: track validation datasets with Git LFS"
```

## 12. Token-efficient Codex and Git practice
- Give Codex one issue or work package at a time.
- Ask it to inspect first and return a concise plan.
- Request patches rather than full repository rewrites.
- Commit after each passing work package.
- Keep audit evidence in files, not repeated in prompts.
- Use `git diff` as the source of truth for review.
- Start new Codex sessions at phase or issue boundaries.

## 12. Phase 3 branch and release
```bash
git switch main
git pull --ff-only
git switch -c phase/3-desktop-gui
# inspect, stage specific files, commit, and push regularly
git push -u origin phase/3-desktop-gui
```

After `07_PHASE_THREE_AUDIT.md` passes:
```bash
git add .
git commit -m "docs: complete Phase 3 audit evidence"
git push
gh pr create --base main --head phase/3-desktop-gui \
  --title "Phase 3: desktop scientific workbench" \
  --body "Adds and audits the Linux desktop GUI without changing model science."
gh pr merge --squash --delete-branch
git switch main && git pull --ff-only
git tag -a v0.3.0 -m "BioMesh audited desktop scientific workbench"
git push origin v0.3.0
gh release create v0.3.0 --generate-notes --title "BioMesh v0.3.0"
```

## 13. Phase 4 branch and release
```bash
git switch main
git pull --ff-only
git switch -c phase/4-research-platform
git push -u origin phase/4-research-platform
```

After `09_PHASE_FOUR_AUDIT.md` passes:
```bash
git add .
git commit -m "docs: complete Phase 4 audit evidence"
git push
gh pr create --base main --head phase/4-research-platform \
  --title "Phase 4: reproducible research platform" \
  --body "Adds audited campaigns, plugins, local queueing, portable projects, and packaging."
gh pr merge --squash --delete-branch
git switch main && git pull --ff-only
git tag -a v0.4.0 -m "BioMesh audited reproducible research platform"
git push origin v0.4.0
gh release create v0.4.0 --generate-notes --title "BioMesh v0.4.0"
```

## 14. Release order
Do not skip audit gates:
```text
v0.1.0-phase1 -> v0.2.0 -> v0.3.0 -> v0.4.0
core science     colony    desktop    platform
```

