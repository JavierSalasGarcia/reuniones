@echo off
rem Levanta el sitio local y la vigilancia de la carpeta de transcripciones.
setlocal
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m reuniones.cli servidor
