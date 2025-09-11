#!/bin/bash
# Simple launcher for Dataset Manager Streamlit app.
# Usage: run_app.sh [project_root]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-$(pwd)}"
# Resolve to absolute path
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
export DM_PROJECT_ROOT="$TARGET_DIR"

# Change to script directory for uv to work properly
cd "$SCRIPT_DIR"

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv to run the app..."
    echo "Working directory: $SCRIPT_DIR"
    echo "Project root: $TARGET_DIR"
    exec uv run streamlit run app.py
else
    echo "uv not found. Trying with pip/conda environment..."
    echo "Make sure you have streamlit installed in your current environment."
    echo "You can install it with: pip install streamlit"
    echo ""
    exec streamlit run app.py
fi
