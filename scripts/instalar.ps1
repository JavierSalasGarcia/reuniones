# Instalacion en Windows. Ejecutar desde la carpeta del proyecto:
#   powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -e .

if (-not (Test-Path config.toml)) { Copy-Item config.example.toml config.toml }
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

Write-Host ""
Write-Host "Listo." -ForegroundColor Green
Write-Host "1. Edita config.toml (carpeta de datos y correo) y .env (contrasena SMTP)."
Write-Host "2. Arranca el sitio con scripts\servidor.cmd"
Write-Host "3. Identifica con scripts\reunion.cmd"
