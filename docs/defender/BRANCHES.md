# aureon.defender: research and development branches

The work runs as a loop: research a capability, build it, test it, and note the branches it opens. Each
branch below came from a previous one. Status: **done** (built and tested in this repo), **next**
(researched, ready to build), **later** (needs hardware, signing or a platform decision).

```
aureon.defender
├── Protection engine ................................................. done
│   ├── Real-time folder watch (download-settle detection) ............ done
│   │   ├── ReadDirectoryChangesW instead of polling (lower latency) .. next
│   │   └── Scan on USB-drive insert (removable media) ................ next
│   ├── Multi-engine scanner .......................................... done
│   │   ├── Reputation DB (MalwareBazaar) ............................. done
│   │   │   └── Full MalwareBazaar daily dump + bloom filter .......... next
│   │   ├── Delivery-trick heuristics (RTLO, double ext, LNK, ISO,
│   │   │   macro docs, password zips, disguised EXEs, broken sigs) .. done
│   │   │   └── OneNote (.one) and HTML-smuggling lures .............. next
│   │   ├── YARA (bundled rules + user rules folder) ................. done
│   │   │   └── YARA Forge community bundle auto-update ............... next
│   │   └── Microsoft Defender engine (MpCmdRun, offline) ............ done
│   ├── Quarantine (scrambled, restorable) ............................ done
│   ├── Ransomware tripwires + writer identification .................. done
│   │   ├── Optional auto-suspend of unsigned writer .................. done
│   │   └── Volume Shadow Copy snapshot before risky installs ......... next
│   ├── Autostart watch (Run keys, Winlogon, Startup, tasks, services) done
│   │   └── WMI event subscriptions + IFEO debugger hijacks ........... next
│   ├── Network watch (C2 IPs, new ports, hosts, DNS) ................. done
│   │   ├── Per-app outbound firewall (OpenSnitch idea via WFP) ....... later (needs a signed driver)
│   │   └── DNS shield via hosts file (URLhaus) ....................... done
│   ├── USB keyboard-injection guard (+ screen lock) .................. done
│   ├── WiFi evil-twin watch .......................................... done
│   ├── Security-settings posture (hourly) ............................ done
│   └── Daily report via local LLM .................................... done
├── Studio (looks without heavy apps) ................................. done
│   ├── Theme, accent, transparency, taskbar, seconds, time/date ...... done
│   ├── Generated wallpapers, 6 presets ............................... done
│   │   ├── Live/animated wallpaper (WorkerW layer) ................... next
│   │   └── Time-of-day wallpaper (dawn/day/dusk/night) ............... next
│   ├── Per-user font install ......................................... done
│   │   └── Google Fonts browser + one-click install (online) ......... next
│   ├── Desktop widget: clock, date, stats, shield .................... done
│   │   ├── Weather (Open-Meteo, no key) and calendar ................. next
│   │   └── Multiple widgets, drag to place ........................... next
│   ├── Undo everything in one click .................................. done
│   └── Cursor themes, sounds, lock-screen image ...................... next
├── Hidden-software radar ............................................. done
│   ├── Programs incl. hidden uninstall entries, by company ........... done
│   ├── Services / tasks / autostarts attributed by file signer ....... done
│   ├── Vendor telemetry (Microsoft, NVIDIA, Intel, ASUS, Dell, HP...) . done
│   ├── Camera / mic / location / screen-capture access log .......... done
│   ├── Recall snapshot detection ..................................... done
│   ├── Monitoring / stalkerware product detection .................... done
│   ├── Browser extensions with broad powers .......................... done
│   ├── Per-company network destinations (which vendor phones home) ... next
│   └── Firmware/UEFI implants and driver inventory ................... next
├── Phones ............................................................ done
│   ├── Android over USB (any brand) and inside Termux ................ done
│   │   ├── Packages by company, no-icon apps, admins, accessibility .. done
│   │   ├── Preload explanations (carrier, OEM, Meta, Google) ......... done
│   │   ├── AppOps recent camera/mic/location/screen/SMS use .......... done
│   │   ├── Auto-scan on plug-in + change log ......................... done
│   │   ├── Disable/uninstall a preload for this user from the app .... next
│   │   └── Wireless ADB pairing (no cable) ........................... next
│   ├── iPhone: apps + provisioning profiles (libimobiledevice) ....... done
│   │   └── Guided encrypted backup + MVT in the app .................. next
│   └── View-only phone link on home WiFi ............................. done
├── Dashboard (void & ember, floating dock, phone layout) ............. done
│   ├── Token + Host pinning + JSON-only POSTs ........................ done
│   └── Tray icon ..................................................... next
├── Install / 24-7 operation .......................................... done
│   ├── SYSTEM engine task, restart-forever, battery-safe ............. done
│   ├── Locked-down ProgramData ACLs, harmless-only inbox ............. done
│   ├── Code signing (stops SmartScreen warnings) ..................... later (needs a certificate)
│   └── Windows Security Center registration .......................... later (needs Microsoft AV program + ELAM driver)
└── Bridges to the rest of Aureon
    ├── Phone spyware check (MVT) from the dashboard .................. next
    ├── WireGuard/Tailscale to the Node ............................... next
    ├── PiKVM rescue panel ............................................ next
    └── Meshtastic alerts over LoRa ................................... next
```

## Why Microsoft Defender stays underneath

Windows only switches Microsoft Defender off when another antivirus registers with Windows Security
Center. Registration is limited to vendors in Microsoft's antivirus partner programme, and their products
ship an early-launch (ELAM) kernel driver signed by Microsoft. Without that, forcing Defender off leaves
the PC with no kernel-level real-time protection at all.

So aureon.defender is the front end and the brain: it decides, alerts, quarantines, watches what Defender
doesn't (autostart, tripwires, C2 traffic, USB injection, WiFi twins, delivery tricks) and uses Defender's
offline engine as one of its scanners. Nothing in Aureon needs Azure or any Microsoft cloud account. The only
online traffic is the free abuse.ch feeds and Defender's own signature updates.
