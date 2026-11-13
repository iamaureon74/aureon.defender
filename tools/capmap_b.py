"""Capability map part B (see capmap_a.py for format)."""

CAPS_B = [
("protect.network-ids", "PROTECT", "Network detection & prevention",
 "Gateway IDS/IPS that combines Suricata's inline rules, Zeek's protocol logs, Snort's rule ecosystem, CrowdSec's crowd-sourced blocklists and fail2ban's log bans; ntopng-style per-device visibility on top.",
 "deploy/shield (built): suricata, crowdsec; aureon analyst reads them",
 """
OISF/suricata: multi-threaded IDS/IPS + EVE JSON
zeek/zeek: deep protocol logging for hunting
snort3/snort3: mature rule ecosystem
crowdsecurity/crowdsec: crowd-sourced IP reputation + bouncers
fail2ban/fail2ban: log-driven bans
ntop/ntopng: per-host traffic visibility
DShield-ISC/dshield: share sensor data with SANS ISC
"""),

("protect.endpoint", "PROTECT", "Endpoint protection (EDR + AV + app firewall)",
 "Laptop EDR without a vendor: Wazuh FIM/rootkit/vuln checks, OSSEC fallback, ClamAV signatures, YARA hunting rules, OpenSnitch per-app outbound control, Lynis hardening score.",
 "aureon audit (built), scripts/linux/harden.sh, scripts/windows/harden.ps1 (built)",
 """
wazuh/wazuh: EDR/SIEM with file integrity + vuln detection
ossec/ossec-hids: lightweight host IDS
Cisco-Talos/clamav: open AV engine
VirusTotal/yara: malware pattern rules
CISOfy/lynis: hardening audit with score
evilsocket/opensnitch: per-app outbound firewall
"""),

("protect.deception", "PROTECT", "Deception & tripwires",
 "Fake services that no legitimate user touches, so any hit is a real intrusion: OpenCanary tripwires, Cowrie shell recording, T-Pot breadth.",
 "deploy/shield opencanary (built), analyst treats hits as HIGH (built)",
 """
thinkst/opencanary: lightweight multi-protocol canary
cowrie/cowrie: SSH/Telnet honeypot with session replay
telekom-security/tpotce: 20+ honeypots + ELK
"""),

("protect.mobile", "PROTECT", "Phone spyware & traffic forensics",
 "MVT IOC scanning + PiRogue network capture + Suricata rules = check both what is on the phone and what it talks to.",
 "docs/PHONE.md, profiles phone-*, deploy/shield suricata",
 """
mvt-project/mvt: Pegasus/Predator IOC scanning
PiRogueToolSuite/pirogue-cli: phone traffic interception station
"""),

("protect.forensics", "PROTECT", "Forensics & reverse engineering",
 "Incident-response kit: memory (Volatility), disk (Sleuth Kit/Autopsy), packets (Wireshark), binaries/APKs (Ghidra, radare2, Cutter, pwndbg).",
 "catalog defend layer; aureon fetch defend",
 """
volatilityfoundation/volatility3: memory forensics
sleuthkit/sleuthkit: filesystem forensics
sleuthkit/autopsy: forensics GUI + timeline
wireshark/wireshark: packet dissection
NationalSecurityAgency/ghidra: decompiler
radareorg/radare2: scriptable RE (runs on phones)
rizinorg/cutter: RE GUI
pwndbg/pwndbg: exploit-aware GDB
Gallopsled/pwntools: exploit/CTF toolkit
"""),

("protect.secrets", "PROTECT", "Secrets & credentials hygiene",
 "Find leaked keys before attackers do (gitleaks, trufflehog verification) and keep passwords in your own vault (Vaultwarden).",
 "deploy/cloud vaultwarden (built); profile laptop-windows gitleaks",
 """
gitleaks/gitleaks: secret scanning in git history
trufflesecurity/trufflehog: verified credential detection
dani-garcia/vaultwarden: self-hosted Bitwarden server
AlessandroZ/LaZagne: password recovery - used to test what malware could steal
gentilkiwi/mimikatz: credential extraction - informs LSASS protection (ASR rule)
"""),

("protect.wireless-watch", "RADIO", "Rogue WiFi & fake cell-tower watch",
 "Baseline-and-compare across radios: Kismet's rogue-AP logic, kalibrate-rtl GSM survey, gr-gsm decoding, phone cell info - flags evil twins, security downgrades, 2G forcing, new LAC/TAC.",
 "aureon rf wifi|cell|gsm (built)",
 """
kismetwireless/kismet: wireless IDS
ptrkrysik/gr-gsm: GSM decoding
steve-m/kalibrate-rtl: GSM base-station scan
"""),

("protect.audit", "PROTECT", "Self-audit lab (authorized use only)",
 "See your own devices as an attacker would: discovery, vuln scanning, web testing, password strength, WiFi strength, AD paths, OSINT exposure. Never auto-installed.",
 "profile lab; catalog audit layer",
 """
carlospolop/PEASS-ng: privilege-escalation checks (run on your own hosts to find misconfig)
peass-ng/PEASS-ng: PEASS-ng (current home)
PowerShellMafia/PowerSploit: PowerShell post-exploitation (threat model for Windows hardening)
swisskyrepo/PayloadsAllTheThings: payload reference for testing your own apps
nmap/nmap: service/OS discovery
RustScan/RustScan: fast port discovery
robertdavidgraham/masscan: very fast scanning
zmap/zmap: network surveys
greenbone/openvas-scanner: full vuln scanner
projectdiscovery/nuclei: template vuln checks
projectdiscovery/httpx: HTTP probing
projectdiscovery/subfinder: subdomain discovery
zaproxy/zaproxy: web app scanner/proxy
sullo/nikto: web server misconfig
sqlmapproject/sqlmap: SQL injection testing
commixproject/commix: command-injection testing
ffuf/ffuf: fast fuzzing
OJ/gobuster: dir/DNS brute force
epi052/feroxbuster: recursive content discovery
rapid7/metasploit-framework: exploit framework
fortra/impacket: Windows protocol library
SecureAuthCorp/impacket: impacket (older home)
Pennyw0rth/NetExec: network credential auditing
byt3bl33d3r/CrackMapExec: NetExec predecessor
SpecterOps/BloodHound: AD attack-path graphs
BloodHoundAD/BloodHound: BloodHound legacy
lgandx/Responder: LLMNR/NBT-NS poisoning test
hashcat/hashcat: GPU password auditing
openwall/john: CPU password auditing
vanhauser-thc/thc-hydra: online login testing
threat9/routersploit: router vuln testing
mitmproxy/mitmproxy: inspect your own app traffic
beefproject/beef: browser exploitation test
trustedsec/social-engineer-toolkit: phishing-awareness simulation
Ettercap/ettercap: LAN MITM testing
bettercap/bettercap: network/BLE/WiFi attack simulation
bettercap/caplets: bettercap scripts
LionSec/xerosploit: MITM toolkit
moxie0/sslstrip: HTTPS downgrade demo (why HSTS matters)
danielmiessler/SecLists: wordlists
"""),

("protect.wifi-audit", "PROTECT", "WiFi & RF strength testing (own networks)",
 "Prove your own WPA key and router resist real attacks: handshake/PMKID capture, WPS checks, evil-twin simulations, then harden.",
 "profile lab",
 """
aircrack-ng/aircrack-ng: WiFi audit suite
aircrack-ng/rtl8812au: monitor-mode USB WiFi driver
ZerBea/hcxdumptool: PMKID/handshake capture
ZerBea/hcxtools: capture conversion
derv82/wifite2: automated WiFi audit
kimocoder/wifite2: maintained wifite2
v1s1t0r1sh3r3/airgeddon: menu-driven WiFi audit
aanarchyy/bully: WPS PIN testing
t6x/reaver-wps-fork-t6x: WPS testing
wiire-a/pixiewps: WPS pixie-dust test
s0lst1c3/eaphammer: WPA-Enterprise evil twin test
sensepost/hostapd-mana: rogue AP research
P0cL4bs/wifipumpkin3: rogue AP framework
wifiphisher/wifiphisher: phishing AP simulation
FluxionNetwork/fluxion: captive-portal attack simulation
SpacehuhnTech/esp8266_deauther: deauth testing (shows why WPA3/PMF matter)
justcallmekoko/ESP32Marauder: ESP32 WiFi/BLE audit
evilsocket/arc: encrypted vault on the go
"""),

("protect.physical", "PROTECT", "Physical/USB/NFC attack surface",
 "Understand BadUSB, NFC cloning and multi-tool attacks so Aureon Key + hidguard can stop them.",
 "aureon hidguard (built), key/ (built)",
 """
RoganDawes/P4wnP1_aloa: USB/WiFi/Bluetooth attack implant (threat model)
mame82/P4wnP1: P4wnP1 original
mame82/P4wnP1_aloa: P4wnP1 A.L.O.A.
hak5/bashbunny-payloads: USB attack payloads (threat model)
hak5/sharkjack-payloads: Ethernet implant payloads (threat model)
hak5/usbrubberducky-payloads: keystroke injection (threat model)
SpacehuhnTech/WiFiDuck: WiFi-controlled keystroke injector
flipperdevices/flipperzero-firmware: multi-protocol RF/NFC tool
DarkFlippers/unleashed-firmware: extended Flipper firmware
RogueMaster/flipperzero-firmware-wPlugins: Flipper with plugins
Proxmark/proxmark3: RFID/NFC research
RfidResearchGroup/proxmark3: maintained Proxmark firmware
AdamLaurie/RFIDIOt: RFID Python tools
nfc-tools/libnfc: NFC library
nfc-tools/mfoc: MIFARE Classic key recovery (shows it is broken)
"""),

("protect.osint", "PROTECT", "Personal exposure (OSINT on yourself)",
 "Find what the internet knows about you: accounts by email/username, phone exposure, domain footprint - then lock it down.",
 "profile lab; Termux setup installs holehe/sherlock",
 """
s0md3v/Photon: fast crawler for your own site's exposed data
megadose/holehe: which sites use your email
sherlock-project/sherlock: username across sites
soxoj/maigret: username dossier
mxrch/GHunt: Google-account exposure
sundowndev/phoneinfoga: phone-number footprint
smicallef/spiderfoot: automated OSINT
laramies/theHarvester: domain emails/hosts
lanmaster53/recon-ng: modular recon
"""),

("network.dns", "NETWORK", "Private filtered DNS",
 "AdGuard's encrypted DoH/DoT for phones + Pi-hole's blocklists + unbound recursion = no ISP or provider sees your queries.",
 "deploy/shield (built)",
 """
AdguardTeam/AdGuardHome: DoH/DoT filtering server
pi-hole/pi-hole: DNS sinkhole
pi-hole/FTL: fast DNS engine
pi-hole/web: Pi-hole dashboard
pi-hole/docker-pi-hole: containerised Pi-hole
NLnetLabs/unbound: recursive DNSSEC resolver
"""),

("network.vpn", "NETWORK", "VPN & mesh overlay",
 "WireGuard speed + wg-easy QR onboarding + Tailscale NAT traversal + headscale self-hosting + ZeroTier/Yggdrasil fallback meshes.",
 "deploy/shield wg-easy (built); profiles",
 """
WireGuard/wireguard-tools: fast modern VPN
wg-easy/wg-easy: WireGuard UI with QR codes
angristan/wireguard-install: one-script WireGuard server
pivpn/pivpn: guided VPN server
OpenVPN/openvpn: compatible fallback VPN
Nyr/openvpn-install: one-script OpenVPN
tailscale/tailscale: NAT-traversing mesh
juanfont/headscale: self-hosted Tailscale control
ZeroTier/ZeroTierOne: virtual L2 network
yggdrasil-network/yggdrasil-go: encrypted IPv6 mesh
cloudflare/cloudflared: outbound-only tunnels
"""),

("network.anonymity", "NETWORK", "Anonymity",
 "Tor + I2P routers, transparent torification, onion file sharing.",
 "catalog net layer; Termux tor",
 """
torproject/tor: onion routing
PurpleI2P/i2pd: lightweight I2P
i2p/i2p.i2p: Java I2P router
brainfucksec/kalitorify: transparent Tor proxy
breadtk/onion_pi: Tor access point
onionshare/onionshare: anonymous file sharing
"""),

("network.offgrid", "RADIO", "Off-grid encrypted communication",
 "Meshtastic LoRa texting + Reticulum's medium-agnostic encrypted networking + NomadNet messaging; Aureon relays alert headlines over the mesh.",
 "deploy/offgrid (built), aureon mesh (built)",
 """
meshtastic/firmware: LoRa mesh radio firmware
meshtastic/python: Meshtastic API/CLI
markqvist/Reticulum: encrypted networking over any link
markqvist/NomadNet: off-grid messaging/pages
wb2osz/direwolf: software packet-radio TNC
"""),

("network.access", "NETWORK", "Access point & connectivity",
 "Node as a secure travel router: captive WiFi onboarding, hotspot sharing, AP management.",
 "catalog net layer",
 """
RaspAP/raspap-webgui: router/AP web UI
billz/raspap-webgui: RaspAP (original)
balena-io/wifi-connect: captive-portal WiFi setup
balena-os/wifi-connect: wifi-connect (moved)
jasbur/RaspiWiFi: AP-mode WiFi setup
sabhiram/raspberry-wifi-conf: WiFi config via AP
lakinduakash/linux-wifi-hotspot: laptop hotspot
oblique/create_ap: one-command AP
netbootxyz/netboot.xyz: network-boot any OS installer
"""),

("network.storage", "NETWORK", "Sync, sharing & transfer",
 "Syncthing P2P between phone and laptop, rclone-crypt backups anywhere, SMB/AFP for legacy, IPFS for content addressing, torrent clients for large public data.",
 "profiles (syncthing); profile node backups (rclone)",
 """
Prowlarr/Prowlarr: indexer manager
syncthing/syncthing: P2P encrypted sync
rclone/rclone: encrypted cloud backup
samba-team/samba: Windows file sharing
netatalk/netatalk: AFP/Time Machine
ipfs/kubo: content-addressed storage
qbittorrent/qBittorrent: BitTorrent client
transmission/transmission: light BitTorrent daemon
Radarr/Radarr: media library automation
Sonarr/Sonarr: series library automation
"""),

("network.crypto-nodes", "NETWORK", "Sovereign money nodes",
 "Validate your own transactions with full nodes - no third-party wallet servers learning your addresses.",
 "catalog only (optional Node personality)",
 """
bitcoin/bitcoin: full node
ElementsProject/lightning: Core Lightning
lightningnetwork/lnd: LND Lightning
monero-project/monero: private-by-default node
"""),
]
