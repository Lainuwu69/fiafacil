# Genera el zip del código fuente de FíaFácil para compartirlo con el grupo o entregarlo.
#
# Uso (desde la carpeta del proyecto):
#     .\scripts\empaquetar.ps1
# Resultado: entrega\FiaFacil_codigo_fuente.zip
#
# NO incluye (por seguridad o porque se regenera en cada computadora):
#   .env               contraseña de la base y clave secreta: cada uno crea el suyo desde .env.example
#   .venv              entorno de Python: se crea con "py -3.13 -m venv .venv" e instalando requirements.txt
#   respaldos, logs    copias de la base (datos personales) y registros de ejecución
#   media              imágenes subidas: cargar_demo las vuelve a generar
#   __pycache__, staticfiles, media_pruebas, entrega

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$salida = Join-Path $raiz "entrega"
$zip = Join-Path $salida "FiaFacil_codigo_fuente.zip"
$temporal = Join-Path $env:TEMP ("fiafacil_empaque_" + [guid]::NewGuid().ToString("N"))
$carpeta = Join-Path $temporal "FiaFacil"

$excluirCarpetas = @(".venv", "venv", "respaldos", "logs", "media", "media_pruebas", "staticfiles", "__pycache__", "entrega", ".git")
$excluirArchivos = @(".env", "*.pyc", "*.log", "*.dump", "*.zip")

New-Item -ItemType Directory -Force $carpeta, $salida | Out-Null
try {
    Get-ChildItem $raiz -Recurse -File -Force | Where-Object {
        $relativa = $_.FullName.Substring($raiz.Length + 1)
        $nombre = $_.Name
        $carpetas = $relativa.Split('\') | Select-Object -SkipLast 1
        $enCarpetaExcluida = @($carpetas | Where-Object { $excluirCarpetas -contains $_ }).Count -gt 0
        $archivoExcluido = @($excluirArchivos | Where-Object { $nombre -like $_ }).Count -gt 0
        -not $enCarpetaExcluida -and -not $archivoExcluido
    } | ForEach-Object {
        $destino = Join-Path $carpeta $_.FullName.Substring($raiz.Length + 1)
        New-Item -ItemType Directory -Force (Split-Path -Parent $destino) | Out-Null
        Copy-Item $_.FullName $destino
    }
    if (Test-Path $zip) { Remove-Item $zip -Confirm:$false }
    Compress-Archive -Path $carpeta -DestinationPath $zip -CompressionLevel Optimal
    $n = (Get-ChildItem $carpeta -Recurse -File).Count
    $kb = [math]::Round((Get-Item $zip).Length / 1KB, 1)
    Write-Output "Zip creado: $zip ($n archivos, $kb KB)"
}
finally {
    Remove-Item $temporal -Recurse -Force -Confirm:$false -ErrorAction SilentlyContinue
}
