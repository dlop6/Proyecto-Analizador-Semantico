<#
  baja mars 4.5 (simulador mips) y verifica su hash
  se corre desde la raiz del repo: .\tools\fetch_mars.ps1
#>
$ErrorActionPreference = 'Stop'

$JarPath = Join-Path $PSScriptRoot 'Mars4_5.jar'
$JarUrl  = 'https://github.com/dpetersanderson/MARS/releases/download/v.4.5.1/Mars4_5.jar'
# mismo hash pinneado que en el script de bash
$ExpectedSha256 = 'AC340B676BA2B62246B9DF77E62F81AD4447BCFD329AB539716BCD09950B7096'

if (-not (Test-Path $JarPath)) {
    Write-Host "descargando mars 4.5..."
    Invoke-WebRequest -Uri $JarUrl -OutFile $JarPath -UseBasicParsing
}

$actualHash = (Get-FileHash -Path $JarPath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualHash -ne $ExpectedSha256) {
    Remove-Item $JarPath -Force
    Write-Error "sha256 del jar no coincide (esperado $ExpectedSha256, obtuvo $actualHash). se aborta."
    exit 1
}
Write-Host "mars verificado ok: $actualHash"
