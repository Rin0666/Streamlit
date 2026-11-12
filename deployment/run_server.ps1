$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run deployment\install_offline.ps1 first."
}

Set-Location $root
& $python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
