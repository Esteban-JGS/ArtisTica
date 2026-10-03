# Abre el Word generado, calcula el indice con sus numeros de pagina y lo guarda.
# Requiere Microsoft Word instalado. Con -Pdf exporta ademas una copia para revisar.
# Uso: powershell -File actualizar-indice.ps1 ..\entregas\ArtisTica_II_Avance.docx [-Pdf]
param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [switch]$Pdf
)

$ruta = (Resolve-Path $Docx).Path

# Se anota que procesos de Word ya existian, para cerrar solo el que abre este script
$previos = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object Id)
$word = New-Object -ComObject Word.Application
$propio = Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $previos -notcontains $_.Id }
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($ruta)
    foreach ($indice in $doc.TablesOfContents) { $indice.Update() }
    $doc.Fields.Update() | Out-Null
    $doc.Save()
    $doc.Repaginate()
    Write-Output "Paginas: $($doc.ComputeStatistics(2))"
    if ($Pdf) {
        $salidaPdf = [System.IO.Path]::ChangeExtension($ruta, ".pdf")
        $doc.ExportAsFixedFormat($salidaPdf, 17)
        Write-Output "PDF: $salidaPdf"
    }
}
finally {
    # Despues de exportar, Word suele perder la conexion COM y quedar oculto en memoria
    try { $doc.Close(0) } catch {}
    try { $word.Quit() } catch {}
    Start-Sleep -Seconds 1
    $propio | Where-Object { -not $_.HasExited } | Stop-Process -Force -ErrorAction SilentlyContinue
}
