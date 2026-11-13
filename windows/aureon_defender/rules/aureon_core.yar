/*
  Aureon starter rules. Behaviour-oriented, written for this project.
  Drop more .yar files into %ProgramData%\Aureon\rules (e.g. from the YARA Forge community bundle).
*/

rule Aureon_PowerShell_Download_Cradle
{
    meta:
        description = "PowerShell that downloads and immediately executes code"
        severity = "high"
    strings:
        $dl1 = "DownloadString" ascii wide nocase
        $dl2 = "DownloadData" ascii wide nocase
        $dl3 = "Invoke-WebRequest" ascii wide nocase
        $dl4 = "Net.WebClient" ascii wide nocase
        $ex1 = "IEX" ascii wide
        $ex2 = "Invoke-Expression" ascii wide nocase
        $ex3 = "[Reflection.Assembly]::Load" ascii wide nocase
    condition:
        filesize < 2MB and 1 of ($dl*) and 1 of ($ex*)
}

rule Aureon_Ransom_Note_And_Shadow_Delete
{
    meta:
        description = "Deletes shadow copies and mentions ransom/decrypt"
        severity = "high"
    strings:
        $s1 = "vssadmin delete shadows" ascii wide nocase
        $s2 = "wmic shadowcopy delete" ascii wide nocase
        $s3 = "bcdedit /set {default} recoveryenabled no" ascii wide nocase
        $n1 = "decrypt" ascii wide nocase
        $n2 = "bitcoin" ascii wide nocase
        $n3 = ".onion" ascii wide nocase
    condition:
        1 of ($s*) and 1 of ($n*)
}

rule Aureon_Credential_Dumper_Strings
{
    meta:
        description = "Strings typical of LSASS credential dumping tools"
        severity = "high"
    strings:
        $a = "sekurlsa::logonpasswords" ascii wide nocase
        $b = "lsadump::sam" ascii wide nocase
        $c = "MiniDumpWriteDump" ascii
        $d = "lsass.exe" ascii wide nocase
        $e = "comsvcs.dll, MiniDump" ascii wide nocase
    condition:
        $a or $b or $e or ($c and $d and uint16(0) == 0x5A4D)
}

rule Aureon_Defender_Tamper
{
    meta:
        description = "Script that disables Microsoft Defender protections"
        severity = "high"
    strings:
        $a = "Set-MpPreference -DisableRealtimeMonitoring $true" ascii wide nocase
        $b = "Add-MpPreference -ExclusionPath" ascii wide nocase
        $c = "DisableAntiSpyware" ascii wide nocase
    condition:
        filesize < 5MB and any of them
}

rule Aureon_Infostealer_Browser_Paths
{
    meta:
        description = "Reads several browsers' saved-password stores (infostealer pattern)"
        severity = "medium"
    strings:
        $c = "\\Google\\Chrome\\User Data\\Default\\Login Data" ascii wide nocase
        $e = "\\Microsoft\\Edge\\User Data\\Default\\Login Data" ascii wide nocase
        $b = "\\BraveSoftware\\Brave-Browser\\User Data" ascii wide nocase
        $f = "\\Mozilla\\Firefox\\Profiles" ascii wide nocase
        $w = "wallet.dat" ascii wide nocase
        $t = "\\Telegram Desktop\\tdata" ascii wide nocase
    condition:
        uint16(0) == 0x5A4D and 3 of them
}
