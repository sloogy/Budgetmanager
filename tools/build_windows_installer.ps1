# BudgetManager Windows Installer Build
# Nutzung auf Windows PowerShell im Projekt-Root:
#   pwsh -ExecutionPolicy Bypass -File tools/build_windows_installer.ps1

$ErrorActionPreference = "Stop"

Write-Host "== BudgetManager Installer Build =="
python tools\sync_version.py --check
python -m compileall -q . -x '_attic|__pycache__'
python -m pytest tests/ -q
pyinstaller BudgetManager.spec --noconfirm

if (-not (Test-Path "dist\BudgetManager.exe")) {
  throw "dist\BudgetManager.exe fehlt nach PyInstaller-Build."
}

$candidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 7\ISCC.exe"
)
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  throw "ISCC.exe nicht gefunden. Installiere Inno Setup: winget install --id JRSoftware.InnoSetup.7 -e"
}

& $iscc "installer\budgetmanager_setup.iss"
$setup = Get-ChildItem -Path . -Filter "BudgetManager_Setup_*.exe" -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) {
  throw "Installer wurde nicht gefunden."
}

Write-Host "Fertig: $($setup.FullName)"
Get-FileHash $setup.FullName -Algorithm SHA256
