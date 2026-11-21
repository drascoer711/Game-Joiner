#!/bin/sh
set -u

build_log="/tmp/game-joiner-render-build.log"

if python -m pip install -r requirements.txt >"$build_log" 2>&1; then
    cat "$build_log"
else
    status=$?
    cat "$build_log"
    details=$(tail -c 1200 "$build_log" 2>/dev/null || true)
    python render_notify.py "Render build failed (pip install, exit $status). Last build output:\n$details" || true
    exit "$status"
fi

if python -c "import aiohttp, discord, flask, socketio"; then
    echo "Python dependency import check passed."
else
    status=$?
    python render_notify.py "Render build failed: Python dependency import check exited with status $status. Check the build logs for the missing package or import error." || true
    exit "$status"
fi
