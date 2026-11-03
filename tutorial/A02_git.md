# Chapter A2: Git and the GitHub workflow

**Time:** 2 hours. **Goal:** you can work on a branch, open and merge a PR, read history, and undo mistakes without fear.
**Practice area:** a scratch repo, never this project.

```bash
mkdir ~/git-practice && cd ~/git-practice && git init -b main
```

## 1. The model in five lines

- A **commit** is a snapshot of your files plus a message, a parent, an author and a hash (like `c08785c`).
- A **branch** is just a movable label pointing at a commit. Creating one is free.
- **HEAD** is "where I am now" (usually the current branch).
- Three areas: **working folder** (your files) → **staging area** (what the next commit will contain, `git add`) → **repository** (`git commit`).
- **Remote** (`origin`) is the copy on GitHub. `push` sends commits, `fetch` downloads them, `pull` = fetch + merge.

## 2. Daily commands (type each)

```bash
git status                       # what changed? what is staged?
git add file.txt                 # stage a file (git add -p stages parts)
git commit -m "Add file"         # snapshot
git log --oneline --graph -10    # history as a short list
git diff                         # unstaged changes; git diff --staged = staged changes
git switch -c fix-typo           # create and move to a new branch (older: git checkout -b)
git switch main                  # go back
git branch -vv                   # branches and what they track
```

**Exercise 1.** Create `a.txt`, commit; create branch `feature`, change `a.txt`, commit; switch to `main`; show that `a.txt` differs. Expected: `main` shows the old text, `feature` the new.

## 3. Merging and PRs

A **pull request** (PR) asks "merge my branch into main". It adds review, CI checks and a record. Flow used in this project:

1. `git switch -c my-change origin/main` (start from the latest main)
2. edit, test, `git commit`
3. `git push -u origin my-change`
4. `gh pr create` (or the GitHub page), wait for **CI green**
5. a human merges; then `git switch main && git pull`

**Merge strategies** (the green button): *merge commit* (keeps all commits + a merge commit; this project), *squash* (all commits become one), *rebase* (replays commits on top of main, linear history).

```bash
git merge feature                # bring feature into the current branch
git rebase main                  # replay my commits on top of main (rewrites MY branch only)
```

**Rule:** never rebase or force-push a branch other people use. **Never push to main directly** (this project's rule; chapter C1 enforces it with branch protection).

**Conflicts:** two branches changed the same lines. Git marks them (`<<<<<<<`, `=======`, `>>>>>>>`). Edit the file to the final text, `git add file`, `git commit` (or `git rebase --continue`).

**Exercise 2.** Create a conflict: on `main` and on `feature`, change the same line differently; merge; resolve; commit. Expected: `git log --graph` shows the merge.

## 4. Worktrees (why this project has `.claude/worktrees/…`)

A **worktree** is a second folder checked out on a different branch from the same repository. You can work on two branches at once without stashing.

```bash
git worktree add ../git-practice-fix -b fix-x      # new folder on a new branch
git worktree list
git worktree remove ../git-practice-fix
```

## 5. Undoing things safely

| Situation | Command |
|---|---|
| Discard changes in a file (not committed) | `git restore file` |
| Unstage a file | `git restore --staged file` |
| Fix the last commit's message or add a forgotten file | `git add file && git commit --amend` (only if not pushed) |
| Undo a pushed commit | `git revert <hash>` (creates a new commit that reverses it) |
| Move the branch back, keep changes staged | `git reset --soft HEAD~1` |
| Move the branch back and **throw changes away** | `git reset --hard <hash>` (dangerous) |
| "I lost a commit!" | `git reflog` lists where HEAD has been; `git switch -c rescue <hash>` |
| Temporarily set work aside | commit it (preferred), or `git stash push -u -m "tag"` |

**Exercise 3.** Commit something, `git reset --hard HEAD~1`, then recover it with `git reflog` and `git switch -c rescue <hash>`. Expected: the file is back.

## 6. Good habits

- Small commits with messages that say *why* ("Fix MWAA log level: the API requires one for disabled modules").
- One topic per PR. Run the tests before pushing.
- `.gitignore` for data, secrets, virtualenvs. **Never commit secrets**; if you did, rotate the secret (deleting the commit is not enough).
- Tags mark releases: `git tag v1.0 && git push --tags`.

## 7. Read this project's history

```bash
git log --oneline --graph -20
git show c08785c --stat
git log --follow -p -- dags/globalpartners_daily.py | head -80
git blame dags/globalpartners_daily.py | head -20
```

Pick any bug from `docs/decisions.md` (MWAA log level, `PYTHONPATH`) and find the PR that fixed it.

## Interview questions

1. Merge vs rebase? (merge preserves history; rebase makes it linear but rewrites commits)
2. What is HEAD? What is a detached HEAD?
3. How do you undo a pushed commit? (`revert`)
4. What is the staging area for? (build precise commits)
5. How do you resolve a conflict? What causes one?
6. What is a PR and what should it contain? (small change, description, tests, CI green)
7. What does `git fetch` do versus `git pull`?
8. How do you find which commit introduced a bug? (`git bisect`)

## Done when

You complete Exercises 1 to 3 and make a PR on a scratch GitHub repo (create one with `gh repo create git-practice --private --source . --push`), see CI or at least the diff, merge it, and delete the branch.
