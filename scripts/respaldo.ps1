# Respaldo de la base de datos de FíaFácil con pg_dump (formato personalizado, comprimido).
#
# Uso (desde la carpeta del proyecto, en PowerShell):
#     .\scripts\respaldo.ps1
# Restaurar un respaldo en una base vacía:
#     & "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -h localhost -U postgres -d fiafacil --clean --if-exists respaldos\ARCHIVO.dump
#
# Lee DB_NAME, DB_USER, DB_PASSWORD, DB_HOST y DB_PORT del archivo .env. La contraseña se
# pasa a pg_dump por la variable PGPASSWORD solo durante la ejecución y luego se borra.
# Plan sugerido: ejecutarlo antes de cada exposición o demo y una vez al día en uso real
# (Programador de tareas de Windows), conservando los últimos 7 respaldos.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$cfg = @{}
foreach ($linea in Get-Content (Join-Path $raiz ".env")) {
    if ($linea -match '^\s*([A-Z_]+)=(.*)$') { $cfg[$Matches[1]] = $Matches[2].Trim() }
}
$pgDump = "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
if (-not (Test-Path $pgDump)) { $pgDump = "pg_dump" }

$carpeta = Join-Path $raiz "respaldos"
New-Item -ItemType Directory -Force $carpeta | Out-Null
$archivo = Join-Path $carpeta ("{0}_{1}.dump" -f $cfg["DB_NAME"], (Get-Date -Format "yyyyMMdd_HHmm"))

$env:PGPASSWORD = $cfg["DB_PASSWORD"]
try {
    & $pgDump -h $cfg["DB_HOST"] -p $cfg["DB_PORT"] -U $cfg["DB_USER"] -F c -f $archivo $cfg["DB_NAME"]
    if ($LASTEXITCODE -ne 0) { throw "pg_dump terminó con error $LASTEXITCODE" }
    $kb = [math]::Round((Get-Item $archivo).Length / 1KB, 1)
    Write-Output "Respaldo creado: $archivo ($kb KB)"
    # Conserva solo los 7 respaldos más recientes.
    Get-ChildItem $carpeta -Filter "*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 7 | Remove-Item -Confirm:$false
}
finally {
    $env:PGPASSWORD = $null
}
