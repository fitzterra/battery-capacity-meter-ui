#!/bin/bash

# Get the current branch name
current_branch=$(git rev-parse --abbrev-ref HEAD)

# Parse the reflog for the first checkout or branch creation entry for this branch
parent_line=$(git reflog --date=iso | grep -m1 -E "checkout: moving from|branch: Created from")

parent=''

if [[ "$parent_line" =~ moving\ from\ ([^[:space:]]+) ]]; then
    parent=${BASH_REMATCH[1]}
elif [[ "$parent_line" =~ Created\ from\ ([^[:space:]]+) ]]; then
    parent=${BASH_REMATCH[1]}
fi

if [[ -n $VERBOSE ]]; then
    if [[ -n $parent ]]; then
        echo "Likely parent branch: ${parent}"
    else
        echo "Could not determine parent branch from reflog."
    fi
else
    echo $parent
fi
