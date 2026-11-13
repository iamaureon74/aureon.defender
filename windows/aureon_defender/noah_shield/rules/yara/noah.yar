// noah shield's bundled YARA rules, run over every risky download while it
// is held (lib/sec/yara.js). Each rule says in meta what it means and how
// sure it is: severity "critical" or "high" marks the file dangerous,
// "medium" asks you to look twice. Written for low false alarms: most need
// two independent signs before they fire.

rule EICAR_Test_File
{
    meta:
        description = "the EICAR anti-virus test file (harmless, used to check that scanning works)"
        severity = "high"
    strings:
        $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    condition:
        $eicar at 0 or ($eicar and filesize < 256)
}

rule PowerShell_Download_Cradle
{
    meta:
        description = "script downloads code from the internet and runs it in memory (PowerShell download cradle)"
        severity = "high"
    strings:
        $dl1 = "DownloadString" nocase ascii wide
        $dl2 = "DownloadData" nocase ascii wide
        $dl3 = "Invoke-WebRequest" nocase ascii wide
        $dl4 = "Net.WebClient" nocase ascii wide
        $dl5 = /\biwr\s+-?u/ nocase
        $run1 = "Invoke-Expression" nocase ascii wide
        $run2 = /\bIEX\s*[\(\$]/ nocase
        $run3 = "[Reflection.Assembly]::Load" nocase ascii wide
    condition:
        filesize < 5MB and any of ($dl*) and any of ($run*)
}

rule PowerShell_Encoded_Hidden
{
    meta:
        description = "starts PowerShell hidden with an encoded command, a common way to hide what a script does"
        severity = "high"
    strings:
        $ps = "powershell" nocase ascii wide
        $enc = /\s-e(nc|ncodedcommand)?\s+[A-Za-z0-9+\/=]{40,}/ nocase
        $hid = /-w(indowstyle)?\s+h(idden)?\b/ nocase
        $nop = /-nop(rofile)?\b/ nocase
    condition:
        filesize < 5MB and $ps and $enc and ($hid or $nop)
}

rule Office_Macro_AutoExec_Shell
{
    meta:
        description = "office macro that runs by itself on open and starts other programs"
        severity = "high"
    strings:
        $auto1 = "AutoOpen" nocase
        $auto2 = "Document_Open" nocase
        $auto3 = "Workbook_Open" nocase
        $auto4 = "Auto_Open" nocase
        $exec1 = "WScript.Shell" nocase
        $exec2 = "Shell.Application" nocase
        $exec3 = "CreateObject(\"MSXML2.XMLHTTP" nocase
        $exec4 = /\bShell\s*\(/ nocase
        $exec5 = "URLDownloadToFile" nocase
        $exec6 = "powershell" nocase
    condition:
        any of ($auto*) and 2 of ($exec*)
}

rule Script_Dropper_WSH
{
    meta:
        description = "Windows script that downloads a file, saves it and runs it"
        severity = "high"
    strings:
        $obj1 = "WScript.Shell" nocase ascii wide
        $obj2 = "MSXML2.XMLHTTP" nocase ascii wide
        $obj3 = "WinHttp.WinHttpRequest" nocase ascii wide
        $save1 = "ADODB.Stream" nocase ascii wide
        $save2 = "SaveToFile" nocase ascii wide
        $run1 = ".Run" nocase ascii wide
        $run2 = ".Exec" nocase ascii wide
        $run3 = "ShellExecute" nocase ascii wide
    condition:
        filesize < 2MB and ($obj2 or $obj3) and any of ($save*) and ($obj1 or any of ($run*))
}

rule HTA_ActiveX_Execution
{
    meta:
        description = "HTML application that runs programs through ActiveX"
        severity = "high"
    strings:
        $hta = "<hta:application" nocase
        $ax = "ActiveXObject" nocase
        $sh1 = "WScript.Shell" nocase
        $sh2 = "Shell.Application" nocase
    condition:
        filesize < 2MB and $hta and $ax and any of ($sh*)
}

rule LNK_Launches_Script_Host
{
    meta:
        description = "Windows shortcut that starts PowerShell, mshta, cmd or rundll32 (a common email attachment trick)"
        severity = "high"
    strings:
        $p1 = "powershell" nocase ascii wide
        $p2 = "mshta" nocase ascii wide
        $p3 = "cmd.exe" nocase ascii wide
        $p4 = "rundll32" nocase ascii wide
        $p5 = "wscript" nocase ascii wide
        $p6 = "certutil" nocase ascii wide
    condition:
        uint32(0) == 0x0000004C and filesize < 1MB and any of them
}

rule Credential_Dumper_Mimikatz
{
    meta:
        description = "contains Mimikatz, a tool that steals Windows passwords from memory"
        severity = "critical"
    strings:
        $s1 = "sekurlsa::logonpasswords" nocase ascii wide
        $s2 = "lsadump::sam" nocase ascii wide
        $s3 = "gentilkiwi" ascii wide
        $s4 = "mimikatz" nocase ascii wide
        $s5 = "kerberos::golden" nocase ascii wide
    condition:
        2 of them
}

rule CobaltStrike_Beacon_Strings
{
    meta:
        description = "strings of a Cobalt Strike beacon, a remote-control implant used by attackers"
        severity = "critical"
    strings:
        $s1 = "%s as %s\\%s: %d" ascii
        $s2 = "beacon.dll" ascii wide
        $s3 = "beacon.x64.dll" ascii wide
        $s4 = "ReflectiveLoader" ascii
        $s5 = "%02d/%02d/%02d %02d:%02d:%02d" ascii
        $s6 = "Started service %s on %s" ascii
    condition:
        uint16(0) == 0x5A4D and 3 of them
}

rule Crypto_Miner_XMRig
{
    meta:
        description = "contains the XMRig cryptocurrency miner (uses your computer to mine for someone else)"
        severity = "high"
    strings:
        $s1 = "stratum+tcp://" ascii wide
        $s2 = "xmrig" nocase ascii wide
        $s3 = "randomx" nocase ascii wide
        $s4 = "donate-level" ascii wide
        $s5 = "cryptonight" nocase ascii wide
    condition:
        3 of them
}

rule Infostealer_Wallet_And_Browser_Paths
{
    meta:
        description = "program that looks for browser passwords and crypto wallets together (typical of info-stealers)"
        severity = "high"
    strings:
        $b1 = "\\Google\\Chrome\\User Data" nocase ascii wide
        $b2 = "Login Data" ascii wide
        $b3 = "\\Mozilla\\Firefox\\Profiles" nocase ascii wide
        $b4 = "Local State" ascii wide
        $w1 = "wallet.dat" nocase ascii wide
        $w2 = "\\Exodus\\" nocase ascii wide
        $w3 = "\\Electrum\\wallets" nocase ascii wide
        $w4 = "nkbihfbeogaeaoehlefnkodbefgpgknn" ascii wide
        $w5 = "\\atomic\\Local Storage" nocase ascii wide
        $x1 = "discord" nocase ascii wide
        $x2 = "\\Telegram Desktop\\tdata" nocase ascii wide
    condition:
        filesize < 30MB and 2 of ($b*) and 2 of ($w*, $x*)
}

rule Ransom_Note_Language
{
    meta:
        description = "text of a ransomware note (files encrypted, pay in bitcoin, contact address)"
        severity = "high"
    strings:
        $a1 = "your files have been encrypted" nocase ascii wide
        $a2 = "all your files are encrypted" nocase ascii wide
        $a3 = "files are locked" nocase ascii wide
        $b1 = "bitcoin" nocase ascii wide
        $b2 = "decrypt" nocase ascii wide
        $b3 = ".onion" nocase ascii wide
        $b4 = "private key" nocase ascii wide
    condition:
        any of ($a*) and 2 of ($b*)
}

rule Reverse_Shell_OneLiner
{
    meta:
        description = "script opens a remote shell back to an attacker's machine"
        severity = "high"
    strings:
        $r1 = /bash\s+-i\s+>&\s*\/dev\/tcp\// ascii
        $r2 = /nc(at)?\s+(-\w+\s+)*-e\s+\/bin\/(ba)?sh/ ascii
        $r3 = "New-Object System.Net.Sockets.TCPClient" nocase ascii wide
        $r4 = /socket\.socket\(.{0,80}\.connect\(.{0,200}(subprocess|pty\.spawn|os\.dup2)/s
        $r5 = "GetStream()" nocase ascii wide
    condition:
        filesize < 2MB and ($r1 or $r2 or $r4 or ($r3 and $r5))
}

rule UPX_Packed_Program
{
    meta:
        description = "program compressed with UPX; legitimate tools use it too, but it hides code from simple scanners"
        severity = "medium"
    strings:
        $u0 = "UPX0" ascii
        $u1 = "UPX1" ascii
        $u2 = "UPX!" ascii
    condition:
        uint16(0) == 0x5A4D and $u0 and $u1 and $u2
}

rule PDF_JavaScript_AutoRun
{
    meta:
        description = "pdf that runs javascript as soon as it opens"
        severity = "high"
    strings:
        $js1 = "/JavaScript" ascii
        $js2 = "/JS" ascii
        $open = "/OpenAction" ascii
        $aa = "/AA" ascii
        $bad1 = "eval(" ascii
        $bad2 = "unescape(" ascii
        $bad3 = "String.fromCharCode" ascii
    condition:
        uint32(0) == 0x46445025 and any of ($js*) and ($open or $aa) and any of ($bad*)
}

rule Office_DDE_Field
{
    meta:
        description = "office document with a DDE field that can start a program without macros"
        severity = "high"
    strings:
        $d1 = /DDEAUTO\s/ nocase
        $d2 = /\bDDE\s+"?c:\\/ nocase
        $c1 = "cmd" nocase
        $c2 = "powershell" nocase
        $c3 = "mshta" nocase
    condition:
        any of ($d*) and any of ($c*)
}

rule Browser_Extension_Stealer_Manifest
{
    meta:
        description = "packed browser extension that asks for every site, cookies and native messaging at once"
        severity = "medium"
    strings:
        $m = "\"manifest_version\"" ascii
        $p1 = "\"<all_urls>\"" ascii
        $p2 = "\"cookies\"" ascii
        $p3 = "\"nativeMessaging\"" ascii
        $p4 = "\"debugger\"" ascii
    condition:
        filesize < 5MB and $m and $p1 and $p2 and ($p3 or $p4)
}
