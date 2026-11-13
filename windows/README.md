# aureon.defender

24/7 protection, a hidden-software radar for laptops and phones, and a desktop studio for Windows, built from the
Aureon capability map (the best of 790 open-source projects). A 21 MB download, no account, works offline.

## Install

1. Download [`release/aureon.defender-0.1.0-win64.zip`](release/) and check it against the `.sha256` file next to it.
2. Unzip it anywhere, open the `aureon.defender` folder and run `aureon.defender.exe install`, then approve the
   administrator prompt. SmartScreen will warn because the app isn't code-signed yet: *More info → Run anyway*.
3. The dashboard opens. Aureon now starts with Windows and keeps running; the unzipped folder can be deleted.

It ships as a normal program folder, not a single self-extracting exe. Antivirus machine-learning models routinely
mis-flag unsigned single-file Python exes (Defender called our first build `Trojan:Win32/Bearfoos.B!ml`). The folder
build scans clean with Microsoft Defender.

Try it without installing: `aureon.defender.exe run` (protects only while it's open).
Remove: *Settings → Apps → Aureon Defender → Uninstall*, or `aureon.defender.exe uninstall [--purge]`.

## What runs 24/7

| Sensor | Every | What it catches |
|---|---|---|
| Real-time files | 2 s | New downloads, Desktop, Temp and Startup files: reputation, delivery tricks, YARA, Defender engine |
| Ransomware tripwires | 5 s | Hidden decoy documents; any change names the busiest writers (optional auto-freeze) |
| USB keyboard guard | 2 s | Fake-keyboard USB sticks (optionally locks the screen) |
| Network watch | 15 s | Connections to known botnet servers, new open ports, hosts-file and DNS hijacks |
| WiFi watch | 60 s | Evil-twin and downgraded copies of trusted networks |
| Autostart watch | 5 min | New Run keys, Winlogon changes, Startup items, scheduled tasks, services |
| Security settings | 1 h | Firewall, Defender, Secure Boot, BitLocker, SMBv1, RDP, open ports |
| Threat feeds | 6 h (online) | MalwareBazaar hashes, Feodo C2 IPs, URLhaus domains, Defender signatures |
| Daily report | 24 h | Plain-English summary, written by a local AI model if Ollama is running |

| Hidden-software radar | 30 min | Every program (incl. ones hidden from Settings › Apps), service, task, autostart and browser extension, by company; vendor telemetry; known monitoring/stalkerware; Recall snapshots; and Windows' own record of which app used your camera, mic, location or screen |

Offline, everything above keeps working from local rules and the last cached feeds.

## Phones (any brand)

Plug in a phone and Aureon scans it automatically.

- **Android** (Pixel, Samsung, Xiaomi, OnePlus, Motorola, carrier phones…): turn on USB debugging and tap *Allow*.
  You get every package grouped by company, including disabled ones and leftovers. Apps with no launcher icon
  are flagged, as are device admins, accessibility and notification-listener apps, and anything sideloaded.
  Known preloads (carrier analytics, Digital Turbine, ironSource Aura, Meta preinstalls, Adups, Carrier IQ…) are
  explained, and each app shows when it last used the camera, mic, location, screen recording, SMS or call log.
  The same code also runs inside Termux on the phone itself.
- **iPhone**: with libimobiledevice installed you get the device details, every app and any enterprise/developer
  provisioning profiles. A deep spyware check needs an encrypted backup plus MVT ([docs/PHONE.md](../docs/PHONE.md)).
  Apple doesn't expose more over USB.
- **Open Aureon on your phone**: Phones › *Phone link* serves a view-only copy of the dashboard on your home WiFi,
  behind its own long key.

## Studio

Six one-click looks (Aurora, Obsidian, Dusk, Paper, Lagoon, Terminal). Each sets the light/dark mode, the accent
colour, a wallpaper generated at your screen size, the taskbar layout and a desktop clock widget. You can also set
each piece yourself: 12/24-hour clock, seconds on the taskbar, date format, your own wallpaper, per-user fonts,
and the widget's font, size, colour and position. **Undo all Studio changes** puts back exactly what you had.
Nothing needs admin rights.

## Commands

```
aureon.defender                 open the dashboard
aureon.defender scan <path>     scan now (exit code 3 when something is found)
aureon.defender status | update
aureon.defender studio list | preset Aurora | restore
aureon.defender quarantine list | restore <id> | delete <id>
```

## Build and test

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1     # runs the tests, then builds dist\aureon.defender.exe
cd windows; python -m unittest discover -s tests -v            # tests only
```

Why Microsoft Defender stays underneath, and the roadmap: [docs/defender/BRANCHES.md](../docs/defender/BRANCHES.md).
