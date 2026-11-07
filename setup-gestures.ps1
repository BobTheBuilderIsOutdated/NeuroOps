$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install --target .camera-deps 'mediapipe==1.2.2'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
New-Item -ItemType Directory -Force models | Out-Null
if (-not (Test-Path 'models/face_landmarker.task')) {
    Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task' -OutFile 'models/face_landmarker.task'
}
Write-Host 'Ready: double-click start-gestures.cmd'
