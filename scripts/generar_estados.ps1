# Genera los estados de cuenta de los cortes ya cumplidos y deja constancia en logs\generar_estados.log.
# Lo ejecuta a diario la tarea programada (ver scripts\programar_tarea.ps1); también se puede correr a mano:
#     .\scripts\generar_estados.ps1

$raiz = Split-Path -Parent $PSScriptRoot
$logs = Join-Path $raiz "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "generar_estados.log"
Set-Location $raiz
"=== $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss') ===" | Out-File $log -Append -Encoding utf8
& (Join-Path $raiz ".venv\Scripts\python.exe") manage.py generar_estados 2>&1 | ForEach-Object { "$_" } | Out-File $log -Append -Encoding utf8
"Código de salida: $LASTEXITCODE" | Out-File $log -Append -Encoding utf8
