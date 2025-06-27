#!/bin/bash


ruff --help 2> /dev/null 1>&2
cf_code=$?
if [[ $cf_code -ne 0 ]]; then
        # if ruff is not present on the system,
        # only print warning message
        readonly MESSAGE="WARN: ruff not found, auto-formatting skipped"
        echo "$MESSAGE"
else
        staged_files=$(git diff --cached --name-only)

        # filter only existing files
        staged_files=$(echo "$staged_files" | while read -r file; do
                [[ -e "$file" && "$file" == *.py ]] && printf "%s " "$file"
        done)

        if [ -n "$staged_files" ]
        then
                ruff check --fix $staged_files || exit 1
                ruff format $staged_files
                git add $staged_files
        fi
fi

