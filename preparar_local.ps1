$ErrorActionPreference = "Stop"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Distric C - Preparacion de localhost" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Copy-Item ".env.local.example" ".env"
    Write-Host "Se creo .env desde .env.local.example." -ForegroundColor Yellow
    Write-Host "Edita .env con PostgreSQL, Google Maps y Cloudinary y vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 0
}

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py cargar_red_vial
py manage.py cargar_rendimientos
py manage.py crear_admin_inicial

Write-Host "" 
Write-Host "Localhost preparado correctamente." -ForegroundColor Green
Write-Host "Ejecuta: .\iniciar_local.ps1" -ForegroundColor Green
