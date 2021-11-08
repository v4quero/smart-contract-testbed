#!/usr/bin/env bash
source "${PWD}/venv/bin/activate"
echo "$@"
python cmd.py "$@"
