# Aureon Hardware

One system for **laptops and phones** that makes them safer, freer, faster and more capable. It's built by
reading all **790** open-source projects in [shep95/rasberry-pi](https://github.com/shep95/rasberry-pi),
taking each one's best capability, and combining them into **53 Aureon capabilities** organised as
**20 organs** that depend on each other, like a body.

- **[windows/](windows/README.md): aureon.defender**, a one-exe Windows app that runs the laptop-side organs 24/7 (protection engine, dashboard, Studio looks and desktop widget)
- [docs/CAPABILITIES.md](docs/CAPABILITIES.md): all 790 projects, the best capability taken from each, and the fused Aureon capability it feeds
- [docs/ORGANISM.md](docs/ORGANISM.md): the 20 organs, what each needs, and what fails if it fails
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how Agent, Node, Mobile and Key fit together
- [docs/CATALOG.md](docs/CATALOG.md): why each project was or wasn't pinned (215 pinned under `upstream/`)
- [docs/PHONE.md](docs/PHONE.md): phone protection steps, and [docs/EXTENSIONS.md](docs/EXTENSIONS.md)

## The organism

| Organ | Job | Built here |
|---|---|---|
| Skin | Filtered DNS + firewall keep most threats out | `deploy/shield`, harden scripts |
| Circulatory system | WireGuard/mesh carry traffic between phone, laptop, Node | `deploy/shield` wg-easy |
| Immune system | IDS/IPS, EDR, tripwires, phone spyware checks | `deploy/shield`, `aureon audit` |
| Nervous system | Metrics, logs and alerts from every sensor | Netdata, `aureon audit` |
| Brain | Local LLM security analyst + private assistant | `deploy/ai`, `aureon analyst` |
| Reflexes | Instant lock with no AI in the loop | `key/firmware`, `aureon hidguard`, `aureon.keyagent` |
| Ears | Rogue WiFi and fake cell-tower (IMSI catcher) watch | `aureon rf` |
| Hands | Below-OS rescue of a laptop that won't boot | `aureon rescue` (PiKVM) |
| Voice | Off-grid encrypted texting over LoRa | `deploy/offgrid`, `aureon mesh` |
| Memory | Photos, files, passwords on your own hardware | `deploy/cloud` |
| Digestive system | Offline Wikipedia, manuals and courses | `deploy/offgrid` Kiwix |
| ...and 9 more | DNA, Skeleton, Heart, Lungs, Liver, Vaccination, Eyes, Endocrine, Muscles | see docs/ORGANISM.md |

## Commands

```bash
python -m aureon body                      # live vitals of every organ on this machine (+ Node if AUREON_NODE set)
python -m aureon body --fail blood         # what breaks if the VPN layer dies
python -m aureon caps                      # the 53 fused capabilities
python -m aureon caps wireless-watch       # one capability + the projects it came from
python -m aureon audit                     # read-only security/perf score
python -m aureon plan laptop-windows       # step-by-step plan: laptop-linux, laptop-windows, phone-android, phone-ios, node, lab
python -m aureon rf wifi --learn ; python -m aureon rf wifi          # evil-twin / downgrade detection
python -m aureon rf cell                   # (Android/Termux) 2G-downgrade / new-cell / new-LAC heuristics
python -m aureon rf gsm --kal kal.txt      # compare a kalibrate-rtl GSM survey
python -m aureon analyst --suricata eve.json --canary canary.log --audit --since 24h --out report.md
python -m aureon hidguard --learn ; python -m aureon hidguard --lock  # BadUSB keystroke-injection guard
python -m aureon rescue status|power on|screenshot|type ...|key Delete|iso rescue.iso   # PiKVM
python -m aureon mesh send --port COM7 "on my way"                   # Meshtastic LoRa
python -m aureon.keyagent --port COM5 --alert-report report.md       # Aureon Key host agent
python -m aureon fetch defend              # pull pinned upstream source for a layer
```

## Node stacks (Pi 5 8GB or any mini-PC)

```bash
cd deploy/shield  && cp .env.example .env && docker compose up -d     # Skin, Blood, Immune, Nerves
cd deploy/cloud   && cp .env.example .env && docker compose up -d     # Memory
cd deploy/ai      && docker compose up -d                              # Brain (+ hourly analyst)
cd deploy/offgrid && docker compose up -d                              # Voice + Digestion
```

## Hardening scripts (dry-run / read-only unless you opt in)

```bash
./scripts/linux/harden.sh ; sudo ./scripts/linux/harden.sh --apply all
sudo ./scripts/linux/perf.sh --apply
powershell -ExecutionPolicy Bypass -File scripts\windows\harden.ps1   # -Apply from an elevated shell
bash scripts/android-termux/setup.sh                                  # inside Termux
```

## Tests

```bash
pip install pyyaml
python -m unittest discover -s tests -v
```

53 tests cover:
- **Coverage:** the capability map accounts for all 790 projects, and the pins match `stack.json`.
- **Organism:** the organ graph is valid, with no cycles and every capability in exactly one organ.
- **Detectors:** WiFi, cell-tower and GSM detection with real `netsh`, `nmcli` and `kal` output formats.
- **Analyst:** every alert source parser, plus the analyst against fake Ollama and OpenAI-compatible servers.
- **Rescue:** the PiKVM client against a fake KVM API, including streamed ISO upload and authentication.
- **Reflexes:** Key agent lock logic, the HID guard, and a simulated run of the Pico firmware.
- **Deploy stacks:** consistency of every compose file.
- **Scripts:** the shell scripts in dry-run, and parsing of the PowerShell script.

CI runs the suite on Ubuntu and Windows, plus `docker compose config` and shellcheck.

## Ground rules

- Each upstream project keeps its own license. Submodules are not downloaded unless you `aureon fetch`.
- The audit/"vaccination" organ (scanners, WiFi/password auditing, OSINT) is for systems you own or are
  authorized to test. No profile installs it automatically.
- RF tools only listen. Transmitter projects in the catalog need an amateur licence and are not wired in.
- RF and cell-tower alerts are heuristics: a hit means "look closer", not proof.

To change the selection: edit `tools/picks.py` / `tools/capmap_*.py`, then
`python tools/build_catalog.py ../rasberry-pi --pin && python tools/build_organism_doc.py`.
