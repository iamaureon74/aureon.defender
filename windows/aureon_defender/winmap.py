"""Research loop output: how each of the 53 Aureon capabilities (fused from all 790 Pi projects) lands on a
Windows laptop inside aureon.defender.

status:
  engine   - running 24/7 inside the aureon.defender engine (this package)
  studio   - part of the customization studio
  app      - in the dashboard / CLI on demand
  node     - Windows is the client; the heavy part runs on the Aureon Node
  branch   - researched, next development branch (see docs/defender/BRANCHES.md)
  n/a      - not meaningful on a Windows laptop
"""

WINMAP = {
 # SYSTEM
 "system.image":        ("app", "studio snapshot/restore + `export-profile`: rebuild your exact setup on a new PC", "NixOS/Ansible idea: declarative machine"),
 "system.firmware":     ("engine", "posture: Secure Boot, BitLocker/Device Encryption, TPM status every hour", "rpi-eeprom/sb-provisioner idea: verified boot chain"),
 "system.appliance":    ("node", "dashboard links to Node appliances (router, NAS, media)", "DietPi/OpenWrt personalities"),
 "system.research-os":  ("branch", "least-privilege: engine as SYSTEM, UI as user, inbox accepts only harmless requests", "OpenBSD pledge idea"),
 "system.knowledge":    ("app", "built-in help + offline docs; Kiwix on Node", "docs as RAG for local AI"),
 # HARDWARE
 "hardware.camera":     ("engine", "radar: which app used your camera, microphone, location or screen capture, and when (Windows' own access records)", "CapabilityAccessManager"),
 "hardware.io":         ("n/a", "GPIO not present on laptops; battery/thermal shown via psutil", ""),
 "hardware.key":        ("engine", "Aureon Key walk-away/panic lock + HID injection guard run inside the engine", "pico-sdk/TinyUSB + hidguard"),
 # PROTECT
 "protect.network-ids": ("engine", "network monitor: connections to known botnet C2 IPs (Feodo/abuse.ch), new listening ports, hosts-file and DNS hijack detection", "Suricata/CrowdSec/ntopng ideas on one host"),
 "protect.endpoint":    ("engine", "multi-engine scanner: Microsoft Defender engine + YARA + hash reputation + heuristics; real-time on Downloads/Desktop/Temp/Startup", "ClamAV/YARA/Wazuh/Lynis/OpenSnitch fused"),
 "protect.deception":   ("engine", "ransomware canary files: any change = HIGH alert + top disk writers named (optional auto-suspend)", "OpenCanary/Cowrie idea on the filesystem"),
 "protect.mobile":      ("app", "Phones: any Android (USB debugging or Termux) - every package by company, no-icon apps, admins, accessibility, sideloads, recent camera/mic/location; iPhone via libimobiledevice + MVT", "mvt-project/mvt + PiRogue ideas"),
 "protect.forensics":   ("app", "quarantine with full metadata; one-click Defender full scan; hash export for VirusTotal lookups", "Volatility/Sleuth Kit workflow"),
 "protect.secrets":     ("engine", "radar flags browser extensions with clipboard/cookie/all-sites powers; gitleaks scan is the next branch", "gitleaks/trufflehog"),
 "protect.wireless-watch": ("engine", "WiFi evil-twin / downgrade watch every minute via netsh", "Kismet + aureon rf"),
 "protect.audit":       ("app", "self-audit: open ports, SMBv1, RDP, LLMNR, ASR rules, firewall profiles", "Lynis/nmap ideas, read-only"),
 "protect.wifi-audit":  ("n/a", "offensive WiFi testing stays in the Linux lab profile", ""),
 "protect.physical":    ("engine", "USB keyboard-injection guard + autorun of removable media blocked by policy check", "Rubber Ducky/P4wnP1 threat model"),
 "protect.osint":       ("engine", "hidden-software radar: every program, service, task and extension by company, monitoring/stalkerware detection, Recall status", "spiderfoot idea turned inward"),
 # NETWORK
 "network.dns":         ("engine", "DNS shield: optional hosts-file blocklist (URLhaus malware domains); DNS-server change alerts", "Pi-hole/AdGuard on one PC"),
 "network.vpn":         ("app", "WireGuard/Tailscale status and one-click connect to the Node", "wg-easy/headscale"),
 "network.anonymity":   ("n/a", "Tor Browser recommended; not wired in", ""),
 "network.offgrid":     ("node", "send/receive LoRa texts through a USB Meshtastic radio", "meshtastic/python"),
 "network.access":      ("app", "Windows Mobile Hotspot status", ""),
 "network.storage":     ("app", "Syncthing status; quarantine/backup folder export", "syncthing/rclone"),
 "network.crypto-nodes": ("n/a", "", ""),
 # FREEDOM
 "freedom.cloud":       ("node", "dashboard tiles open Immich/Nextcloud/Vaultwarden on the Node", ""),
 "freedom.comms":       ("node", "", ""),
 "freedom.web":         ("n/a", "", ""),
 "freedom.data":        ("engine", "local SQLite: hash reputation, events; nothing leaves the PC", "postgres/redis role, embedded"),
 "freedom.business":    ("n/a", "", ""),
 "freedom.dev":         ("n/a", "", ""),
 "freedom.remote":      ("app", "PiKVM rescue commands from the dashboard", "pikvm/kvmd"),
 "freedom.dashboard":   ("app", "the aureon.defender dashboard itself", "homepage/dashy ideas"),
 # PERFORM
 "perform.observe":     ("engine", "CPU/RAM/disk/battery sampling + top processes; shown in dashboard and desktop widget", "Netdata/Glances/btop"),
 "perform.compute":     ("n/a", "", ""),
 "perform.compat":      ("n/a", "", ""),
 "perform.desktop":     ("studio", "theme, accent, transparency, taskbar, wallpaper, time format, fonts, desktop widgets - without heavy theming apps", "LVGL/Slint/info-beamer/MagicMirror widget ideas"),
 "perform.stream":      ("app", "Sunshine status (stream laptop to phone)", ""),
 # INTELLIGENCE
 "intel.llm":           ("engine", "daily plain-English security report via local Ollama/llama.cpp if present, rule-based otherwise", "aureon analyst"),
 "intel.voice":         ("branch", "offline voice commands (whisper.cpp)", ""),
 "intel.vision":        ("branch", "", ""),
 "intel.accel":         ("n/a", "", ""),
 "intel.robotics":      ("n/a", "", ""),
 # HOME / RADIO / MEDIA / MAKE / LEARN
 "home.automation":     ("node", "", ""),
 "radio.sdr":           ("branch", "RTL-SDR on Windows: rtl_433 tracker sweep", ""),
 "radio.aviation-space": ("n/a", "", ""),
 "radio.ham":           ("n/a", "", ""),
 "media.center":        ("n/a", "", ""),
 "media.play":          ("n/a", "", ""),
 "make.fabrication":    ("n/a", "", ""),
 "make.astro":          ("n/a", "", ""),
 "learn.code":          ("n/a", "", ""),
}
