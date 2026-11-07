$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install --target .deps -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Run: python app.py'
