@echo off
setlocal
rem Chamar somente no ramo de sucesso do atualizador do faturamento.
rem Nao contem credenciais; usa alimentacao_fob\.env.local ou ambiente existente.
if /I not "%~1"=="--faturamento-ok" (
  echo FOB nao executado: falta confirmacao de sucesso do faturamento.
  exit /b 64
)
if not defined FOB_PYTHON set "FOB_PYTHON=python"
pushd "%~dp0.."
if errorlevel 1 exit /b 1
"%FOB_PYTHON%" -B -m alimentacao_fob --rotina-diaria
set "FOB_RESULT=%ERRORLEVEL%"
popd
exit /b %FOB_RESULT%
