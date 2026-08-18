$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Write-Host "No existe .env. Ejecuta primero .\preparar_local.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando Distric C en http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Daphne/Channels atendera HTTP y WebSockets." -ForegroundColor DarkGray
py manage.py runserver 127.0.0.1:8000
