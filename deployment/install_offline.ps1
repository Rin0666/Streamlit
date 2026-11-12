$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venv = Join-Path $root ".venv"
$wheelhouse = Join-Path $root "wheelhouse_py311"
$requirements = Join-Path $root "requirements.txt"
$python = $null

if (-not (Test-Path $wheelhouse)) {
    throw "Missing wheelhouse folder: $wheelhouse"
}

try {
    $py311 = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $py311) {
        $python = $py311.Trim()
    }
}
catch {
    $python = $null
}

if (-not $python) {
    $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($LASTEXITCODE -eq 0 -and $version.Trim() -eq "3.11") {
        $python = "python"
    }
}

if (-not $python) {
    throw "Python 3.11 was not found. Install Python 3.11 on the server first."
}

& $python -m venv $venv
& (Join-Path $venv "Scripts\python.exe") -m pip install --no-index --find-links $wheelhouse --requirement $requirements

Write-Host "Offline install complete."
Write-Host "Run with:"
Write-Host ".\.venv\Scripts\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501"
