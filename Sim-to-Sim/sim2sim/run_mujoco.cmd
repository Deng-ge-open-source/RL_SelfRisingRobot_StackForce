@echo off
setlocal
title StackForce MuJoCo Setup and Run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_mujoco.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo StackForce setup did not complete. Review the error above and try again.
  pause
)
exit /b %EXIT_CODE%
