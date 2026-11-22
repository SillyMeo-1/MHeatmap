# Build the release artifacts: dist\MHeatmap.exe and dist\MHeatmap.zip
#   powershell -ExecutionPolicy Bypass -File tools\build_release.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "==> PyInstaller"
py -3 -m PyInstaller --noconfirm MHeatmap.spec

$dist = Join-Path $root "dist"
$exe = Join-Path $dist "MHeatmap.exe"
if (-not (Test-Path $exe)) { throw "missing $exe" }

Write-Host "==> packaging zip"
$zip = Join-Path $dist "MHeatmap.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
$stage = Join-Path $env:TEMP ("mheatmap-zip-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item $exe $stage
Copy-Item (Join-Path $root "packaging\README.txt") (Join-Path $stage "README.txt")
# keep the readme readable in old Notepad
$readme = Join-Path $stage "README.txt"
$content = Get-Content $readme -Raw -Encoding UTF8
[System.IO.File]::WriteAllText($readme, $content, (New-Object System.Text.UTF8Encoding $true))
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -CompressionLevel Optimal
Remove-Item -Recurse -Force $stage

Get-ChildItem $dist | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "done: $exe"
