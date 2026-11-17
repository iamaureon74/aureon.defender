# one command: build + install aureon.defender on this windows pc, then build + install the android app on a
# usb-connected phone. run from the repository folder in an ordinary powershell window:
#
#   powershell -ExecutionPolicy Bypass -File scripts\windows\build-and-install-all.ps1
#
# what it does, in order (it stops and says why if a step fails):
#   1. checks for python 3.12 and a java 17+ jdk; offers to install them with winget if missing
#   2. builds the windows app (windows\build.ps1: tests first, then pyinstaller) and installs it
#      -> windows shows one administrator prompt; that click is yours
#   3. gets google's official android sdk pieces (platform 36, build-tools 36.0.0, platform-tools) if missing
#   4. builds and signs the apk (android\defender\build.ps1) and installs it on the phone with adb
#      -> the phone needs usb debugging on and must trust this pc
# nothing is uploaded anywhere. -SkipWindows / -SkipAndroid run just one half.
param([switch]$SkipWindows, [switch]$SkipAndroid)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path (Join-Path $PSScriptRoot '..\..')
function Say($m) { Write-Host "`n== $m" -ForegroundColor Green }
function Need($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function WingetInstall($id, $what) {
  if (-not (Need 'winget')) { throw "$what is missing and winget isn't available. install $what, then run this again." }
  $a = Read-Host "$what is missing. install it now with winget ($id)? [y/N]"
  if ($a -notmatch '^[yY]') { throw "$what is needed; stopping." }
  winget install -e --id $id --accept-source-agreements --accept-package-agreements
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}

Push-Location $repo
try {
  if (-not $SkipWindows) {
    Say 'windows: checking python 3.12'
    $py = $null
    foreach ($c in @('py -3.12', 'python')) {
      try { $v = Invoke-Expression "$c -c `"import sys;print(sys.version_info[:2]>=(3,12))`"" 2>$null; if ($v -eq 'True') { $py = $c; break } } catch {}
    }
    if (-not $py) { WingetInstall 'Python.Python.3.12' 'python 3.12'; $py = 'py -3.12' }
    $venv = Join-Path $repo 'windows\.venv'
    if (-not (Test-Path "$venv\Scripts\python.exe")) { Invoke-Expression "$py -m venv `"$venv`"" }

    Say 'windows: building (runs the tests first)'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $repo 'windows\build.ps1') -Venv $venv
    if ($LASTEXITCODE) { throw 'windows build failed (see the output above)' }
    $exe = Join-Path $repo 'windows\dist\aureon.defender\aureon.defender.exe'
    if (-not (Test-Path $exe)) { throw "build finished but $exe is missing" }

    Say 'windows: installing — approve the administrator prompt'
    & $exe install
    if ($LASTEXITCODE) { throw 'windows install did not finish (was the administrator prompt declined?)' }
  }

  if (-not $SkipAndroid) {
    Say 'android: checking java 17+'
    $javaOk = $false
    if (Need 'java') { $jv = (& java -version 2>&1 | Out-String); if ($jv -match 'version "(\d+)') { $javaOk = [int]$Matches[1] -ge 17 } }
    if (-not $javaOk) { WingetInstall 'Microsoft.OpenJDK.17' 'a java 17 jdk' }
    if (-not $env:JAVA_HOME -or -not (Test-Path "$env:JAVA_HOME\bin\javac.exe")) {
      $javac = (Get-Command javac -ErrorAction SilentlyContinue).Source
      if (-not $javac) { $javac = Get-ChildItem "$env:ProgramFiles\Microsoft\jdk-17*\bin\javac.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName }
      if (-not $javac) { throw 'could not find javac; set JAVA_HOME to your jdk folder and run again' }
      $env:JAVA_HOME = Split-Path (Split-Path $javac)
    }

    Say 'android: checking the sdk (google official downloads only)'
    if (-not $env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    $sdk = $env:ANDROID_HOME
    $sdkmanager = Join-Path $sdk 'cmdline-tools\latest\bin\sdkmanager.bat'
    if (-not (Test-Path $sdkmanager)) {
      New-Item -ItemType Directory -Force $sdk | Out-Null
      $zip = Join-Path $env:TEMP 'android-cmdline-tools.zip'
      Invoke-WebRequest 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip' -OutFile $zip
      $tmp = Join-Path $env:TEMP 'android-cmdline-tools'
      Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
      Expand-Archive $zip $tmp
      New-Item -ItemType Directory -Force (Join-Path $sdk 'cmdline-tools') | Out-Null
      Move-Item (Join-Path $tmp 'cmdline-tools') (Join-Path $sdk 'cmdline-tools\latest')
    }
    $need = @('platforms;android-36', 'build-tools;36.0.0', 'platform-tools')
    if (-not (Test-Path (Join-Path $sdk 'platforms\android-36\android.jar')) -or -not (Test-Path (Join-Path $sdk 'build-tools\36.0.0')) -or -not (Test-Path (Join-Path $sdk 'platform-tools\adb.exe'))) {
      Write-Host 'you will be asked to accept google''s android sdk licenses.'
      & $sdkmanager --sdk_root=$sdk --licenses
      & $sdkmanager --sdk_root=$sdk @need
      if ($LASTEXITCODE) { throw 'sdkmanager could not install the android build pieces' }
    }

    Say 'android: building and signing the apk'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $repo 'android\defender\build.ps1') -AndroidHome $sdk -JavaHome $env:JAVA_HOME
    if ($LASTEXITCODE) { throw 'android build failed (see the output above)' }
    $apk = Join-Path $repo 'android\defender\build\aureon-defender.apk'

    Say 'android: installing on the phone'
    $adb = Join-Path $sdk 'platform-tools\adb.exe'
    $devices = (& $adb devices) | Select-Object -Skip 1 | Where-Object { $_ -match '\tdevice$' }
    if (-not $devices) {
      Write-Host "no phone found. plug it in, turn on usb debugging, tap 'allow' on the phone, then run:`n  `"$adb`" install -r `"$apk`""
    } else {
      $out = (& $adb install -r $apk 2>&1 | Out-String)
      Write-Host $out
      if ($out -match 'INSTALL_FAILED_UPDATE_INCOMPATIBLE') {
        Write-Host 'the phone has a copy signed with a different key. to replace it (its local history is lost), run:'
        Write-Host "  `"$adb`" uninstall org.aureon.defender"
        Write-Host "  `"$adb`" install `"$apk`""
      }
    }
    Write-Host "apk kept at: $apk"
  }
  Say 'done'
} finally { Pop-Location }
