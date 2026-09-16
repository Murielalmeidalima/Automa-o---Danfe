@echo off
REM ============================================================
REM  Baixador de DANFE - execucao a partir do codigo-fonte
REM  (duplo clique: cria o ambiente virtual e abre o programa)
REM ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

REM --- Localiza o Python instalado (python ou py launcher) -----
set "PY="
where python >nul 2>nul
if %errorlevel%==0 ( set "PY=python" ) else (
    where py >nul 2>nul
    if %errorlevel%==0 ( set "PY=py -3" ) else (
        echo Python nao encontrado.
        echo Instale o Python em https://www.python.org/downloads/
        echo ATENCAO: marque a opcao "Add Python to PATH" na instalacao.
        pause
        exit /b 1
    )
)

REM --- Cria o ambiente virtual na primeira execucao ------------
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente virtual ...
    %PY% -m venv .venv
    if errorlevel 1 ( echo Falha ao criar venv. & pause & exit /b 1 )
)

REM --- Instala dependencias (se necessario) ----------------------
echo Verificando dependencias ...
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 ( echo Falha ao instalar dependencias. & pause & exit /b 1 )

REM --- Executa a aplicacao ---------------------------------------
echo Iniciando o Baixador de DANFE ...
".venv\Scripts\python.exe" main.py

endlocal