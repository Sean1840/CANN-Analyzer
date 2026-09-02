@echo off
setlocal
set PYTHONPATH=%~dp0..\tools;%PYTHONPATH%
python -m cann_analyze %*
