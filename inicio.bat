@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PG_CTL=C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"
set "PG_DATA=C:\Program Files\PostgreSQL\18\data"

cd /d "%SCRIPT_DIR%"

:: Configurando binario local do Node.js
if exist "D:\nodejs\node-v24.18.0-win-x64" (
    set "PATH=D:\nodejs\node-v24.18.0-win-x64;%PATH%"
)

echo.
echo ============================================================
echo  MIDWAY 7.0.0 - Inicio do painel React + FastAPI
echo ============================================================
echo.

if not exist "%SCRIPT_DIR%run.bat" (
    echo ERRO: run.bat nao encontrado em "%SCRIPT_DIR%".
    goto erro
)

if not exist "%SCRIPT_DIR%frontend\package.json" (
    echo ERRO: frontend\package.json nao encontrado.
    goto erro
)

if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo ERRO: dependencias do frontend nao encontradas.
    echo Execute antes: cd frontend ^&^& npm install
    echo Pasta esperada: "%SCRIPT_DIR%frontend\node_modules"
    goto erro
)

echo [1/3] Verificando PostgreSQL local...
if exist "%PG_CTL%" (
    "%PG_CTL%" status -D "%PG_DATA%" >nul 2>&1
    if errorlevel 1 (
        call "%SCRIPT_DIR%run.bat" postgres_start
        if errorlevel 1 goto erro
    ) else (
        echo PostgreSQL ja esta em execucao.
    )
) else (
    echo AVISO: pg_ctl nao encontrado em "%PG_CTL%".
    echo A API ainda pode subir se o banco estiver em outro host configurado no .env.
)

echo.
echo [2/3] Abrindo API FastAPI em nova janela...
start "MIDWAY API FastAPI" /D "%SCRIPT_DIR%" cmd /k "call run.bat api"

echo Aguardando inicializacao da API...
timeout /t 4 /nobreak >nul

echo.
echo [3/3] Abrindo frontend React em nova janela...
start "MIDWAY Frontend React" /D "%SCRIPT_DIR%" cmd /k "call run.bat frontend"

echo.
echo ============================================================
echo  Painel React: http://127.0.0.1:5173
echo  API FastAPI : http://127.0.0.1:8000
echo  Docs API    : http://127.0.0.1:8000/docs
echo ============================================================
echo.
echo Se a pagina nao abrir automaticamente, acesse:
echo http://127.0.0.1:5173
echo.

start "" "http://127.0.0.1:5173"
goto fim

:erro
echo.
echo Falha ao iniciar o MIDWAY. Verifique as mensagens acima.
pause
exit /b 1

:fim
endlocal
