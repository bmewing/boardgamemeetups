#!/bin/bash
set -e
# Runs once before the function build, with functions/lib/ as the working directory.
# Vendors the backend's `app` package for packages/core/app/.include to pick up. This
# stage is a bare shell (no Python), so it only copies files.
rm -rf app
cp -r ../../backend/app ./app
find ./app -name "__pycache__" -type d -prune -exec rm -rf {} +
