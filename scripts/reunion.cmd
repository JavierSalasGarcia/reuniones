@echo off
rem Identifica a quien acaba de entrar, o da de alta:  reunion.cmd nueva "Nombre" correo@uaemex.mx
setlocal
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m reuniones.cli %*
