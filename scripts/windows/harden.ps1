<#
Aureon Windows hardening. Read-only by default: shows current state and what -Apply would change.
  powershell -ExecutionPolicy Bypass -File scripts\windows\harden.ps1
  (elevated) powershell -ExecutionPolicy Bypass -File scripts\windows\harden.ps1 -Apply
Review each item before using -Apply. Nothing here disables Windows Update or Defender.
#>
param([switch]$Apply)

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($Apply -and -not $admin) { Write-Host "-Apply needs an elevated PowerShell"; exit 1 }

function Step($name, $check, $fix) {
    $ok = $false
    try { $ok = [bool](& $check) } catch { $ok = $false }
    if ($ok) { Write-Host "[OK]   $name" -ForegroundColor Green; return }
    if ($Apply) {
        Write-Host "[FIX]  $name" -ForegroundColor Yellow
        try { & $fix } catch { Write-Host "       failed: $_" -ForegroundColor Red }
    } else {
        Write-Host "[TODO] $name" -ForegroundColor Yellow
    }
}

Step "Firewall on for all profiles" `
    { (Get-NetFirewallProfile | Where-Object Enabled -eq $false).Count -eq 0 } `
    { Set-NetFirewallProfile -All -Enabled True -DefaultInboundAction Block }

Step "Defender real-time protection" `
    { (Get-MpComputerStatus).RealTimeProtectionEnabled } `
    { Set-MpPreference -DisableRealtimeMonitoring $false }

Step "Defender PUA blocking" `
    { (Get-MpPreference).PUAProtection -eq 1 } `
    { Set-MpPreference -PUAProtection Enabled }

Step "Defender network protection" `
    { (Get-MpPreference).EnableNetworkProtection -eq 1 } `
    { Set-MpPreference -EnableNetworkProtection Enabled }

Step "Controlled Folder Access (ransomware shield)" `
    { (Get-MpPreference).EnableControlledFolderAccess -eq 1 } `
    { Set-MpPreference -EnableControlledFolderAccess Enabled }

# Common Attack Surface Reduction rules (block mode). GUIDs from Microsoft ASR reference.
$asr = @{
    "Block Office child processes"            = "d4f940ab-401b-4efc-aadc-ad5f3c50688a"
    "Block credential theft from LSASS"       = "9e6c4e1f-7d60-472f-ba1a-a39ef669e4b2"
    "Block executable email content"          = "be9ba2d9-53ea-4cdc-84e5-9b1eeee46550"
    "Block obfuscated scripts"                = "5beb7efe-fd9a-4556-801d-275e5ffc04cc"
    "Block untrusted USB processes"           = "b2b3f03d-6a65-4f7b-a9c7-1c7ef74a9ba4"
    "Block abuse of vulnerable signed drivers"= "56a863a9-875e-4185-98a7-b882c64b5ce5"
}
foreach ($k in $asr.Keys) {
    $id = $asr[$k]
    Step "ASR: $k" `
        { $p = Get-MpPreference; $i = [array]::IndexOf(@($p.AttackSurfaceReductionRules_Ids), $id); $i -ge 0 -and @($p.AttackSurfaceReductionRules_Actions)[$i] -eq 1 } `
        { Add-MpPreference -AttackSurfaceReductionRules_Ids $id -AttackSurfaceReductionRules_Actions Enabled }
}

Step "SMBv1 disabled" `
    { -not (Get-SmbServerConfiguration).EnableSMB1Protocol } `
    { Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force }

Step "Remote Desktop disabled" `
    { (Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server').fDenyTSConnections -eq 1 } `
    { Set-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 1 }

Step "LLMNR disabled (stops Responder-style poisoning)" `
    { (Get-ItemProperty 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient' -ErrorAction Stop).EnableMulticast -eq 0 } `
    { New-Item 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient' -Force | Out-Null
      Set-ItemProperty 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient' -Name EnableMulticast -Value 0 -Type DWord }

if ($admin) {
    $bl = (Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue).ProtectionStatus
    Write-Host ("[INFO] BitLocker on {0}: {1}  (turn on in Settings > Privacy & security > Device encryption)" -f $env:SystemDrive, $bl)
    try { Write-Host "[INFO] Secure Boot: $(Confirm-SecureBootUEFI)" } catch { Write-Host "[INFO] Secure Boot: unsupported/legacy" }
}

Write-Host ""
Write-Host "Recommended installs (winget):"
Write-Host "  winget install WireGuard.WireGuard tailscale.tailscale Syncthing.Syncthing VirusTotal.YARA Gitleaks.Gitleaks"
Write-Host "  winget install Ollama.Ollama RustDesk.RustDesk LizardByte.Sunshine WiresharkFoundation.Wireshark"
if (-not $Apply) { Write-Host "`n(read-only run - re-run elevated with -Apply to fix TODO items)" }
