@echo off
REM Simple launcher for Dataset Manager Streamlit app.
REM Usage: run_app.bat [project_root]

setlocal ENABLEDELAYEDEXPANSION

REM Resolve script directory
set "SCRIPT_DIR=%~dp0"

REM Use first arg if provided; otherwise current working directory
set "TARGET_DIR=%CD%"
if not "%~1"=="" (
  set "TARGET_DIR=%~1"
)

REM Export as environment variable for the app
set "DM_PROJECT_ROOT=%TARGET_DIR%"

REM Change to script directory for uv to work properly
cd /d "%SCRIPT_DIR%"

REM Check if uv is available
where uv >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using uv to run the app...
    echo Working directory: %SCRIPT_DIR%
    echo Project root: %TARGET_DIR%
    uv run streamlit run app.py
) else (
    echo uv not found. Trying with pip/conda environment...
    echo Make sure you have streamlit installed in your current environment.
    echo You can install it with: pip install streamlit
    echo.
    streamlit run app.py
)

@REM @REM Keep the window open after the script completes
@REM pause

endlocal

