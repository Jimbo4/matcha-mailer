@echo off
setlocal
cd /d "%~dp0"
title Matcha Mailer

if not exist ".venv\Scripts\pythonw.exe" (
  echo Prima installazione del Matcha Mailer: serve un minuto.
  py -3 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Non trovo Python. Installalo da https://www.python.org/downloads/ e riapri questo file.
    pause
    exit /b 1
  )
)

fc /b requirements.txt ".venv\requirements.installed" >nul 2>&1
if errorlevel 1 (
  echo Installo o aggiorno le librerie...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Installazione non riuscita: controlla la connessione e riprova.
    pause
    exit /b 1
  )
  copy /y requirements.txt ".venv\requirements.installed" >nul
)

start "" ".venv\Scripts\pythonw.exe" -m matcha_mailer
exit /b 0
