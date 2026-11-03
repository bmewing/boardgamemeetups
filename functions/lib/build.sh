#!/bin/bash
set -e
# Vendors the backend's `app` package into lib/ for packages/core/app/.include to pick up.
#
# This runs twice. First on the full repo checkout, where backend/ exists and we copy it.
# Then again inside the remote build container for the function, which only receives the
# functions/ folder: there backend/ is absent and the copy from the first pass is used.
# Plain shell only; the first pass has no Python.
if [ -d ../../backend/app ]; then
  rm -rf app
  cp -r ../../backend/app ./app
  find ./app -name "__pycache__" -type d -prune -exec rm -rf {} +
elif [ -d app ]; then
  echo "backend/ not present here; using the app package vendored earlier"
else
  echo "error: neither ../../backend/app nor a vendored lib/app exists" >&2
  exit 1
fi
