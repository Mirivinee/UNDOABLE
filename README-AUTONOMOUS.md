# Running UNDOABLE's build autonomously

Claude Code builds one task at a time from `PROGRESS.md` and commits.
`run-autonomous.sh` runs the tests and pushes to GitHub only if they pass.
It stops on failing tests, a reported blocker, no progress, or after `MAX_RUNS`.

## 1. GitHub token (scoped to this repo only)
GitHub → Settings → Developer settings → Fine-grained tokens → Generate:
- Repository access: **Only select repositories → UNDOABLE**
- Permissions: **Contents: Read and write** (nothing else)
- Short expiry (e.g. 30 days)

## 2. Build and start the sandbox
```bash
git clone https://github.com/Mirivinee/UNDOABLE.git && cd UNDOABLE
# copy the starter kit files into this folder, then:
docker build -t undoable-sandbox .
docker run -it --rm -v "$PWD":/work -e GH_TOKEN=<your_token> undoable-sandbox bash
```

## 3. Log in to Claude Code once (inside the container)
```bash
claude        # log in, then exit
```

## 4. First commit, then go
```bash
git add -A && git commit -m "chore: starter kit"
./run-autonomous.sh              # or: MAX_RUNS=5 ./run-autonomous.sh
```

## Safety built in
- Refuses to run outside a container
- Claude cannot push, force-reset, rebase, curl, or read `.env` (settings deny list + hook)
- Push happens only after `pytest` passes
- Stops on blockers, no progress, or run limit
- Token can only touch this one repo

Check `logs/run.log` and the commit history after each session, and read the code for each phase.
