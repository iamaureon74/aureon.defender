# Aureon Hardware

Security, freedom and speed for **laptops and phones**, built by combining the best of the
790 open-source projects in [shep95/rasberry-pi](https://github.com/shep95/rasberry-pi).

Every one of the 790 was reviewed ([docs/CATALOG.md](docs/CATALOG.md)); **206 were picked** and
pinned here as submodules under `upstream/<layer>/`, at the same upstream commits.

## The four pieces

| Piece | What it is |
|---|---|
| **Aureon Agent** (`aureon/`, `scripts/`) | Cross-platform CLI: posture audit, per-device plans, hardening and performance scripts for Linux, Windows, macOS, Android (Termux) |
| **Aureon Node** (`deploy/shield/`) | A Pi 5 or mini-PC that becomes your private gateway: WireGuard + AdGuard + unbound + CrowdSec + Suricata + OpenCanary + Netdata, plus optional private cloud and local AI |
| **Aureon Mobile** (`docs/PHONE.md`) | Phone protection: encrypted DNS and always-on VPN to the Node, MVT spyware checks, PiRogue traffic inspection, Termux toolbox |
| **Aureon Key** (`key/`) | Raspberry Pi Pico companion: panic button, tamper switch, walk-away lock |

How they fit together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). What goes past the
original brief (off-grid mesh, IMSI-catcher awareness, offline knowledge, AI analyst...):
[docs/EXTENSIONS.md](docs/EXTENSIONS.md).

## Quick start

```bash
git clone https://github.com/shep95/aureon-hardware && cd aureon-hardware
python -m aureon audit                 # read-only security/perf score of this machine
python -m aureon profiles              # laptop-linux, laptop-windows, phone-android, phone-ios, node, lab
python -m aureon plan laptop-windows   # ordered steps for your device
python -m aureon components --layer defend --platform android
python -m aureon fetch defend          # pull pinned source for a layer (shallow)
```

Hardening (dry-run / read-only unless you opt in):

```bash
./scripts/linux/harden.sh                      # show plan
sudo ./scripts/linux/harden.sh --apply all
sudo ./scripts/linux/perf.sh --apply
powershell -ExecutionPolicy Bypass -File scripts\windows\harden.ps1   # add -Apply from an elevated shell
```

Node:

```bash
cd deploy/shield && cp .env.example .env && docker compose up -d
```

Aureon Key: flash MicroPython to a Pico, copy `key/firmware/main.py`, wire a button to GP15 and a
reed switch to GP14, then `pip install pyserial && python -m aureon.keyagent --port COM5 --dry-run`.

## Layout

```
aureon/            CLI: audit, profiles, plan, components, fetch, keyagent
scripts/           linux/ windows/ android-termux/
deploy/shield/     Node gateway compose stack
key/firmware/      Pico firmware
upstream/<layer>/  206 pinned upstream projects (git submodules, not downloaded by default)
stack.json         machine-readable component manifest
tools/             picks.py (the selection) + build_catalog.py (regenerates manifest/catalog/pins)
```

To change the selection: edit `tools/picks.py`, then
`python tools/build_catalog.py ../rasberry-pi --pin`.

## Ground rules

- Each upstream project keeps its own license.
- The `audit` layer (scanners, WiFi/password auditing, OSINT) is for your own systems or
  authorized engagements only, and no profile installs it automatically.
- Scripts default to dry-run / read-only. Read them before using `--apply` / `-Apply`.
