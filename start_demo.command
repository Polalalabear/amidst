#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -S "$task_root/scripts/start_q1q5_demo.py" "$@"
