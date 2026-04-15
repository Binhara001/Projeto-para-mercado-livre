@echo off
echo.
echo  ================================
echo    ML Dashboard - Iniciando...
echo  ================================
echo.

cd /d "%~dp0backend"

:: Verifica se Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale em https://python.org
    pause
    exit /b
)

:: Instala dependências se necessário
if not exist ".deps_ok" (
    echo Instalando dependencias...
    pip install -r requirements.txt
    echo. > .deps_ok
)

:: Abre o navegador após 2 segundos
start "" timeout /t 2 /nobreak >nul && start http://localhost:5000

:: Inicia o servidor
echo Servidor rodando em http://localhost:5000
echo Pressione Ctrl+C para encerrar.
echo.
python app.py
pause
