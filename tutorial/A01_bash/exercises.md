# Chapter A1: exercises

Work inside `~/bash-practice` (`cd ~/bash-practice`). Type each answer yourself. Compare your output with **Expected**.
If you are stuck for more than 10 minutes, look at `solutions.md`, then close it and type the answer from memory.

| # | Task | Expected output |
|---|---|---|
| 1 | List the files inside `logs` | `run1.log`, `run2.log`, `run3.log` (one per line) |
| 2 | How many orders are in `orders.csv`? (do not count the header) | `10` |
| 3a | How many lines containing `ERROR` are there in all the logs? | `2` |
| 3b | Which log files contain `ERROR`? (names only) | `logs/run1.log` and `logs/run2.log` |
| 4 | Total amount of orders whose status is `done` | `117.25` |
| 5 | Number of orders per location | `4 boston`, `3 cambridge`, `3 somerville` (Mac shows leading spaces: fine) |
| 6 | Put the number of orders in a variable `n`, then print `rows: 10` using the variable | `rows: 10` |
| 7a | Print `yes` if the file mentions `refunded`, else `no`, on ONE line | `yes` |
| 7b | The same for the word `dispute` | `no` |
| 7c | Search for `dispute` quietly, then print the exit code | `exit code: 1` |
| 8 | For every log file print `file: number of ERROR lines` | `logs/run1.log: 1`, `logs/run2.log: 1`, `logs/run3.log: 0` |
| 9 | Write a script `check_errors.sh` that takes a folder, prints `errors found` and exits with code 1 if any `.log` file in it has `ERROR`, otherwise prints `clean`. Test both cases (delete `run1.log` and `run2.log` for the clean case) | first `errors found`, then after deleting: `clean` |
| 10 | Print the single order line with the highest amount (skip the header) | `9,boston,30.00,done` |
| 11 | Print the ids of the 3 biggest orders on ONE line, comma separated | `9,5,7` |
| 12 | Explain `infra/down.sh` line by line in a file `down_explained.md` (your own words) | no fixed answer: check it against lessons 5 to 9 |

## Bonus (no answer given: use `--help` and the lessons)

- B1: print the number of ERROR lines per log *only for the files that have at least one* (`grep -c` plus `grep -l`, or a loop with an `if`).
- B2: write `backup.sh` that copies `orders.csv` to `orders-YYYY-MM-DD.csv` using `$(date +%F)`, and refuses to overwrite an existing backup (use `[ -f … ]`).
- B3: change `check_errors.sh` so a missing folder argument prints a usage message and exits with code 2.

## Self-check before you tick the chapter

You can say in one sentence each: what a pipe does · what `$?` is · the difference between `;`, `&&`, `||` · why variables get double quotes ·
what `set -euo pipefail` protects you from · what `export` changes.
