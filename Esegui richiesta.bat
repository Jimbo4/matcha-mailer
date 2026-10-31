@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Matcha Mailer - Esegui richiesta

if not exist ".venv\Scripts\python.exe" (
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

echo Se si apre il browser di Google, fai l'accesso con il tuo account personale.
echo.
".venv\Scripts\python.exe" -m matcha_mailer richiesta
echo.
echo Fatto. Puoi chiudere questa finestra e scrivere "fatto" a Claude.
pause
