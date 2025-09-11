@echo off

rem Simple launcher for Dataset Manager Streamlit app.

rem Usage: run_app.bat [project_root]



set SCRIPT_DIR=%~dp0

set TARGET_DIR=%CD%

if not "%~1"=="" set TARGET_DIR=%~1

set DM_PROJECT_ROOT=%TARGET_DIR%

streamlit run "%SCRIPT_DIR%app.py"

