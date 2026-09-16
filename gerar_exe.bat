@echo off
REM ============================================================
REM  Baixador de DANFE - gerador do executavel unico (.exe)
REM
REM  Gera dist\BaixadorDANFE.exe
REM  - Se o Python ja estiver instalado, usa ele.
REM  - Se NAO tiver Python, o script INSTALA automaticamente
REM    (valor preferido ao winget; fallback ao instalador oficial
REM    do python.org, sem precisar de administrador).
REM
REM  Basta dar duplo clique. Nao precisa abrir nenhum editor/IDE.
REM ============================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   Baixador de DANFE - gerador do executavel (.exe)
echo ============================================================
echo.

REM ---------- 1) Detectar Python ---------------------------------
set "PY="
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    echo [1/4] Python nao encontrado. Instalando automaticamente...
    echo.
    call :instalar_python
    if errorlevel 1 (
        echo Nao foi possivel instalar o Python automaticamente.
        echo Instale manualmente em https://www.python.org/downloads/
        echo (marque "Add Python to PATH") e rode este arquivo de novo.
        pause
        exit /b 1
    )

    REM apos instalar, re-detectar (sessao atual nao atualiza o PATH)
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%ProgramFiles%\Python313\python.exe"
    ) do if exist "%%~P" set "PY=%%~P"
    if not defined PY (
        echo Python instalado, mas nao localizamos o executavel nesta sessao.
        echo Feche e abra esta janela e rode o gerar_exe.bat de novo.
        pause
        exit /b 1
    )
)
echo Python encontrado: !PY!
echo.

REM ---------- 2) Criar ambiente virtual ---------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Criando ambiente virtual...
    !PY! -m venv .venv
    if errorlevel 1 ( echo Falha ao criar venv. & pause & exit /b 1 )
)

REM ---------- 3) Instalar dependencias + PyInstaller --------------
echo [3/4] Instalando dependencias e PyInstaller (primeira vez demora)...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 ( echo Falha ao instalar dependencias. & pause & exit /b 1 )

REM ---------- 4) Compilar o executavel ----------------------------
echo [4/4] Compilando BaixadorDANFE.exe (2 a 5 minutos)...
".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm --clean --onefile --windowed ^
    --name BaixadorDANFE ^
    --collect-all customtkinter ^
    main.py
if errorlevel 1 ( echo Falha ao compilar o executavel. & pause & exit /b 1 )

echo.
echo ============================================================
echo  Pronto! Executavel gerado:
echo  %~dp0dist\BaixadorDANFE.exe
echo ============================================================
echo.
echo  Envie esse arquivo pelo WhatsApp e rode na maquina da
echo  empresa com duplo clique - nao precisa de Python la.
echo.
pause
exit /b 0

REM ============================================================
REM :instalar_python
REM   tenta winget; se nao houver, baixa o instalador oficial
REM   e instala silenciosamente em modo per-usuario (sem admin)
REM ============================================================
:instalar_python
where winget >nul 2>nul
if not errorlevel 1 (
    echo Tentando com winget (Windows 10/11)...
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo winget falhou - tentando instalador oficial.
        goto tentar_pythonorg
    )
    exit /b 0
)

:tentar_pythonorg
set "PYURL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
set "PYINST=%TEMP%\python-3.12.7-amd64.exe"
echo Baixando instalador oficial do Python (python.org)...
curl -sSL -o "%PYINST%" "%PYURL%"
if errorlevel 1 (
    echo Falha ao baixar o instalador. Verifique a internet.
    exit /b 1
)
echo Instalando Python em modo silencioso (per-usuario, sem admin)...
start /wait "" "%PYINST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Include_doc=0
del "%PYINST%" >nul 2>nul
exit /b 0