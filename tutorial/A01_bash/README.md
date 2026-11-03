# Chapter A1: Bash and the command line

**Time:** 3 to 4 hours, in two sessions. **Goal:** you can read any line in `infra/up.sh` and `infra/down.sh`, and write small scripts yourself.
**You type everything.** Do not copy-paste the exercises: typing is how the options stick.

## Setup (once)

```bash
bash tutorial/A01_bash/make_sandbox.sh
cd ~/bash-practice
ls
```

You should see `logs` and `orders.csv`. Everything you break here is safe: running the setup command again recreates the folder.

Your Mac's terminal runs **zsh**. The scripts in this project start with `#!/usr/bin/env bash`, so they run in **bash**. For everything in this chapter the two behave the same, and the lessons point out the few differences.

---

## Lesson 1: Where am I, and what is here?

A shell is a program that reads a line you type, runs it, and prints the result. A *command* is the first word. Everything after it is an *argument*; arguments that start with `-` are *options* (also called flags) that change how the command behaves.

```bash
pwd                 # print working directory: where am I?
ls                  # list files here
ls -l               # long format: permissions, size, date
ls -la              # also show hidden files (names starting with a dot)
cd logs             # change directory into logs
cd ..               # go up one level (.. = parent folder, . = this folder)
cd ~                # go home (~ = your home folder)
cd -                # go back to the previous folder
```

**Paths.** `/Users/you/x` is *absolute* (starts at the root `/`). `logs/run1.log` is *relative* (starts from where you are). When a script says `cd "$(dirname "$0")"` it is making itself independent of where you ran it from (lesson 8).

**Options can be combined:** `ls -la` is `ls -l -a`. Most commands also have long names: `ls --help` (Linux) or `man ls` (Mac, press `q` to quit).

**Try it:** `ls -la ~/bash-practice` and find the `logs` folder.

## Lesson 2: Looking at files

```bash
cat orders.csv            # print the whole file
head -n 3 orders.csv      # first 3 lines
tail -n 3 orders.csv      # last 3 lines
tail -n +2 orders.csv     # everything FROM line 2 on (skips the header)
wc -l orders.csv          # count lines (wc = word count; -l = lines)
less orders.csv           # scroll; q quits
```

`tail -n +2` is the one beginners miss: `+2` means "start at line 2", so it drops the header line.

## Lesson 3: Input, output and pipes (the most important idea)

Every command has three channels: **stdin** (input), **stdout** (normal output), **stderr** (error messages). By default they connect to your keyboard and screen. You can rewire them:

```bash
ls > files.txt            # stdout into a file (overwrites)
ls >> files.txt           # stdout appended to the file
wc -l < orders.csv        # file into stdin
command 2> errors.txt     # only stderr into a file
command > out.txt 2>&1    # stdout and stderr into the same file
command > /dev/null       # throw the output away (/dev/null is a black hole)
```

A **pipe** `|` connects the stdout of one command to the stdin of the next. It is how you build tools out of small tools:

```bash
tail -n +2 orders.csv | wc -l        # skip header, then count: how many orders?
```

Read a pipeline left to right as "take this, then do that to the result".

## Lesson 4: The data toolkit (grep, sort, uniq, cut, awk, sed)

```bash
grep ERROR logs/run1.log          # lines containing ERROR
grep -c ERROR logs/run1.log       # count of matching lines
grep -l ERROR logs/*.log          # only the NAMES of files that match
grep -h ERROR logs/*.log          # hide the file names in the output
grep -v INFO logs/run1.log        # lines that do NOT match (v = invert)
grep -q ERROR logs/run1.log       # quiet: print nothing, only set the exit code (lesson 6)
grep -i error logs/run1.log       # ignore upper/lower case

cut -d, -f2 orders.csv            # split each line at commas, keep field 2
sort                              # sort lines; -n numbers, -r reverse, -t, -k3 = by field 3 split at commas
uniq -c                           # count consecutive identical lines (so sort first!)
paste -sd, -                      # join all lines into one, separated by commas
```

`*` in `logs/*.log` is a **glob**: the shell expands it to all matching file names *before* the command runs.

**awk** processes text line by line, with fields `$1 $2 …`. The pattern `awk -F, '$4=="done"{s+=$3} END{print s}' orders.csv` reads: *split at commas (-F,); for every line whose 4th field is "done", add the 3rd field to s; at the end print s.* You will use awk for quick sums and filters.

**sed** edits streams: `sed 's/ERROR/PROBLEM/' file` replaces the first ERROR on each line.

**Pipeline example:** orders per location:

```bash
cut -d, -f2 orders.csv | tail -n +2 | sort | uniq -c
```

Take the location column, drop the header, sort so equal names are neighbours, count the neighbours.

## Lesson 5: Variables, quotes and `$(...)`

```bash
name="Polat"            # NO spaces around =
echo "Hello $name"      # double quotes: variables are expanded
echo 'Hello $name'      # single quotes: printed exactly, nothing expanded
today=$(date +%F)       # $(command) = run the command and use its output as text
echo "Today is $today"
n=$((3 + 4))            # $(( )) = arithmetic
export AWS_REGION=us-east-1   # export = also visible to programs this shell starts
```

**Always put variables in double quotes** (`"$file"`): without quotes, a value with a space is split into two arguments. This is the #1 source of bad shell scripts.

`export` matters because a normal variable stays inside the shell. `down.sh` sets `export AWS_REGION=us-east-1`, so the `aws` and `cdk` programs it starts can see it.

**Special variables:** `$0` the script's own path · `$1 $2 …` the arguments given to the script · `$?` the exit code of the last command · `$HOME` your home folder.

## Lesson 6: Exit codes, `&&`, `||`, `;`

Every command ends with a number: **0 = success, anything else = failure.** You do not see it; check it with `$?`.

```bash
grep -q refunded orders.csv; echo $?     # 0: found
grep -q dispute orders.csv; echo $?      # 1: not found
```

```bash
cmd1 ; cmd2        # run cmd2 no matter what
cmd1 && cmd2       # run cmd2 only if cmd1 SUCCEEDED
cmd1 || cmd2       # run cmd2 only if cmd1 FAILED
cmd1 && cmd2 || cmd3     # "if cmd1 then cmd2 else cmd3" (careful: cmd3 also runs if cmd2 fails)
```

In `down.sh`: `[ "$answer" = "$ACCOUNT" ] || { echo "Cancelled"; exit 1; }` means *"check the answer matches; if NOT, print Cancelled and stop"*. `{ …; }` groups several commands.

## Lesson 7: Tests and `if`

`[ … ]` is a command that tests something and sets the exit code.

```bash
[ -f orders.csv ]            # true if it is a regular file
[ -d logs ]                  # true if it is a directory
[ -z "$x" ]                  # true if $x is empty
[ "$a" = "$b" ]              # string equal (spaces around = and the brackets are REQUIRED)
[ "$n" -gt 5 ]               # number greater than (-lt -ge -le -eq -ne)
[ ! -d .venv ]               # ! = not
```

```bash
if [ -d logs ]; then
  echo "logs exists"
else
  echo "no logs"
fi
```

In `down.sh`: `[ -d .venv ] || python3.11 -m venv .venv` = *"if there is no .venv folder, create one"*.

## Lesson 8: Loops and the script header

```bash
for f in logs/*.log; do
  echo "$f has $(grep -c ERROR "$f") errors"
done

for attempt in 1 2 3; do
  echo "attempt $attempt"
done

while read -r line; do echo "got: $line"; done < orders.csv
```

`down.sh` uses a loop to retry: *try `cdk destroy`; if it works, `break` out; if it fails three times, give up.*

**Making a script:**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
```

| Line | Meaning |
|---|---|
| `#!/usr/bin/env bash` | the "shebang": which program should run this file |
| `set -e` | stop at the first command that fails (otherwise the script keeps going after errors) |
| `set -u` | stop if you use a variable that was never set (catches typos) |
| `set -o pipefail` | a pipeline fails if ANY step fails, not just the last |
| `cd "$(dirname "$0")"` | go to the folder the script lives in, so relative paths work wherever you run it from |

Run a script with `bash script.sh`, or `chmod +x script.sh` once (make it executable) and then `./script.sh`.

## Lesson 9: Finding things, and calling other tools

```bash
find . -name "*.log"              # all .log files below here
find . -name "*.log" | xargs grep -l ERROR   # xargs: turn lines into arguments for another command
which python3                     # where is this program?
echo "$PATH"                      # the list of folders the shell searches for programs, separated by :
```

`export PATH="$PWD/.venv/bin:$PATH"` (from `down.sh`) puts the project's virtualenv first in the search list, so `python` and `cdk` mean the project's own copy.

Tools you use in this project, all driven from the shell: `git`, `docker compose`, `aws`, `cdk`, `pytest`. Their options follow the same rules as `ls -la`. Use `tool --help` and `tool subcommand --help` constantly.

`aws sts get-caller-identity --query Account --output text` means *ask AWS who I am, keep only the Account field, print it as plain text.* `--query` takes a JMESPath expression; quote it when it has brackets (zsh treats `[` specially).

## Lesson 10: Read a real script, line by line

Open `infra/down.sh` and read it with this chapter next to it:

```bash
cat infra/down.sh
```

Exercise 12 asks you to explain it line by line, in your own words.

## Common traps (zsh on a Mac)

| Trap | Fix |
|---|---|
| `zsh: no matches found: foo[0]` | quote it: `'foo[0]'` |
| Spaces in a file name break a command | quote variables: `"$file"` |
| `wc -l` output has leading spaces on Mac | use `$(( ))` or `tr -d ' '` to clean it |
| `sed -i` works differently on Mac (needs `-i ''`) | avoid `-i`; write to a new file |
| `rm -rf "$dir/"` with `dir` empty deletes `/` | use `set -u`; check variables before rm |

## Cheat sheet: 20 commands that matter

`pwd` `ls -la` `cd` `cat` `head` `tail -n +2` `wc -l` `grep -c/-l/-v/-q` `cut -d, -f` `sort -n -r` `uniq -c` `awk -F,` `sed 's/a/b/'` `find . -name` `xargs` `echo "$x"` `export` `chmod +x` `which` `man` / `--help`

## Finish the chapter

Do `exercises.md`. When all answers match, tick A1 in `TUTORIAL.md`.
