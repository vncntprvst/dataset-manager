#!/bin/bash
# Simple launcher for Dataset Manager Streamlit app.
# Usage: run_app.sh [project_root]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-$(pwd)}"
# Resolve to absolute path
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
export DM_PROJECT_ROOT="$TARGET_DIR"
exec streamlit run "$SCRIPT_DIR/app.py"
