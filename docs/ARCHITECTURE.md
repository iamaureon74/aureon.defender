# Aureon Hardware - architecture

Aureon is not one more tool. It is **four pieces that combine the best capability of all 790 projects** (53 fused capabilities, 20 organs - see [CAPABILITIES.md](CAPABILITIES.md) and [ORGANISM.md](ORGANISM.md)) from
[shep95/rasberry-pi](https://github.com/shep95/rasberry-pi) into one system for laptops and phones.

```
                 ┌──────────────────────────── Aureon Node (Pi 5 / mini-PC) ─────────────────────────────┐
  Phone ──WG──▶  │ wg-easy ─▶ AdGuard Home ─▶ unbound      Suricata/Zeek   CrowdSec   OpenCanary  Netdata │
  Laptop ─WG──▶  │ (VPN)      (filter, DoT)   (recursive)  (IDS)           (IPS)      (tripwire)  (metrics)│
                 │ optional: Immich · Nextcloud · Vaultwarden · Ollama+Open WebUI · Wazuh manager · Kiwix │
                 └───────────────────────────────────────────────────────────────────────────────────────┘
                        ▲ alerts / EDR events (Wazuh, CrowdSec)            ▲ Syncthing P2P
  ┌──────────── Aureon Agent (laptop) ────────────┐        ┌──────────── Aureon Mobile (phone) ───────────┐
  │ python -m aureon audit  (posture score)        │        │ Private DNS (DoT) → Node                     │
  │ harden: firewall · OpenSnitch · CrowdSec ·     │        │ Always-on WireGuard + kill switch            │
  │   fail2ban · sysctl · ClamAV/YARA · Wazuh      │        │ MVT spyware scan (from laptop)               │
  │ perf: zram · governor · TRIM · light Wayland · │        │ PiRogue traffic inspection (Node)            │
  │   FEX/box64 on ARM                             │        │ Termux: nmap · tor · llama.cpp · radare2     │
  │ local AI: llama.cpp/Ollama · whisper · piper   │        │ Immich / Nextcloud / RustDesk / Moonlight    │
  └──────────────▲─────────────────────────────────┘        └──────────────────────────────────────────────┘
                 │ USB serial
        ┌────────┴─────── Aureon Key (Pico / Pico 2) ───────┐
        │ panic button · tamper switch · walk-away lock     │
        │ (future: FIDO2 token, USB-HID injection guard)    │
        └───────────────────────────────────────────────────┘
```

## Why these combinations

| Goal | Combination | What the combo gives you that no single project does |
|---|---|---|
| Protect the phone everywhere | wg-easy + AdGuard Home + unbound + CrowdSec | Phone's DNS and traffic go through *your* filter and IPS on any WiFi or cell network; no third-party DNS provider sees queries |
| Detect phone spyware | MVT + PiRogue + Suricata + YARA | Forensic IOC scan of the device *and* live network inspection of what it talks to |
| Laptop EDR without a vendor | Wazuh agent + manager on Node + ClamAV + YARA + OpenSnitch | File integrity, rootkit checks, malware scan, outbound app control, central alerts |
| Know when you're being probed | OpenCanary + Cowrie + CrowdSec + Netdata anomalies | Tripwires turn any LAN intrusion into an alert within seconds |
| Rogue WiFi / IMSI catcher awareness | Kismet + gr-gsm + kalibrate-rtl + RTL-SDR | Baseline your normal radio environment; flag new APs, deauth floods, odd cell towers |
| Faster laptop | zram + TRIM + governor + sway/labwc + Netdata | More usable RAM, less swap stall, lighter desktop, and measurements to prove it |
| Run more software | FEX/box64/Hangover + Wine + Podman + Incus | x86 apps on ARM laptops, Windows apps on Linux, everything sandboxed |
| Private AI on device | llama.cpp/Ollama + whisper.cpp + piper + openWakeWord + ONNX/OpenVINO/Coral | Offline voice assistant; NPU/TPU acceleration where present |
| Freedom from big-tech clouds | Immich + Nextcloud + Vaultwarden + Syncthing + Matrix + Jitsi | Photos, files, passwords, chat and calls you own |
| Laptop-phone fusion | Sunshine + Moonlight + RustDesk + Syncthing + code-server | Phone becomes a remote screen/controller for the laptop; files sync P2P |
| Physical security | Aureon Key (pico-sdk/TinyUSB/MicroPython) + keyagent | Hardware panic/tamper/walk-away lock |

## Layers (see `stack.json`)

| Layer | Purpose | Count |
|---|---|---|
| base | OS, boot, VMs, sandboxing, app compatibility | 17 |
| defend | firewall, IDS/IPS, AV, EDR, forensics, honeypots | 31 |
| audit | authorized self-audit lab - never auto-installed | 39 |
| net | DNS, VPN, mesh, anonymity, sync | 19 |
| perf | monitoring, x86-on-ARM, streaming, light desktops | 28 |
| ai | local LLM, speech, vision, accelerators | 23 |
| cloud | self-hosted replacements for cloud services | 20 |
| key | Pico toolchains for the Aureon Key | 14 |
| rf | SDR / radio-environment awareness / off-grid comms | 12 |
| ops | provisioning, containers, backups | 12 |

## Honest limits

- Phones are locked down by design. On stock iOS/Android the real levers are DNS, VPN, app
  choice and forensics (MVT) - not kernel changes. Custom ROMs need an unlockable bootloader and a
  device-specific build; the Pi/Android manifests in the catalog are only references.
- Nothing in the catalog overclocks laptop CPUs safely; "faster" here means memory compression,
  lighter software, correct power profiles and offloading heavy work (AI, media, storage) to the Node.
- Audit-layer tools are for systems you own or are authorized to test. They are listed so you can
  see your devices the way an attacker would, and are never installed by a profile automatically.
