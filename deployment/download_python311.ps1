$ErrorActionPreference = "Stop"
$directory = Join-Path $PSScriptRoot "python311"
$installer = Join-Path $directory "python-3.11.9-amd64.exe"
$expectedHash = "5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde"
$url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"

if (-not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Path $directory | Out-Null
}
if (-not (Test-Path -LiteralPath $installer)) {
    $partial = "$installer.partial"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $partial -UseBasicParsing
    if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $expectedHash) {
        throw "Downloaded installer failed SHA256 verification: $partial"
    }
    Move-Item -LiteralPath $partial -Destination $installer
}
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expectedHash) {
    throw "Bundled installer failed SHA256 verification: $installer"
}
Write-Host "Verified offline installer: $installer"
Write-Host "This downloads the runtime only; it does not install Python on this computer."
