# aureon.defender

The command centre for a Windows laptop and the phones you plug into it. It protects 24/7, online or offline,
whether or not the window is open. It shows what every company has installed, running or watching, keeps a timeline
of every device that has ever connected, and brings all of noah.shield's protection system-wide. A 40 MB download,
no account.

## Install

1. Download [`release/aureon-defender-windows-x64-0.4.0.zip`](https://github.com/shep95/aureon.defender/releases/tag/v0.4.1) and check it against the `.sha256` file next to it.
2. Unzip it anywhere, open the `aureon.defender` folder and run `aureon.defender.exe install`, then approve the
   administrator prompt. The publisher is not code-signed; Windows may warn. Verify the source and release hash before deciding whether to install.
3. The dashboard opens. The engine now starts with Windows as SYSTEM and restarts itself if anything stops it.

To update, run `install` from a newer zip: it replaces the installed copy and waits for the new engine to report.
Diagnostics: `%ProgramData%\Aureon\aureon.log`. Remove: *Settings → Apps → Aureon Defender → Uninstall*.

It ships as a normal program folder, not a single self-extracting exe. Antivirus machine-learning models routinely
mis-flag unsigned single-file Python exes (Defender called our first build `Trojan:Win32/Bearfoos.B!ml`). The folder
build scans clean with Microsoft Defender.

## What runs 24/7

| Sensor | Every | What it catches |
|---|---|---|
| Real-time files | 2 s | New downloads, Desktop, Temp and Startup files: reputation, delivery tricks, YARA (Aureon + noah.shield rules), Defender engine |
| Device log | 3 s | Every connect / disconnect: USB drives, phones, Bluetooth, headphones, displays, keyboards, cameras |
| Ransomware tripwires | 5 s | Hidden decoy documents; any change names the busiest writers (optional auto-freeze) |
| USB keyboard guard | 2 s | Fake-keyboard USB sticks (optionally locks the screen) |
| Network watch | 15 s | Connections to known botnet servers, new open ports, hosts-file and DNS hijacks |
| Defender alerts | 1 min | Everything Microsoft Defender catches, shown as Aureon alerts |
| WiFi watch | 1 min | Evil-twin and downgraded copies of trusted networks |
| Autostart watch | 5 min | New Run keys, Winlogon changes, Startup items, scheduled tasks, services |
| Hidden-software radar | 30 min | Every program (incl. hidden ones), service, task, extension by company; telemetry; stalkerware; Recall; camera/mic/location/screen access |
| Security settings | 1 h | Firewall, Defender, Secure Boot, BitLocker, SMBv1, RDP, open ports |
| Leak audit | 6 h | 17 privacy settings and every security product registered with Windows |
| Device history | 6 h | Windows' own records: first and last connection of every USB / Bluetooth / phone / display device and every network joined; tracking tags (Tile, AirTag, SmartTag…) flagged |
| Threat feeds | 6 h (online) | abuse.ch lists, Defender signatures; the DNS shield applies malware and (opt-in) noah.shield tracker domains to every app |
| Daily report | 24 h | Plain-English summary, written by a local AI model if Ollama is running |

In your session: branded notifications (Aureon's name and icon, Open/Dismiss, bursts merged, quiet hours) and a
clipboard guard that warns when a key, card number or wallet phrase is copied and clears it after 60 seconds.

## noah.shield, imported

The extension ships inside Aureon. **Browsers** shows where it's loaded and sets it up where it isn't. Aureon is
its companion on this PC (screen brightness, Tor, local AI) unless the noah desktop app already is. The parts that
make sense for the whole computer are rebuilt natively: the tracker list (system-wide DNS), the YARA rules, the
220 Gitleaks secret patterns (clipboard guard and folder scan), lossless photo metadata cleaning, the k-anonymity
password breach check, the screen-recording extension watch, and noah's looks as Studio themes.

## Phones (any brand)

- **Android** (Pixel, Samsung, Xiaomi, OnePlus, Motorola, carrier phones…): turn on USB debugging and tap *Allow*;
  Aureon scans automatically. Every package by company, apps with no icon, device admins, accessibility and
  notification access, sideloads, explained preloads (carrier analytics, Digital Turbine, ironSource, Meta, Google
  SafetyCore…), and when each app last used the camera, mic, location, screen recording, SMS or call log.
- **iPhone**: with libimobiledevice, the device, every app and any enterprise/developer profiles. A deep spyware
  check needs an encrypted backup plus MVT ([docs/PHONE.md](../docs/PHONE.md)).
- **Phone link**: a view-only copy of the dashboard on your home WiFi, behind its own long key.

## Studio

19 looks in groups: Yours (Ember), Cozy (Hearth, Gruvbox, Catppuccin), Nature (Moss, Everforest, Pasture),
Moody (Kanagawa, Rosé Pine, Tokyo Night, Rain, Nord), noah.shield's photos (Meteor, Halo, Lights, Sea, Rings,
Glitch) and Paper for daytime. A look sets the wallpaper at your screen size, light/dark, accent, taskbar, the
desktop clock and **aureon.defender's own colours**. Also: brightness, 12/24-hour clock, seconds, date format, your
own wallpaper and fonts. **Undo Studio changes** restores exactly what you had. Nothing needs admin rights.

## Commands

```
aureon.defender                       open the dashboard
aureon.defender scan <path>           scan now (exit code 3 when something is found)
aureon.defender status | update
aureon.defender devices list | sweep | clear
aureon.defender leaks list | fix <id>
aureon.defender studio list | preset Moss | restore
aureon.defender quarantine list | restore <id> | delete <id>
```

## Build and test

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1     # 81 tests, then the program folder + zip + sha256
cd windows; python -m unittest discover -s tests -v            # tests only
```

Why Microsoft Defender stays underneath, and the roadmap: [docs/defender/BRANCHES.md](../docs/defender/BRANCHES.md).
