# Chapter A1: solutions

Every command below was run on a Mac against the sandbox and produced the **Expected** output. Try first, then compare.

```bash
# 1
ls logs

# 2  (tail -n +2 starts from line 2 = drops the header; wc -l counts lines)
tail -n +2 orders.csv | wc -l

# 3a  (-h hides file names, so each match is one line)
grep -h ERROR logs/*.log | wc -l
# 3b  (-l prints only file names)
grep -l ERROR logs/*.log

# 4  (-F, = fields split at commas; $4 is status, $3 is amount; END runs after the last line)
awk -F, '$4=="done"{s+=$3} END{print s}' orders.csv

# 5  (location column -> drop header -> sort -> count neighbours)
cut -d, -f2 orders.csv | tail -n +2 | sort | uniq -c

# 6  ($(( )) turns "      10" into the number 10)
n=$(tail -n +2 orders.csv | wc -l)
echo "rows: $((n))"

# 7a / 7b  (-q = quiet, only the exit code; && runs on success, || on failure)
grep -q refunded orders.csv && echo yes || echo no
grep -q dispute orders.csv && echo yes || echo no
# 7c
grep -q dispute orders.csv; echo "exit code: $?"

# 8
for f in logs/*.log; do echo "$f: $(grep -c ERROR "$f")"; done

# 9  check_errors.sh
#!/usr/bin/env bash
set -euo pipefail
if grep -q ERROR "$1"/*.log; then
  echo "errors found"
  exit 1
fi
echo "clean"
```

Test for 9 (the second `bash` line prints `exit=1` because the script exited with 1):

```bash
bash check_errors.sh logs || echo "exit=$?"
rm logs/run1.log logs/run2.log
bash check_errors.sh logs
```

```bash
# 10  (sort numerically (-n), reverse (-r), by field 3 split at commas; head -n 1 = the first line)
tail -n +2 orders.csv | sort -t, -k3 -nr | head -n 1

# 11  (top 3, keep field 1, join with commas)
tail -n +2 orders.csv | sort -t, -k3 -nr | head -n 3 | cut -d, -f1 | paste -sd, -
```

**Exercise 12 (hints for what each part of `down.sh` does):**

- `set -euo pipefail`: stop on the first error, on unset variables, and on failed pipeline steps.
- `cd "$(dirname "$0")"`: work from the `infra` folder wherever you launched it.
- `ACCOUNT=$(aws sts get-caller-identity …)`: ask AWS for your account id and keep it in a variable.
- `read -r -p "…" answer` then `[ "$answer" = "$ACCOUNT" ] || { …; exit 1; }`: make the person type the account id; cancel if different.
- `[ -d .venv ] || python3.11 -m venv .venv`: create a virtualenv only if it does not exist.
- `export PATH="$PWD/.venv/bin:$PATH"`: use the project's own tools first.
- the `for attempt in 1 2 3` loop: retry `cdk destroy` up to 3 times, waiting 5 minutes between tries; `break` on success.
- `python cleanup.py`: remove what CloudFormation leaves behind.
