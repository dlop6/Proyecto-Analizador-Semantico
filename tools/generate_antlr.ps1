<#
  regenera lexer, parser y visitor de python a partir de program/Compiscript.g4
  se corre desde la raiz del repo: .\tools\generate_antlr.ps1
#>
$ErrorActionPreference = 'Stop'

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$JarPath   = Join-Path $PSScriptRoot 'antlr-4.13.1-complete.jar'
$JarUrl    = 'https://www.antlr.org/download/antlr-4.13.1-complete.jar'
# pinneado contra el jar oficial de antlr.org, verificado manualmente. si no coincide, no confiamos en el binario
$ExpectedSha256 = 'BC13A9C57A8DD7D5196888211E5EDE657CB64A3CE968608697E4F668251A8487'

function Get-Sha256Hex($path) {
    (Get-FileHash -Path $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

if (-not (Test-Path $JarPath)) {
    Write-Host "descargando antlr 4.13.1..."
    Invoke-WebRequest -Uri $JarUrl -OutFile $JarPath -UseBasicParsing
}

$actualHash = Get-Sha256Hex $JarPath
if ($actualHash -ne $ExpectedSha256) {
    Remove-Item $JarPath -Force
    Write-Error "sha256 del jar no coincide (esperado $ExpectedSha256, obtuvo $actualHash). se aborta, no se confia en el binario."
    exit 1
}
Write-Host "jar verificado ok: $actualHash"

$GrammarFile = Join-Path $RepoRoot 'program\Compiscript.g4'
$OutDir      = Join-Path $RepoRoot 'compiler\generated'

if (-not (Test-Path $GrammarFile)) {
    Write-Error "no se encontro la gramatica en $GrammarFile"
    exit 1
}

Write-Host "generando lexer/parser/visitor python..."
& java -Xmx500M -cp $JarPath org.antlr.v4.Tool `
    -Dlanguage=Python3 -visitor -no-listener `
    -o $OutDir `
    $GrammarFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "antlr fallo generando el parser (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

$required = @('CompiscriptLexer.py', 'CompiscriptParser.py', 'CompiscriptVisitor.py')
foreach ($f in $required) {
    $p = Join-Path $OutDir $f
    if (-not (Test-Path $p)) {
        Write-Error "no se genero el archivo esperado: $f"
        exit 1
    }
}

# antlr no genera __init__.py (no sabe que esto es un paquete python), asi que lo
# reponemos siempre -- si se borra compiler/generated entero (clon limpio, o alguien
# limpiando el directorio a mano) el import compiler.generated tiene que seguir andando.
$initContent = @'
# unico punto de acoplamiento con lo que genera antlr en todo el proyecto.
# si algun dia cambia la ubicacion o la version, se toca nada mas este archivo.
from .CompiscriptLexer import CompiscriptLexer
from .CompiscriptParser import CompiscriptParser
from .CompiscriptVisitor import CompiscriptVisitor

__all__ = ["CompiscriptLexer", "CompiscriptParser", "CompiscriptVisitor"]
'@
Set-Content -Path (Join-Path $OutDir '__init__.py') -Value $initContent -Encoding utf8

Write-Host "listo. lexer, parser y visitor generados en compiler/generated"
