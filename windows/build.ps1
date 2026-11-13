# Build aureon.defender (program folder + zip). One-folder layout, not --onefile: unsigned self-extracting
# single-file exes are routinely mis-flagged by antivirus machine-learning models (e.g. Trojan:Win32/Bearfoos!ml).
#   powershell -ExecutionPolicy Bypass -File windows\build.ps1 [-Venv path]
param([string]$Venv = "$PSScriptRoot\.venv")
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent

if (-not (Test-Path "$Venv\Scripts\python.exe")) { python -m venv $Venv }
$py = "$Venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -r "$PSScriptRoot\requirements.txt" pyinstaller==6.11.1

# tests first: a broken build never ships
Push-Location $PSScriptRoot
& $py -m unittest discover -s tests
if ($LASTEXITCODE) { Pop-Location; throw "tests failed" }

& $py -m PyInstaller --noconfirm --clean --onedir --noconsole --name aureon.defender `
    --icon "$PSScriptRoot\assets\aureon.ico" `
    --paths $PSScriptRoot --paths $repo `
    --add-data "$PSScriptRoot\aureon_defender\ui;aureon_defender\ui" `
    --add-data "$PSScriptRoot\aureon_defender\rules;aureon_defender\rules" `
    --add-data "$PSScriptRoot\aureon_defender\noah_shield;aureon_defender\noah_shield" `
    --hidden-import win32com.client --hidden-import pythoncom --hidden-import pywintypes `
    --hidden-import aureon.audit --hidden-import aureon.rfwatch --hidden-import aureon.hidguard --hidden-import aureon.analyst `
    --hidden-import aureon.keyagent `
    --distpath "$PSScriptRoot\dist" --workpath "$env:TEMP\aureon-build" --specpath "$env:TEMP\aureon-build" `
    "$PSScriptRoot\launcher.py"
Pop-Location
$ver = (& $py -c "import sys; sys.path.insert(0, r'$PSScriptRoot'); from aureon_defender.core import VERSION; print(VERSION)").Trim()
New-Item -ItemType Directory -Force "$PSScriptRoot\release" | Out-Null
$zip = "$PSScriptRoot\release\aureon.defender-$ver-win64.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path "$PSScriptRoot\dist\aureon.defender" -DestinationPath $zip
Get-FileHash $zip -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $zip -Leaf)" } | Set-Content "$zip.sha256" -Encoding ascii
Get-Content "$zip.sha256"
