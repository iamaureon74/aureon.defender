# Beyond the brief - extensions

Things the catalog makes possible that weren't in the original list.

1. **Off-grid communication** - Meshtastic LoRa radios + Reticulum/NomadNet: encrypted text
   between phones and laptops with no cell network or internet (outages, travel, protests).
2. **Radio-environment awareness** - RTL-SDR + kalibrate-rtl/gr-gsm to inventory nearby cell
   towers and flag anomalies; rtl_433 to find unknown transmitters (hidden sensors, trackers);
   Kismet for rogue access points and deauth floods.
3. **Offline knowledge** - Kiwix serves Wikipedia, Stack Exchange and repair manuals from the
   Node or the phone with no connection.
4. **Out-of-band rescue** - PiKVM/TinyPilot attached to a laptop gives BIOS-level remote control
   to recover a machine that won't boot.
5. **AI security analyst** - feed Wazuh/CrowdSec/Suricata alerts into a local LLM
   (Ollama + n8n) to get plain-language summaries and suggested actions without sending logs
   to any cloud.
6. **Camera-based presence** - Frigate + YOLO on the Node: alert when someone is at your desk
   while you're away; combine with the Aureon Key walk-away lock.
7. **Self-hosted identity** - Vaultwarden + headscale + Caddy: your own password manager,
   VPN control plane and HTTPS for every device.
8. **Reproducible machines** - NixOS + nixos-hardware or Ansible playbooks so a lost/stolen laptop
   can be rebuilt identically in an hour; rclone crypt + Syncthing for the data.
9. **Hardware token** - extend the Aureon Key into a FIDO2/U2F authenticator (TinyUSB HID +
   RP2350 secure boot/OTP). Open implementations exist outside this catalog (e.g. pico-fido).
10. **USB-HID injection guard** - host agent that alerts (and can lock the screen) the moment an untrusted keyboard device appears
    (defends against Rubber-Ducky/pico-ducky style attacks; typing-speed analysis is future work).
11. **Compute pooling** - k3s across Node(s) and laptops to push heavy jobs (transcoding,
    AI, builds) off the battery-powered device.
12. **Secret hygiene** - gitleaks + trufflehog as pre-commit hooks on every repo you own.

## Status
Built and tested in this repo:
- Off-grid communication: `deploy/offgrid` (Kiwix, Reticulum, Meshtastic bridge), `aureon mesh`
- Radio-environment awareness: `aureon rf wifi|cell|gsm`
- Offline knowledge: Kiwix in `deploy/offgrid`
- Out-of-band rescue: `aureon rescue` (PiKVM API)
- AI security analyst: `aureon analyst` + `deploy/ai` (hourly), relayed to the Key and the LoRa mesh
- USB-HID injection guard: `aureon hidguard`
- Organism model: `aureon body`

## Roadmap
- [ ] `aureon apply <profile>` running each plan step with confirmation
- [ ] Wazuh manager in `deploy/soc/` feeding the analyst
- [ ] Frigate camera presence (Eyes organ) + walk-away lock fusion
- [ ] Aureon Key v3: TinyUSB C firmware, inline USB firewall via Pico-PIO-USB, FIDO2 research
- [ ] Ansible playbooks mirroring `scripts/linux/`
- [ ] Offline voice pipeline (Wyoming: openWakeWord -> whisper.cpp -> LLM -> Piper)
