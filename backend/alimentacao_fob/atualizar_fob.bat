@echo off
setlocal
rem Sem credenciais. --faturamento-ok atualiza so Pendencias; --sincronizar importa mestres.
set "FOB_ACTION="
if /I "%~1"=="--faturamento-ok" set "FOB_ACTION=--atualizar-recentes"
if /I "%~1"=="--sincronizar" set "FOB_ACTION=--sincronizar"
if /I "%~1"=="--validar" set "FOB_ACTION="
if /I not "%~1"=="--validar" if not defined FOB_ACTION goto :usage
if not "%~2"=="" goto :usage
if not defined FOB_PYTHON set "FOB_PYTHON=%~dp0..\.venv-fob\Scripts\python.exe"
if not exist "%FOB_PYTHON%" (
  echo FOB: Python nao encontrado. Prepare backend\.venv-fob ou defina FOB_PYTHON com caminho absoluto.
  exit /b 69
)
"%FOB_PYTHON%" -c "import openpyxl, psycopg" >nul 2>nul
if errorlevel 1 (
  echo FOB: faltam dependencias. Instale backend\requirements-alimentacao-fob.txt nesse Python.
  exit /b 69
)
pushd "%~dp0.."
if errorlevel 1 exit /b 1
"%FOB_PYTHON%" -B -m alimentacao_fob %FOB_ACTION%
set "FOB_RESULT=%ERRORLEVEL%"
popd
exit /b %FOB_RESULT%

:usage
echo Uso: atualizar_fob.bat --faturamento-ok ^| --sincronizar ^| --validar
exit /b 64
