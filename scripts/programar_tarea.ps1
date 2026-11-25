# Programa en Windows la generación diaria de estados de cuenta (requisito 6: "en la fecha de corte
# se genera el listado de pago"). Crea la tarea "FiaFacil - generar estados" para el usuario actual:
#   - todos los días a las 21:00 (después de la hora de corte habitual, 20:00);
#   - si la laptop estaba apagada a esa hora, se ejecuta apenas se encienda (StartWhenAvailable).
# No necesita permisos de administrador. Uso:
#     .\scripts\programar_tarea.ps1            crea o actualiza la tarea
#     .\scripts\programar_tarea.ps1 -Quitar    elimina la tarea

param([switch]$Quitar)

$nombre = "FiaFacil - generar estados"
if ($Quitar) {
    Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    Write-Output "Tarea '$nombre' eliminada."
    return
}
$script = Join-Path $PSScriptRoot "generar_estados.ps1"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$disparador = New-ScheduledTaskTrigger -Daily -At "21:00"
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $nombre -Action $accion -Trigger $disparador -Settings $ajustes `
    -Description "Genera los estados de cuenta de FíaFácil de los cortes ya cumplidos (manage.py generar_estados)." -Force | Out-Null
$t = Get-ScheduledTask -TaskName $nombre
Write-Output "Tarea '$nombre' programada: $($t.State); próxima ejecución $((Get-ScheduledTaskInfo -TaskName $nombre).NextRunTime)."
