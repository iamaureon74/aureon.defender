param(
  [string]$AndroidHome=$env:ANDROID_HOME,
  [string]$JavaHome=$env:JAVA_HOME,
  [string]$KeyStore="",
  [string]$PasswordFile=""
)
$ErrorActionPreference='Stop'
if(!$AndroidHome -or !$JavaHome){throw 'Set ANDROID_HOME and JAVA_HOME (JDK 17+). Install Android platform 36 and build-tools 36.0.0.'}
$suffix=if($IsWindows -or $env:OS -eq 'Windows_NT'){'.exe'}else{''}
$java=Join-Path $JavaHome "bin/java$suffix"
$javac=Join-Path $JavaHome "bin/javac$suffix"
$keytool=Join-Path $JavaHome "bin/keytool$suffix"
$tools=Join-Path $AndroidHome 'build-tools/36.0.0'
$aapt=Join-Path $tools "aapt2$suffix"
$android=Join-Path $AndroidHome 'platforms/android-36/android.jar'
$build=Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force "$build/classes","$build/generated","$build/dex" | Out-Null
function Check {if($LASTEXITCODE){throw "Build failed: $LASTEXITCODE"}}
& $aapt compile --dir "$PSScriptRoot/res" -o "$build/resources.zip";Check
& $aapt link -o "$build/unsigned.apk" --manifest "$PSScriptRoot/AndroidManifest.xml" -I $android --min-sdk-version 31 --target-sdk-version 36 --java "$build/generated" "$build/resources.zip";Check
$sources=@(Get-ChildItem "$PSScriptRoot/src","$build/generated" -Recurse -Filter '*.java' | ForEach-Object FullName)
& $javac -encoding UTF-8 -source 8 -target 8 -classpath $android -d "$build/classes" @sources;Check
New-Item -ItemType Directory -Force "$build/tests" | Out-Null
& $javac -encoding UTF-8 -source 8 -target 8 -classpath "$build/classes" -d "$build/tests" "$PSScriptRoot/tests/RulesTest.java" "$PSScriptRoot/tests/MemoryTest.java";Check
$separator=[IO.Path]::PathSeparator
& $java -cp "$build/classes$separator$build/tests" RulesTest;Check
& $java -cp "$build/classes$separator$build/tests" MemoryTest;Check
$classes=@(Get-ChildItem "$build/classes" -Recurse -Filter '*.class' | ForEach-Object FullName)
& $java -cp "$tools/lib/d8.jar" com.android.tools.r8.D8 --lib $android --min-api 31 --output "$build/dex" @classes;Check
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive=[System.IO.Compression.ZipFile]::Open("$build/unsigned.apk",'Update')
try{[System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive,"$build/dex/classes.dex",'classes.dex')|Out-Null}finally{$archive.Dispose()}
if(!$KeyStore){
 $KeyStore="$build/local-signing.p12";$PasswordFile="$build/local-signing-password.txt"
 if(!(Test-Path -LiteralPath $KeyStore)){
  [System.IO.File]::WriteAllText($PasswordFile,[guid]::NewGuid().ToString('N'))
  & $keytool -genkeypair -keystore $KeyStore -storetype PKCS12 -storepass:file $PasswordFile -alias aureon-defender -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Aureon Defender Local Build';Check
 }
}
if(!$PasswordFile){throw 'Provide the password file for your signing key. Never commit the key/password.'}
& (Join-Path $tools "zipalign$suffix") -f -p 4 "$build/unsigned.apk" "$build/aligned.apk";Check
& $java -jar "$tools/lib/apksigner.jar" sign --ks $KeyStore --ks-pass "file:$PasswordFile" --out "$build/aureon-defender.apk" "$build/aligned.apk";Check
& $java -jar "$tools/lib/apksigner.jar" verify --verbose "$build/aureon-defender.apk";Check
Write-Output "APK: $build/aureon-defender.apk"
