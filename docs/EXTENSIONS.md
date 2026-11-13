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
10. **USB-HID injection guard** - host agent that alerts when a new keyboard device appears and
    types faster than a human (defends against Rubber-Ducky/pico-ducky style attacks).
11. **Compute pooling** - k3s across Node(s) and laptops to push heavy jobs (transcoding,
    AI, builds) off the battery-powered device.
12. **Secret hygiene** - gitleaks + trufflehog as pre-commit hooks on every repo you own.

## Roadmap
- [ ] `aureon apply <profile>` that runs the scripts step by step with confirmation
- [ ] Wazuh manager + AI-summary pipeline in `deploy/soc/`
- [ ] `deploy/cloud/` and `deploy/ai/` compose files
- [ ] USB-HID injection guard in `aureon/hidguard.py`
- [ ] Aureon Key v2: TinyUSB C firmware (HID + CDC), FIDO2 research
- [ ] Ansible playbooks mirroring `scripts/linux/`
