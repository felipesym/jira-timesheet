@echo off
setlocal EnableExtensions
title Jira Sync
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "BASE_DIR=%~dp0"

cd /d "%BASE_DIR%"
if errorlevel 1 (
    echo Nao foi possivel acessar a pasta do Jira Sync:
    echo %BASE_DIR%
    set "RESULT=2"
    goto :failure
)

if not exist "%BASE_DIR%jira_sync_menu.py" (
    echo O arquivo jira_sync_menu.py nao foi encontrado em:
    echo %BASE_DIR%
    set "RESULT=2"
    goto :failure
)

if exist "%BASE_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%BASE_DIR%.venv\Scripts\python.exe"
    set "PYTHON_ARG="
    goto :python_found
)

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    set "PYTHON_ARG=-3"
    goto :python_found
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "PYTHON_ARG="
    goto :python_found
)

echo Python 3 nao foi encontrado.
echo Instale o Python 3.10 ou superior e execute este arquivo novamente.
set "RESULT=9009"
goto :failure

:python_found
"%PYTHON_CMD%" %PYTHON_ARG% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :python_version_error

echo Iniciando o Jira Sync...
echo.
"%PYTHON_CMD%" %PYTHON_ARG% "%BASE_DIR%jira_sync_menu.py" --windows
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" goto :success
goto :failure

:python_version_error
echo A versao encontrada do Python nao e compativel.
echo Instale o Python 3.10 ou superior e execute este arquivo novamente.
set "RESULT=3"
goto :failure

:failure
echo.
echo O Jira Sync terminou com erro ^(codigo %RESULT%^).
echo Leia as mensagens acima para identificar a causa.
echo.
echo Pressione qualquer tecla para fechar esta janela...
pause >nul
endlocal & exit /b %RESULT%

:success
endlocal & exit /b 0
