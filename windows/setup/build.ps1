param([Parameter(Mandatory=$true)][string]$PayloadZip,[Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
$payloadPath=(Resolve-Path -LiteralPath $PayloadZip).Path
$compiler=Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if(!(Test-Path -LiteralPath $compiler)){throw 'The Windows .NET Framework C# compiler is required.'}
$stage=Join-Path $PSScriptRoot ('build/'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $stage | Out-Null
$digest=(Get-FileHash -LiteralPath $payloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
$source=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'Setup.cs')).Replace('__PAYLOAD_SHA256__',$digest)
$sourcePath=Join-Path $stage 'Setup.cs';[IO.File]::WriteAllText($sourcePath,$source,[Text.UTF8Encoding]::new($true))
$outputPath=[IO.Path]::GetFullPath($OutputFile)
New-Item -ItemType Directory -Force (Split-Path $outputPath) | Out-Null
$icon=Join-Path $PSScriptRoot '../assets/aureon.ico'
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/win32manifest:$PSScriptRoot/setup.manifest" "/win32icon:$icon" "/resource:${payloadPath},Payload" /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$outputPath" $sourcePath
if($LASTEXITCODE){throw 'Setup compilation failed.'}
Get-FileHash -LiteralPath $outputPath -Algorithm SHA256
