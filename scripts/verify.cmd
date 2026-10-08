@echo off
rem Single offline verification entry point (no CI job; run before pushing).
rem Usage: scripts\verify.cmd   (from repo root)
setlocal
cd /d "%~dp0.."
set PYTHONPATH=%CD%\tools;%PYTHONPATH%
set PY=%PYTHON%
if "%PY%"=="" set PY=python

echo [1/3] unit tests
%PY% -m pytest tests -q || exit /b 1

echo [2/3] skill payload in sync
%PY% scripts\sync_skills_payload.py --check || exit /b 1

echo [3/3] locate/parse eval
%PY% eval\run_eval.py || exit /b 1

echo all checks passed
endlocal
