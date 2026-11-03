#!/usr/bin/env bash
# Creates a small practice folder with known files, so every exercise has one right answer.
#   bash make_sandbox.sh            -> ~/bash-practice
#   bash make_sandbox.sh /some/dir  -> that folder (its name must start with bash-practice)
# Safe to run again: it deletes and recreates ONLY the folder it creates.
set -euo pipefail
dir="${1:-$HOME/bash-practice}"
case "$(basename "$dir")" in bash-practice*) ;; *) echo "Refusing: the folder name must start with bash-practice"; exit 1;; esac
rm -rf "$dir"
mkdir -p "$dir/logs"
cd "$dir"

cat > orders.csv <<'CSV'
order_id,location,amount,status
1,boston,12.50,done
2,boston,8.00,done
3,cambridge,15.25,done
4,cambridge,9.75,refunded
5,somerville,22.00,done
6,boston,5.50,cancelled
7,somerville,18.40,done
8,cambridge,11.10,done
9,boston,30.00,done
10,somerville,7.25,refunded
CSV

cat > logs/run1.log <<'LOG'
2026-11-01 06:00:01 INFO replay_day started
2026-11-01 06:02:10 INFO replay_day finished
2026-11-01 06:02:11 INFO extract_to_bronze started
2026-11-01 06:05:40 ERROR extract_to_bronze timeout
LOG
cat > logs/run2.log <<'LOG'
2026-11-02 06:00:01 INFO replay_day started
2026-11-02 06:01:50 INFO replay_day finished
2026-11-02 06:01:51 INFO extract_to_bronze started
2026-11-02 06:04:30 INFO extract_to_bronze finished
2026-11-02 06:04:31 INFO dq_checks started
2026-11-02 06:05:02 ERROR dq_checks check 7 failed
LOG
cat > logs/run3.log <<'LOG'
2026-11-03 06:00:01 INFO replay_day started
2026-11-03 06:01:40 INFO replay_day finished
2026-11-03 06:01:41 INFO dq_checks started
2026-11-03 06:02:30 INFO dq_checks finished
LOG

echo "Practice folder ready: $dir"
