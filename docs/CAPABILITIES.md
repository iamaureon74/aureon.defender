# Aureon capability map

Each of the 790 projects in shep95/rasberry-pi was read for its single best capability. Those capabilities are fused into **53 Aureon capabilities** across 12 domains. This is the one system: `python -m aureon caps` browses it, `python -m aureon caps show <id>` explains one, and the *Realised in* line says where it lives in this repo.

Status words in *Realised in*: **built** = Aureon code in this repo, deploy/* = ready compose stack, profile = in a device plan, catalog = pinned or listed and fetchable, not yet wired in.

| Domain | Capabilities | Projects |
|---|---|---|
| SYSTEM | Aureon OS image factory, Firmware, boot & secure-boot chain, Appliance OS personalities, Alternative & research kernels | 122 |
| LEARN | Platform knowledge base, Learning & creating | 32 |
| HARDWARE | Camera & vision capture, GPIO, sensors & displays, Aureon Key microcontroller platform | 78 |
| PROTECT | Network detection & prevention, Endpoint protection (EDR + AV + app firewall), Deception & tripwires, Phone spyware & traffic forensics, Forensics & reverse engineering, Secrets & credentials hygiene, Self-audit lab (authorized use only), WiFi & RF strength testing (own networks), Physical/USB/NFC attack surface, Personal exposure (OSINT on yourself) | 114 |
| RADIO | Rogue WiFi & fake cell-tower watch, Off-grid encrypted communication, Software-defined radio core, Aviation, weather & space reception, Amateur radio & emergency comms | 56 |
| NETWORK | Private filtered DNS, VPN & mesh overlay, Anonymity, Access point & connectivity, Sync, sharing & transfer, Sovereign money nodes | 46 |
| FREEDOM | Personal cloud, Own communications, Web serving & reverse proxy, Databases, Business apps, Own dev platform | 45 |
| PERFORM | Remote access & rescue, Dashboards, Observability & health, Containers, VMs & clusters, Run any software anywhere, Fast, light desktop & UI, Game & desktop streaming | 88 |
| INTELLIGENCE | Local LLM brain, Offline voice, Vision & presence, AI acceleration, Robotics & drones | 78 |
| HOME | Device automation & presence | 30 |
| MEDIA | Media, music & cameras, Gaming & emulation | 64 |
| MAKE | 3D printing, CNC & laser, Astronomy | 37 |

## SYSTEM

### Aureon OS image factory (`system.image`)

**Fused capability:** One pipeline that builds signed, minimal, reproducible images for Node, laptop and phone: pi-gen stages + Buildroot minimalism + Yocto layers + Nix reproducibility + first-boot automation + safe flashing.

**Realised in:** tools/ (planned: images/), profile node step 1

| Project | Best capability taken | Pinned |
|---|---|---|
| [Drewsif/PiShrink](https://github.com/Drewsif/PiShrink) | shrink images to minimum size, auto-expand on boot | yes |
| [archlinuxarm/PKGBUILDs](https://github.com/archlinuxarm/PKGBUILDs) | Arch Linux ARM package recipes |  |
| [raspberrypi/pi-gen-micro](https://github.com/raspberrypi/pi-gen-micro) | tiny initramfs-style images |  |
| [raspberrypi/rpi-image-gen](https://github.com/raspberrypi/rpi-image-gen) | declarative YAML image layers |  |
| [RPi-Distro/pi-gen](https://github.com/RPi-Distro/pi-gen) | staged Debian image build |  |
| [guysoft/CustomPiOS](https://github.com/guysoft/CustomPiOS) | distro-from-modules framework |  |
| [buildroot/buildroot](https://github.com/buildroot/buildroot) | minimal read-only embedded rootfs | yes |
| [agherzan/meta-raspberrypi](https://github.com/agherzan/meta-raspberrypi) | Yocto BSP layer |  |
| [balena-os/meta-balena](https://github.com/balena-os/meta-balena) | OTA-updatable container OS layer |  |
| [balena-os/balena-raspberrypi](https://github.com/balena-os/balena-raspberrypi) | device-specific Yocto integration |  |
| [armbian/build](https://github.com/armbian/build) | one build system for hundreds of ARM boards | yes |
| [void-linux/void-mklive](https://github.com/void-linux/void-mklive) | live/installer ISO creation | yes |
| [void-linux/void-packages](https://github.com/void-linux/void-packages) | clean cross-compiling package templates |  |
| [NixOS/nixos-hardware](https://github.com/NixOS/nixos-hardware) | per-device hardware quirks as code | yes |
| [nvmd/nixos-raspberrypi](https://github.com/nvmd/nixos-raspberrypi) | Nix flakes for Pi boards |  |
| [hypriot/image-builder-rpi](https://github.com/hypriot/image-builder-rpi) | container-ready image recipe |  |
| [TOLDOTECHNIK/buildroot-webkit](https://github.com/TOLDOTECHNIK/buildroot-webkit) | kiosk browser appliance image |  |
| [sakaki-/gentoo-on-rpi-64bit](https://github.com/sakaki-/gentoo-on-rpi-64bit) | source-optimised 64-bit userland |  |
| [manjaro-arm/rpi4-images](https://github.com/manjaro-arm/rpi4-images) | rolling-release ARM images |  |
| [android-rpi/local_manifests](https://github.com/android-rpi/local_manifests) | AOSP device manifests | yes |
| [lineage-rpi/android_local_manifest](https://github.com/lineage-rpi/android_local_manifest) | LineageOS device tree layout | yes |
| [openfyde/overlay-rpi4-openfyde](https://github.com/openfyde/overlay-rpi4-openfyde) | ChromiumOS board overlay |  |
| [FydeOS/chromium_os-raspberry_pi](https://github.com/FydeOS/chromium_os-raspberry_pi) | verified-boot ChromiumOS build | yes |
| [nmcclain/raspberian-firstboot](https://github.com/nmcclain/raspberian-firstboot) | run-once first-boot script hook |  |
| [davidferguson/pibakery](https://github.com/davidferguson/pibakery) | visual block-based image customisation |  |
| [seamusdemora/RonR-RPi-image-utils](https://github.com/seamusdemora/RonR-RPi-image-utils) | shrink/backup running images |  |
| [raspberrypi/rpi-imager](https://github.com/raspberrypi/rpi-imager) | verified image download + OS customisation |  |
| [balena-io/etcher](https://github.com/balena-io/etcher) | validated flashing that refuses system disks | yes |
| [hypriot/flash](https://github.com/hypriot/flash) | one-command flash with cloud-init |  |
| [raspberrypi/noobs](https://github.com/raspberrypi/noobs) | multi-OS boot menu installer |  |
| [raspberrypi/scriptexecutor](https://github.com/raspberrypi/scriptexecutor) | scripted provisioning during boot |  |

### Firmware, boot & secure-boot chain (`system.firmware`)

**Fused capability:** A verified boot chain: signed EEPROM/bootloader + UEFI for standard OSes + USB recovery + kernel/userland tooling, with key provisioning done once at the factory step.

**Realised in:** profile node; catalog base layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [raspberrypi/firmware](https://github.com/raspberrypi/firmware) | GPU firmware + boot blobs |  |
| [raspberrypi/rpi-firmware](https://github.com/raspberrypi/rpi-firmware) | packaged firmware updates |  |
| [RPi-Distro/firmware](https://github.com/RPi-Distro/firmware) | Debian-packaged firmware |  |
| [raspberrypi/rpi-eeprom](https://github.com/raspberrypi/rpi-eeprom) | updatable signed bootloader EEPROM |  |
| [raspberrypi/rpi-sb-provisioner](https://github.com/raspberrypi/rpi-sb-provisioner) | secure-boot key provisioning at scale | yes |
| [raspberrypi/usbboot](https://github.com/raspberrypi/usbboot) | USB device boot / recovery | yes |
| [raspberrypi/rpi-update](https://github.com/raspberrypi/rpi-update) | bleeding-edge kernel/firmware fetch |  |
| [pftf/RPi3](https://github.com/pftf/RPi3) | UEFI firmware for Pi 3 |  |
| [pftf/RPi4](https://github.com/pftf/RPi4) | UEFI firmware for Pi 4 (boots generic ARM distros) |  |
| [worproject/rpi5-uefi](https://github.com/worproject/rpi5-uefi) | UEFI firmware for Pi 5 | yes |
| [raspberrypi/linux](https://github.com/raspberrypi/linux) | maintained ARM kernel with board drivers |  |
| [raspberrypi/userland](https://github.com/raspberrypi/userland) | VideoCore userspace libraries |  |
| [raspberrypi/utils](https://github.com/raspberrypi/utils) | vcgencmd/pinctrl/eeprom tools |  |
| [raspberrypi/tools](https://github.com/raspberrypi/tools) | cross-compilation toolchains |  |
| [RPi-Distro/raspberrypi-sys-mods](https://github.com/RPi-Distro/raspberrypi-sys-mods) | system tweaks/udev rules |  |
| [RPi-Distro/raspi-config](https://github.com/RPi-Distro/raspi-config) | one-screen system configuration |  |
| [raspberrypi/rc_gui](https://github.com/raspberrypi/rc_gui) | GUI system configuration |  |
| [raspberrypi/rpi-keyboard-config](https://github.com/raspberrypi/rpi-keyboard-config) | keyboard firmware configuration |  |
| [raspberrypi/hats](https://github.com/raspberrypi/hats) | HAT EEPROM identification spec |  |
| [raspberrypi/pico-bootrom-rp2040](https://github.com/raspberrypi/pico-bootrom-rp2040) | RP2040 mask-ROM bootloader source |  |
| [raspberrypi/pico-bootrom-rp2350](https://github.com/raspberrypi/pico-bootrom-rp2350) | RP2350 secure-boot ROM source |  |

### Appliance OS personalities (`system.appliance`)

**Fused capability:** Aureon Node can take any of these single-purpose personalities (router, NAS, media, home hub, node box) while keeping the Aureon shield underneath; the best idea taken from each is the one-click appliance UX.

**Realised in:** deploy/* stacks; profile node

| Project | Best capability taken | Pinned |
|---|---|---|
| [Itai-Nelken/PiApps-terminal_bash-edition](https://github.com/Itai-Nelken/PiApps-terminal_bash-edition) | terminal app store |  |
| [jmcerrejon/PiKISS](https://github.com/jmcerrejon/PiKISS) | one-menu installer for hundreds of apps |  |
| [jiangcuo/Proxmox-Port](https://github.com/jiangcuo/Proxmox-Port) | Proxmox VE ported to ARM64 |  |
| [MichaIng/DietPi](https://github.com/MichaIng/DietPi) | optimised minimal Debian + software menu | yes |
| [openwrt/openwrt](https://github.com/openwrt/openwrt) | router firmware with package system | yes |
| [home-assistant/operating-system](https://github.com/home-assistant/operating-system) | appliance OS with supervisor + OTA |  |
| [LibreELEC/LibreELEC.tv](https://github.com/LibreELEC/LibreELEC.tv) | just-enough-OS for media |  |
| [osmc/osmc](https://github.com/osmc/osmc) | polished media appliance |  |
| [libretro/Lakka-LibreELEC](https://github.com/libretro/Lakka-LibreELEC) | console-like gaming appliance |  |
| [batocera-linux/batocera.linux](https://github.com/batocera-linux/batocera.linux) | plug-and-play retro gaming OS |  |
| [RetroPie/RetroPie-Setup](https://github.com/RetroPie/RetroPie-Setup) | script-built emulation station |  |
| [moode-player/moode](https://github.com/moode-player/moode) | audiophile player appliance |  |
| [volumio/Build](https://github.com/volumio/Build) | music appliance image build |  |
| [volumio/volumio3-os](https://github.com/volumio/volumio3-os) | music OS base |  |
| [hifiberry/hifiberry-os](https://github.com/hifiberry/hifiberry-os) | DSP audio appliance |  |
| [motioneye-project/motioneyeos](https://github.com/motioneye-project/motioneyeos) | camera NVR appliance |  |
| [guysoft/OctoPi](https://github.com/guysoft/OctoPi) | 3D-printer host appliance |  |
| [mainsail-crew/MainsailOS](https://github.com/mainsail-crew/MainsailOS) | Klipper printer appliance |  |
| [guysoft/FullPageOS](https://github.com/guysoft/FullPageOS) | boot-to-fullscreen-browser kiosk |  |
| [getumbrel/umbrel](https://github.com/getumbrel/umbrel) | home-server app store OS |  |
| [IceWhaleTech/CasaOS](https://github.com/IceWhaleTech/CasaOS) | friendly personal-cloud dashboard |  |
| [IceWhaleTech/ZimaOS](https://github.com/IceWhaleTech/ZimaOS) | NAS-focused personal cloud OS |  |
| [YunoHost/yunohost](https://github.com/YunoHost/yunohost) | self-hosting OS with SSO and app catalog |  |
| [nextcloud/nextcloudpi](https://github.com/nextcloud/nextcloudpi) | Nextcloud appliance with auto-config |  |
| [openmediavault/openmediavault](https://github.com/openmediavault/openmediavault) | NAS web management |  |
| [OpenMediaVault-Plugin-Developers/installScript](https://github.com/OpenMediaVault-Plugin-Developers/installScript) | OMV install on existing OS |  |
| [openhab/openhabian](https://github.com/openhab/openhabian) | home-automation appliance |  |
| [homebridge/homebridge-raspbian-image](https://github.com/homebridge/homebridge-raspbian-image) | HomeKit bridge appliance |  |
| [colloqi/piSignage](https://github.com/colloqi/piSignage) | digital-signage player |  |
| [colloqi/pisignage-server](https://github.com/colloqi/pisignage-server) | signage fleet server |  |
| [Screenly/Anthias](https://github.com/Screenly/Anthias) | open digital signage |  |
| [Start9Labs/start-os](https://github.com/Start9Labs/start-os) | sovereign personal server OS |  |
| [Start9Labs/embassy-os](https://github.com/Start9Labs/embassy-os) | earlier Start9 server OS |  |
| [mynodebtc/mynode](https://github.com/mynodebtc/mynode) | Bitcoin/Lightning node appliance |  |
| [raspiblitz/raspiblitz](https://github.com/raspiblitz/raspiblitz) | Lightning node appliance |  |
| [rootzoll/raspiblitz](https://github.com/rootzoll/raspiblitz) | Lightning node (original repo) |  |
| [raspibolt/raspibolt](https://github.com/raspibolt/raspibolt) | hand-built hardened Bitcoin node guide |  |
| [PiRogueToolSuite/pirogue-os](https://github.com/PiRogueToolSuite/pirogue-os) | mobile-forensics appliance | yes |
| [PiRogueToolSuite/deb-packages](https://github.com/PiRogueToolSuite/deb-packages) | PiRogue packaging |  |
| [BlackArch/blackarch](https://github.com/BlackArch/blackarch) | 2800+ security tools repo |  |
| [jiangcuo/pxvirt](https://github.com/jiangcuo/pxvirt) | Proxmox VE on ARM |  |
| [pimox/pimox7](https://github.com/pimox/pimox7) | Proxmox 7 on Pi |  |
| [evilsocket/pwnagotchi](https://github.com/evilsocket/pwnagotchi) | autonomous WiFi-learning pet (audit) |  |
| [jayofelony/pwnagotchi](https://github.com/jayofelony/pwnagotchi) | maintained pwnagotchi fork |  |
| [infinition/Bjorn](https://github.com/infinition/Bjorn) | autonomous network audit appliance |  |
| [AllskyTeam/allsky](https://github.com/AllskyTeam/allsky) | all-sky camera appliance |  |
| [thomasjacquin/allsky](https://github.com/thomasjacquin/allsky) | all-sky camera (original) |  |
| [rlancaste/AstroPi3](https://github.com/rlancaste/AstroPi3) | astrophotography setup script |  |
| [billw2/rpi-clone](https://github.com/billw2/rpi-clone) | live clone to a new disk | yes |
| [framps/raspiBackup](https://github.com/framps/raspiBackup) | scheduled full-system backups | yes |
| [Botspot/pi-apps](https://github.com/Botspot/pi-apps) | curated ARM app store | yes |

### Alternative & research kernels (`system.research-os`)

**Fused capability:** Ideas Aureon borrows for hardening: Plan 9 per-process namespaces, OpenBSD pledge/unveil minimalism, capability-style isolation, bare-metal tiny trusted computing bases for the Key.

**Realised in:** docs/ARCHITECTURE.md (design references); key/

| Project | Best capability taken | Pinned |
|---|---|---|
| [9front/9front](https://github.com/9front/9front) | per-process namespaces, everything-is-a-file |  |
| [plan9foundation/plan9](https://github.com/plan9foundation/plan9) | original Plan 9 distributed OS |  |
| [inferno-os/inferno-os](https://github.com/inferno-os/inferno-os) | portable VM-based distributed OS |  |
| [haiku/haiku](https://github.com/haiku/haiku) | responsive single-user desktop OS |  |
| [freebsd/freebsd-src](https://github.com/freebsd/freebsd-src) | jails + Capsicum capabilities |  |
| [NetBSD/src](https://github.com/NetBSD/src) | maximally portable BSD |  |
| [openbsd/src](https://github.com/openbsd/src) | pledge/unveil, secure-by-default |  |
| [rsta2/circle](https://github.com/rsta2/circle) | bare-metal C++ environment |  |
| [ultibohub/Core](https://github.com/ultibohub/Core) | bare-metal Pascal unikernel |  |
| [ultibohub/FPC](https://github.com/ultibohub/FPC) | Free Pascal for Ultibo |  |
| [RT-Thread/rt-thread](https://github.com/RT-Thread/rt-thread) | IoT RTOS with rich components |  |
| [rust-embedded/rust-raspberrypi-OS-tutorials](https://github.com/rust-embedded/rust-raspberrypi-OS-tutorials) | memory-safe kernel in Rust |  |
| [s-matyukevich/raspberry-pi-os](https://github.com/s-matyukevich/raspberry-pi-os) | Linux-like kernel teaching OS |  |
| [bztsrc/raspi3-tutorial](https://github.com/bztsrc/raspi3-tutorial) | bare-metal peripherals tutorial |  |
| [dwelch67/raspberrypi](https://github.com/dwelch67/raspberrypi) | bare-metal examples |  |
| [dwelch67/raspberrypi-three](https://github.com/dwelch67/raspberrypi-three) | bare-metal Pi 3 examples |  |
| [mrvn/RaspberryPi-baremetal](https://github.com/mrvn/RaspberryPi-baremetal) | minimal bare-metal kernel |  |
| [jncronin/rpi-boot](https://github.com/jncronin/rpi-boot) | multiboot-style loader |  |
| [ms-iot/samples](https://github.com/ms-iot/samples) | Windows IoT samples |  |

## LEARN

### Platform knowledge base (`system.knowledge`)

**Fused capability:** Searchable offline docs + known-issue trackers fed into the local AI (RAG) so the assistant answers hardware questions without the internet.

**Realised in:** deploy/offgrid kiwix + deploy/ai open-webui documents

| Project | Best capability taken | Pinned |
|---|---|---|
| [Gadgetoid/Pinout.xyz](https://github.com/Gadgetoid/Pinout.xyz) | interactive GPIO pinout reference |  |
| [pinout-xyz/Pinout.xyz](https://github.com/pinout-xyz/Pinout.xyz) | Pinout.xyz (current home) |  |
| [raspberrypi/documentation](https://github.com/raspberrypi/documentation) | official hardware/software documentation |  |
| [raspberrypi/bookworm-feedback](https://github.com/raspberrypi/bookworm-feedback) | known issues for Bookworm |  |
| [raspberrypi/trixie-feedback](https://github.com/raspberrypi/trixie-feedback) | known issues for Trixie |  |
| [raspberrypi/pico-feedback](https://github.com/raspberrypi/pico-feedback) | known Pico issues |  |

### Learning & creating (`learn.code`)

**Fused capability:** Teach and build on the platform: block coding, beginner IDEs, offline school content, office suite.

**Realised in:** catalog only (Kolibri pairs with offline Kiwix)

| Project | Best capability taken | Pinned |
|---|---|---|
| [arduino/arduino-cli](https://github.com/arduino/arduino-cli) | Arduino builds from CLI |  |
| [arduino/arduino-ide](https://github.com/arduino/arduino-ide) | Arduino IDE |  |
| [astro-pi/python-sense-emu](https://github.com/astro-pi/python-sense-emu) | Sense HAT emulator |  |
| [RPi-Distro/python-sense-emu](https://github.com/RPi-Distro/python-sense-emu) | packaged emulator |  |
| [fritzing/fritzing-app](https://github.com/fritzing/fritzing-app) | circuit design |  |
| [google/blockly](https://github.com/google/blockly) | block programming |  |
| [KDE/gcompris](https://github.com/KDE/gcompris) | kids education suite |  |
| [learningequality/kolibri](https://github.com/learningequality/kolibri) | offline learning platform | yes |
| [kiwix/kiwix-tools](https://github.com/kiwix/kiwix-tools) | offline Wikipedia server | yes |
| [kiwix/kiwix-hotspot](https://github.com/kiwix/kiwix-hotspot) | offline content hotspot | yes |
| [iiab/iiab](https://github.com/iiab/iiab) | Internet-in-a-Box offline library | yes |
| [LibreOffice/core](https://github.com/LibreOffice/core) | office suite |  |
| [lordmauve/pgzero](https://github.com/lordmauve/pgzero) | zero-boilerplate games |  |
| [martinohanlon/mcpi](https://github.com/martinohanlon/mcpi) | Minecraft Pi API |  |
| [martinohanlon/minecraft-stuff](https://github.com/martinohanlon/minecraft-stuff) | Minecraft helpers |  |
| [microsoft/pxt](https://github.com/microsoft/pxt) | MakeCode |  |
| [microsoft/pxt-microbit](https://github.com/microsoft/pxt-microbit) | MakeCode micro:bit |  |
| [mu-editor/mu](https://github.com/mu-editor/mu) | beginner Python editor |  |
| [processing/processing4](https://github.com/processing/processing4) | creative coding |  |
| [pygame-community/pygame-ce](https://github.com/pygame-community/pygame-ce) | games in Python |  |
| [pygame/pygame](https://github.com/pygame/pygame) | pygame |  |
| [RaspberryPiFoundation/editor-api](https://github.com/RaspberryPiFoundation/editor-api) | code editor backend |  |
| [RaspberryPiFoundation/editor-ui](https://github.com/RaspberryPiFoundation/editor-ui) | code editor UI |  |
| [scratchfoundation/scratch-desktop](https://github.com/scratchfoundation/scratch-desktop) | Scratch desktop |  |
| [scratchfoundation/scratch-gui](https://github.com/scratchfoundation/scratch-gui) | Scratch UI |  |
| [thonny/thonny](https://github.com/thonny/thonny) | beginner Python IDE |  |

## HARDWARE

### Camera & vision capture (`hardware.camera`)

**Fused capability:** Low-latency camera capture with hardware ISP feeding Aureon's AI presence detection and NVR.

**Realised in:** deploy (Frigate in EXTENSIONS); ai layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [raspberrypi/libcamera](https://github.com/raspberrypi/libcamera) | modern camera stack |  |
| [raspberrypi/libpisp](https://github.com/raspberrypi/libpisp) | Pi 5 ISP back-end |  |
| [raspberrypi/picamera2](https://github.com/raspberrypi/picamera2) | Python camera API |  |
| [raspberrypi/rpicam-apps](https://github.com/raspberrypi/rpicam-apps) | camera CLI apps |  |
| [raspberrypi/imx500-models](https://github.com/raspberrypi/imx500-models) | on-sensor AI camera models |  |

### GPIO, sensors & displays (`hardware.io`)

**Fused capability:** One HAL for buttons, tamper switches, sensors, LEDs and small screens on the Node and Key: libgpiod for correctness, gpiozero for simplicity, luma/e-paper for status screens.

**Realised in:** key/firmware (GP14/GP15); Node status display (planned)

| Project | Best capability taken | Pinned |
|---|---|---|
| [PiSupply/PiJuice](https://github.com/PiSupply/PiJuice) | battery UPS HAT - Node survives power cuts and shuts down cleanly | yes |
| [RaspberryPiFoundation/python-build-hat](https://github.com/RaspberryPiFoundation/python-build-hat) | LEGO motor/sensor HAT |  |
| [RPi-Distro/python-gpiozero](https://github.com/RPi-Distro/python-gpiozero) | packaged gpiozero |  |
| [raspberrypi/rpi-sense](https://github.com/raspberrypi/rpi-sense) | Sense HAT driver |  |
| [adafruit/Adafruit_Blinka](https://github.com/adafruit/Adafruit_Blinka) | CircuitPython APIs on Linux |  |
| [adafruit/Adafruit_CircuitPython_Bundle](https://github.com/adafruit/Adafruit_CircuitPython_Bundle) | hundreds of sensor drivers |  |
| [adafruit/Adafruit_CircuitPython_DHT](https://github.com/adafruit/Adafruit_CircuitPython_DHT) | DHT temperature/humidity |  |
| [adafruit/Adafruit_Python_DHT](https://github.com/adafruit/Adafruit_Python_DHT) | legacy DHT driver |  |
| [adafruit/Raspberry-Pi-Installer-Scripts](https://github.com/adafruit/Raspberry-Pi-Installer-Scripts) | one-line HAT installers |  |
| [astro-pi/python-sense-hat](https://github.com/astro-pi/python-sense-hat) | Sense HAT Python API |  |
| [brgl/libgpiod](https://github.com/brgl/libgpiod) | correct kernel GPIO character-device access |  |
| [dotnet/iot](https://github.com/dotnet/iot) | .NET device bindings |  |
| [fivdi/onoff](https://github.com/fivdi/onoff) | Node.js GPIO with interrupts |  |
| [fivdi/pigpio](https://github.com/fivdi/pigpio) | Node.js pigpio wrapper |  |
| [geerlingguy/raspberry-pi-pcie-devices](https://github.com/geerlingguy/raspberry-pi-pcie-devices) | tested PCIe device database |  |
| [golemparts/rppal](https://github.com/golemparts/rppal) | Rust peripheral access |  |
| [goodtft/LCD-show](https://github.com/goodtft/LCD-show) | SPI LCD drivers |  |
| [gpiozero/gpiozero](https://github.com/gpiozero/gpiozero) | simplest device-oriented GPIO API |  |
| [hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) | fast LED matrix driving |  |
| [jgarff/rpi_ws281x](https://github.com/jgarff/rpi_ws281x) | DMA-driven addressable LEDs |  |
| [joan2937/lg](https://github.com/joan2937/lg) | GPIO for Pi 5 (RP1) |  |
| [joan2937/pigpio](https://github.com/joan2937/pigpio) | hardware-timed PWM/servo/waveforms |  |
| [juj/fbcp-ili9341](https://github.com/juj/fbcp-ili9341) | high-fps SPI display driver |  |
| [nebrius/raspi-io](https://github.com/nebrius/raspi-io) | Johnny-Five IO plugin |  |
| [notro/fbtft](https://github.com/notro/fbtft) | framebuffer for small TFTs |  |
| [periph/host](https://github.com/periph/host) | Go peripheral drivers |  |
| [pi4j/pi4j-v2](https://github.com/pi4j/pi4j-v2) | Java GPIO |  |
| [pimoroni/bme280-python](https://github.com/pimoroni/bme280-python) | environment sensor |  |
| [pimoroni/displayhatmini-python](https://github.com/pimoroni/displayhatmini-python) | small IPS display HAT |  |
| [pimoroni/enviroplus-python](https://github.com/pimoroni/enviroplus-python) | air-quality monitoring |  |
| [pimoroni/fanshim-python](https://github.com/pimoroni/fanshim-python) | temperature-driven fan control |  |
| [pimoroni/inky](https://github.com/pimoroni/inky) | e-paper status displays |  |
| [pimoroni/st7789-python](https://github.com/pimoroni/st7789-python) | SPI LCD driver |  |
| [pimoroni/unicornhatmini-python](https://github.com/pimoroni/unicornhatmini-python) | RGB LED matrix |  |
| [rm-hull/luma.led_matrix](https://github.com/rm-hull/luma.led_matrix) | LED matrix text/graphics |  |
| [rm-hull/luma.oled](https://github.com/rm-hull/luma.oled) | OLED status displays |  |
| [rpi-ws281x/rpi-ws281x-python](https://github.com/rpi-ws281x/rpi-ws281x-python) | Python addressable LEDs |  |
| [rwaldron/johnny-five](https://github.com/rwaldron/johnny-five) | JS robotics/IoT framework |  |
| [stianeikeland/go-rpio](https://github.com/stianeikeland/go-rpio) | Go GPIO via /dev/mem |  |
| [tasanakorn/rpi-fbcp](https://github.com/tasanakorn/rpi-fbcp) | framebuffer mirroring |  |
| [Tieske/rpi-gpio](https://github.com/Tieske/rpi-gpio) | Lua GPIO |  |
| [waveshareteam/e-Paper](https://github.com/waveshareteam/e-Paper) | e-paper drivers |  |
| [WiringPi/WiringPi](https://github.com/WiringPi/WiringPi) | classic C GPIO library |  |

### Aureon Key microcontroller platform (`hardware.key`)

**Fused capability:** The Key firmware stack: pico-sdk + TinyUSB for USB identity, Embassy/rp-hal for memory-safe Rust, Zephyr for crypto/secure boot, MicroPython for rapid features, Wokwi for CI simulation.

**Realised in:** key/firmware/main.py (built); aureon/keyagent.py, aureon/hidguard.py (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [Wren6991/PicoDVI](https://github.com/Wren6991/PicoDVI) | DVI video out from RP2040 |  |
| [sekigon-gonnoc/Pico-PIO-USB](https://github.com/sekigon-gonnoc/Pico-PIO-USB) | USB host via PIO - lets a future Key sit inline as a USB firewall | yes |
| [adafruit/circuitpython](https://github.com/adafruit/circuitpython) | USB-drive-editable firmware | yes |
| [arduino/ArduinoCore-mbed](https://github.com/arduino/ArduinoCore-mbed) | Arduino on RP2040 via mbed |  |
| [carlk3/no-OS-FatFS-SD-SPI-RPi-Pico](https://github.com/carlk3/no-OS-FatFS-SD-SPI-RPi-Pico) | SD card logging without an OS |  |
| [dhylands/rshell](https://github.com/dhylands/rshell) | remote shell to MicroPython boards |  |
| [earlephilhower/arduino-pico](https://github.com/earlephilhower/arduino-pico) | fast Arduino core for RP2040/RP2350 |  |
| [embassy-rs/embassy](https://github.com/embassy-rs/embassy) | async memory-safe Rust firmware | yes |
| [FreeRTOS/FreeRTOS-Kernel](https://github.com/FreeRTOS/FreeRTOS-Kernel) | SMP real-time kernel |  |
| [hathach/tinyusb](https://github.com/hathach/tinyusb) | USB device/host stack (HID, CDC, MSC) | yes |
| [micropython/micropython](https://github.com/micropython/micropython) | Python on microcontrollers | yes |
| [micropython/micropython-lib](https://github.com/micropython/micropython-lib) | MicroPython packages |  |
| [pimoroni/pico-boilerplate](https://github.com/pimoroni/pico-boilerplate) | project template |  |
| [pimoroni/pimoroni-pico](https://github.com/pimoroni/pimoroni-pico) | drivers for Pico add-ons |  |
| [raspberrypi/debugprobe](https://github.com/raspberrypi/debugprobe) | SWD/UART debug probe firmware | yes |
| [raspberrypi/openocd](https://github.com/raspberrypi/openocd) | on-chip debugging | yes |
| [raspberrypi/pico-examples](https://github.com/raspberrypi/pico-examples) | reference code for every peripheral | yes |
| [raspberrypi/pico-extras](https://github.com/raspberrypi/pico-extras) | extra audio/sleep/scanvideo libs |  |
| [raspberrypi/pico-micropython-examples](https://github.com/raspberrypi/pico-micropython-examples) | MicroPython examples |  |
| [raspberrypi/pico-playground](https://github.com/raspberrypi/pico-playground) | experimental demos |  |
| [raspberrypi/pico-sdk](https://github.com/raspberrypi/pico-sdk) | official C SDK | yes |
| [raspberrypi/pico-setup](https://github.com/raspberrypi/pico-setup) | toolchain setup |  |
| [raspberrypi/pico-setup-windows](https://github.com/raspberrypi/pico-setup-windows) | Windows toolchain installer |  |
| [raspberrypi/pico-vscode](https://github.com/raspberrypi/pico-vscode) | VS Code integration |  |
| [raspberrypi/picotool](https://github.com/raspberrypi/picotool) | flash/inspect/sign binaries | yes |
| [rp-rs/rp-hal](https://github.com/rp-rs/rp-hal) | Rust HAL | yes |
| [tinygo-org/tinygo](https://github.com/tinygo-org/tinygo) | Go on microcontrollers |  |
| [wokwi/rp2040js](https://github.com/wokwi/rp2040js) | RP2040 emulator for CI | yes |
| [zephyrproject-rtos/zephyr](https://github.com/zephyrproject-rtos/zephyr) | RTOS with crypto + MCUboot secure boot | yes |
| [dbisu/pico-ducky](https://github.com/dbisu/pico-ducky) | HID injection - studied to build the detector | yes |

## PROTECT

### Network detection & prevention (`protect.network-ids`)

**Fused capability:** Gateway IDS/IPS that combines Suricata's inline rules, Zeek's protocol logs, Snort's rule ecosystem, CrowdSec's crowd-sourced blocklists and fail2ban's log bans; ntopng-style per-device visibility on top.

**Realised in:** deploy/shield (built): suricata, crowdsec; aureon analyst reads them

| Project | Best capability taken | Pinned |
|---|---|---|
| [OISF/suricata](https://github.com/OISF/suricata) | multi-threaded IDS/IPS + EVE JSON | yes |
| [zeek/zeek](https://github.com/zeek/zeek) | deep protocol logging for hunting | yes |
| [snort3/snort3](https://github.com/snort3/snort3) | mature rule ecosystem | yes |
| [crowdsecurity/crowdsec](https://github.com/crowdsecurity/crowdsec) | crowd-sourced IP reputation + bouncers | yes |
| [fail2ban/fail2ban](https://github.com/fail2ban/fail2ban) | log-driven bans | yes |
| [ntop/ntopng](https://github.com/ntop/ntopng) | per-host traffic visibility | yes |
| [DShield-ISC/dshield](https://github.com/DShield-ISC/dshield) | share sensor data with SANS ISC | yes |

### Endpoint protection (EDR + AV + app firewall) (`protect.endpoint`)

**Fused capability:** Laptop EDR without a vendor: Wazuh FIM/rootkit/vuln checks, OSSEC fallback, ClamAV signatures, YARA hunting rules, OpenSnitch per-app outbound control, Lynis hardening score.

**Realised in:** aureon audit (built), scripts/linux/harden.sh, scripts/windows/harden.ps1 (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [wazuh/wazuh](https://github.com/wazuh/wazuh) | EDR/SIEM with file integrity + vuln detection | yes |
| [ossec/ossec-hids](https://github.com/ossec/ossec-hids) | lightweight host IDS | yes |
| [Cisco-Talos/clamav](https://github.com/Cisco-Talos/clamav) | open AV engine | yes |
| [VirusTotal/yara](https://github.com/VirusTotal/yara) | malware pattern rules | yes |
| [CISOfy/lynis](https://github.com/CISOfy/lynis) | hardening audit with score | yes |
| [evilsocket/opensnitch](https://github.com/evilsocket/opensnitch) | per-app outbound firewall | yes |

### Deception & tripwires (`protect.deception`)

**Fused capability:** Fake services that no legitimate user touches, so any hit is a real intrusion: OpenCanary tripwires, Cowrie shell recording, T-Pot breadth.

**Realised in:** deploy/shield opencanary (built), analyst treats hits as HIGH (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [thinkst/opencanary](https://github.com/thinkst/opencanary) | lightweight multi-protocol canary | yes |
| [cowrie/cowrie](https://github.com/cowrie/cowrie) | SSH/Telnet honeypot with session replay | yes |
| [telekom-security/tpotce](https://github.com/telekom-security/tpotce) | 20+ honeypots + ELK | yes |

### Phone spyware & traffic forensics (`protect.mobile`)

**Fused capability:** MVT IOC scanning + PiRogue network capture + Suricata rules = check both what is on the phone and what it talks to.

**Realised in:** docs/PHONE.md, profiles phone-*, deploy/shield suricata

| Project | Best capability taken | Pinned |
|---|---|---|
| [mvt-project/mvt](https://github.com/mvt-project/mvt) | Pegasus/Predator IOC scanning | yes |
| [PiRogueToolSuite/pirogue-cli](https://github.com/PiRogueToolSuite/pirogue-cli) | phone traffic interception station | yes |

### Forensics & reverse engineering (`protect.forensics`)

**Fused capability:** Incident-response kit: memory (Volatility), disk (Sleuth Kit/Autopsy), packets (Wireshark), binaries/APKs (Ghidra, radare2, Cutter, pwndbg).

**Realised in:** catalog defend layer; aureon fetch defend

| Project | Best capability taken | Pinned |
|---|---|---|
| [volatilityfoundation/volatility3](https://github.com/volatilityfoundation/volatility3) | memory forensics | yes |
| [sleuthkit/sleuthkit](https://github.com/sleuthkit/sleuthkit) | filesystem forensics | yes |
| [sleuthkit/autopsy](https://github.com/sleuthkit/autopsy) | forensics GUI + timeline | yes |
| [wireshark/wireshark](https://github.com/wireshark/wireshark) | packet dissection | yes |
| [NationalSecurityAgency/ghidra](https://github.com/NationalSecurityAgency/ghidra) | decompiler | yes |
| [radareorg/radare2](https://github.com/radareorg/radare2) | scriptable RE (runs on phones) | yes |
| [rizinorg/cutter](https://github.com/rizinorg/cutter) | RE GUI | yes |
| [pwndbg/pwndbg](https://github.com/pwndbg/pwndbg) | exploit-aware GDB | yes |
| [Gallopsled/pwntools](https://github.com/Gallopsled/pwntools) | exploit/CTF toolkit | yes |

### Secrets & credentials hygiene (`protect.secrets`)

**Fused capability:** Find leaked keys before attackers do (gitleaks, trufflehog verification) and keep passwords in your own vault (Vaultwarden).

**Realised in:** deploy/cloud vaultwarden (built); profile laptop-windows gitleaks

| Project | Best capability taken | Pinned |
|---|---|---|
| [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) | secret scanning in git history | yes |
| [trufflesecurity/trufflehog](https://github.com/trufflesecurity/trufflehog) | verified credential detection | yes |
| [dani-garcia/vaultwarden](https://github.com/dani-garcia/vaultwarden) | self-hosted Bitwarden server | yes |
| [AlessandroZ/LaZagne](https://github.com/AlessandroZ/LaZagne) | password recovery - used to test what malware could steal |  |
| [gentilkiwi/mimikatz](https://github.com/gentilkiwi/mimikatz) | credential extraction - informs LSASS protection (ASR rule) |  |

### Self-audit lab (authorized use only) (`protect.audit`)

**Fused capability:** See your own devices as an attacker would: discovery, vuln scanning, web testing, password strength, WiFi strength, AD paths, OSINT exposure. Never auto-installed.

**Realised in:** profile lab; catalog audit layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [carlospolop/PEASS-ng](https://github.com/carlospolop/PEASS-ng) | privilege-escalation checks (run on your own hosts to find misconfig) |  |
| [peass-ng/PEASS-ng](https://github.com/peass-ng/PEASS-ng) | PEASS-ng (current home) | yes |
| [PowerShellMafia/PowerSploit](https://github.com/PowerShellMafia/PowerSploit) | PowerShell post-exploitation (threat model for Windows hardening) |  |
| [swisskyrepo/PayloadsAllTheThings](https://github.com/swisskyrepo/PayloadsAllTheThings) | payload reference for testing your own apps |  |
| [nmap/nmap](https://github.com/nmap/nmap) | service/OS discovery | yes |
| [RustScan/RustScan](https://github.com/RustScan/RustScan) | fast port discovery | yes |
| [robertdavidgraham/masscan](https://github.com/robertdavidgraham/masscan) | very fast scanning | yes |
| [zmap/zmap](https://github.com/zmap/zmap) | network surveys | yes |
| [greenbone/openvas-scanner](https://github.com/greenbone/openvas-scanner) | full vuln scanner | yes |
| [projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei) | template vuln checks | yes |
| [projectdiscovery/httpx](https://github.com/projectdiscovery/httpx) | HTTP probing | yes |
| [projectdiscovery/subfinder](https://github.com/projectdiscovery/subfinder) | subdomain discovery | yes |
| [zaproxy/zaproxy](https://github.com/zaproxy/zaproxy) | web app scanner/proxy | yes |
| [sullo/nikto](https://github.com/sullo/nikto) | web server misconfig | yes |
| [sqlmapproject/sqlmap](https://github.com/sqlmapproject/sqlmap) | SQL injection testing | yes |
| [commixproject/commix](https://github.com/commixproject/commix) | command-injection testing |  |
| [ffuf/ffuf](https://github.com/ffuf/ffuf) | fast fuzzing | yes |
| [OJ/gobuster](https://github.com/OJ/gobuster) | dir/DNS brute force | yes |
| [epi052/feroxbuster](https://github.com/epi052/feroxbuster) | recursive content discovery | yes |
| [rapid7/metasploit-framework](https://github.com/rapid7/metasploit-framework) | exploit framework | yes |
| [fortra/impacket](https://github.com/fortra/impacket) | Windows protocol library | yes |
| [SecureAuthCorp/impacket](https://github.com/SecureAuthCorp/impacket) | impacket (older home) |  |
| [Pennyw0rth/NetExec](https://github.com/Pennyw0rth/NetExec) | network credential auditing | yes |
| [byt3bl33d3r/CrackMapExec](https://github.com/byt3bl33d3r/CrackMapExec) | NetExec predecessor |  |
| [SpecterOps/BloodHound](https://github.com/SpecterOps/BloodHound) | AD attack-path graphs | yes |
| [BloodHoundAD/BloodHound](https://github.com/BloodHoundAD/BloodHound) | BloodHound legacy |  |
| [lgandx/Responder](https://github.com/lgandx/Responder) | LLMNR/NBT-NS poisoning test | yes |
| [hashcat/hashcat](https://github.com/hashcat/hashcat) | GPU password auditing | yes |
| [openwall/john](https://github.com/openwall/john) | CPU password auditing | yes |
| [vanhauser-thc/thc-hydra](https://github.com/vanhauser-thc/thc-hydra) | online login testing | yes |
| [threat9/routersploit](https://github.com/threat9/routersploit) | router vuln testing |  |
| [mitmproxy/mitmproxy](https://github.com/mitmproxy/mitmproxy) | inspect your own app traffic | yes |
| [beefproject/beef](https://github.com/beefproject/beef) | browser exploitation test |  |
| [trustedsec/social-engineer-toolkit](https://github.com/trustedsec/social-engineer-toolkit) | phishing-awareness simulation |  |
| [Ettercap/ettercap](https://github.com/Ettercap/ettercap) | LAN MITM testing |  |
| [bettercap/bettercap](https://github.com/bettercap/bettercap) | network/BLE/WiFi attack simulation | yes |
| [bettercap/caplets](https://github.com/bettercap/caplets) | bettercap scripts |  |
| [LionSec/xerosploit](https://github.com/LionSec/xerosploit) | MITM toolkit |  |
| [moxie0/sslstrip](https://github.com/moxie0/sslstrip) | HTTPS downgrade demo (why HSTS matters) |  |
| [danielmiessler/SecLists](https://github.com/danielmiessler/SecLists) | wordlists | yes |

### WiFi & RF strength testing (own networks) (`protect.wifi-audit`)

**Fused capability:** Prove your own WPA key and router resist real attacks: handshake/PMKID capture, WPS checks, evil-twin simulations, then harden.

**Realised in:** profile lab

| Project | Best capability taken | Pinned |
|---|---|---|
| [aircrack-ng/aircrack-ng](https://github.com/aircrack-ng/aircrack-ng) | WiFi audit suite | yes |
| [aircrack-ng/rtl8812au](https://github.com/aircrack-ng/rtl8812au) | monitor-mode USB WiFi driver |  |
| [ZerBea/hcxdumptool](https://github.com/ZerBea/hcxdumptool) | PMKID/handshake capture | yes |
| [ZerBea/hcxtools](https://github.com/ZerBea/hcxtools) | capture conversion | yes |
| [derv82/wifite2](https://github.com/derv82/wifite2) | automated WiFi audit | yes |
| [kimocoder/wifite2](https://github.com/kimocoder/wifite2) | maintained wifite2 |  |
| [v1s1t0r1sh3r3/airgeddon](https://github.com/v1s1t0r1sh3r3/airgeddon) | menu-driven WiFi audit | yes |
| [aanarchyy/bully](https://github.com/aanarchyy/bully) | WPS PIN testing |  |
| [t6x/reaver-wps-fork-t6x](https://github.com/t6x/reaver-wps-fork-t6x) | WPS testing |  |
| [wiire-a/pixiewps](https://github.com/wiire-a/pixiewps) | WPS pixie-dust test |  |
| [s0lst1c3/eaphammer](https://github.com/s0lst1c3/eaphammer) | WPA-Enterprise evil twin test |  |
| [sensepost/hostapd-mana](https://github.com/sensepost/hostapd-mana) | rogue AP research |  |
| [P0cL4bs/wifipumpkin3](https://github.com/P0cL4bs/wifipumpkin3) | rogue AP framework |  |
| [wifiphisher/wifiphisher](https://github.com/wifiphisher/wifiphisher) | phishing AP simulation |  |
| [FluxionNetwork/fluxion](https://github.com/FluxionNetwork/fluxion) | captive-portal attack simulation |  |
| [SpacehuhnTech/esp8266_deauther](https://github.com/SpacehuhnTech/esp8266_deauther) | deauth testing (shows why WPA3/PMF matter) |  |
| [justcallmekoko/ESP32Marauder](https://github.com/justcallmekoko/ESP32Marauder) | ESP32 WiFi/BLE audit |  |
| [evilsocket/arc](https://github.com/evilsocket/arc) | encrypted vault on the go |  |

### Physical/USB/NFC attack surface (`protect.physical`)

**Fused capability:** Understand BadUSB, NFC cloning and multi-tool attacks so Aureon Key + hidguard can stop them.

**Realised in:** aureon hidguard (built), key/ (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [RoganDawes/P4wnP1_aloa](https://github.com/RoganDawes/P4wnP1_aloa) | USB/WiFi/Bluetooth attack implant (threat model) |  |
| [mame82/P4wnP1](https://github.com/mame82/P4wnP1) | P4wnP1 original |  |
| [mame82/P4wnP1_aloa](https://github.com/mame82/P4wnP1_aloa) | P4wnP1 A.L.O.A. |  |
| [hak5/bashbunny-payloads](https://github.com/hak5/bashbunny-payloads) | USB attack payloads (threat model) |  |
| [hak5/sharkjack-payloads](https://github.com/hak5/sharkjack-payloads) | Ethernet implant payloads (threat model) |  |
| [hak5/usbrubberducky-payloads](https://github.com/hak5/usbrubberducky-payloads) | keystroke injection (threat model) |  |
| [SpacehuhnTech/WiFiDuck](https://github.com/SpacehuhnTech/WiFiDuck) | WiFi-controlled keystroke injector |  |
| [flipperdevices/flipperzero-firmware](https://github.com/flipperdevices/flipperzero-firmware) | multi-protocol RF/NFC tool |  |
| [DarkFlippers/unleashed-firmware](https://github.com/DarkFlippers/unleashed-firmware) | extended Flipper firmware |  |
| [RogueMaster/flipperzero-firmware-wPlugins](https://github.com/RogueMaster/flipperzero-firmware-wPlugins) | Flipper with plugins |  |
| [Proxmark/proxmark3](https://github.com/Proxmark/proxmark3) | RFID/NFC research | yes |
| [RfidResearchGroup/proxmark3](https://github.com/RfidResearchGroup/proxmark3) | maintained Proxmark firmware |  |
| [AdamLaurie/RFIDIOt](https://github.com/AdamLaurie/RFIDIOt) | RFID Python tools |  |
| [nfc-tools/libnfc](https://github.com/nfc-tools/libnfc) | NFC library | yes |
| [nfc-tools/mfoc](https://github.com/nfc-tools/mfoc) | MIFARE Classic key recovery (shows it is broken) |  |

### Personal exposure (OSINT on yourself) (`protect.osint`)

**Fused capability:** Find what the internet knows about you: accounts by email/username, phone exposure, domain footprint - then lock it down.

**Realised in:** profile lab; Termux setup installs holehe/sherlock

| Project | Best capability taken | Pinned |
|---|---|---|
| [s0md3v/Photon](https://github.com/s0md3v/Photon) | fast crawler for your own site's exposed data |  |
| [megadose/holehe](https://github.com/megadose/holehe) | which sites use your email | yes |
| [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | username across sites | yes |
| [soxoj/maigret](https://github.com/soxoj/maigret) | username dossier | yes |
| [mxrch/GHunt](https://github.com/mxrch/GHunt) | Google-account exposure |  |
| [sundowndev/phoneinfoga](https://github.com/sundowndev/phoneinfoga) | phone-number footprint |  |
| [smicallef/spiderfoot](https://github.com/smicallef/spiderfoot) | automated OSINT | yes |
| [laramies/theHarvester](https://github.com/laramies/theHarvester) | domain emails/hosts | yes |
| [lanmaster53/recon-ng](https://github.com/lanmaster53/recon-ng) | modular recon |  |

## RADIO

### Rogue WiFi & fake cell-tower watch (`protect.wireless-watch`)

**Fused capability:** Baseline-and-compare across radios: Kismet's rogue-AP logic, kalibrate-rtl GSM survey, gr-gsm decoding, phone cell info - flags evil twins, security downgrades, 2G forcing, new LAC/TAC.

**Realised in:** aureon rf wifi|cell|gsm (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [kismetwireless/kismet](https://github.com/kismetwireless/kismet) | wireless IDS | yes |
| [ptrkrysik/gr-gsm](https://github.com/ptrkrysik/gr-gsm) | GSM decoding | yes |
| [steve-m/kalibrate-rtl](https://github.com/steve-m/kalibrate-rtl) | GSM base-station scan | yes |

### Off-grid encrypted communication (`network.offgrid`)

**Fused capability:** Meshtastic LoRa texting + Reticulum's medium-agnostic encrypted networking + NomadNet messaging; Aureon relays alert headlines over the mesh.

**Realised in:** deploy/offgrid (built), aureon mesh (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [meshtastic/firmware](https://github.com/meshtastic/firmware) | LoRa mesh radio firmware | yes |
| [meshtastic/python](https://github.com/meshtastic/python) | Meshtastic API/CLI | yes |
| [markqvist/Reticulum](https://github.com/markqvist/Reticulum) | encrypted networking over any link | yes |
| [markqvist/NomadNet](https://github.com/markqvist/NomadNet) | off-grid messaging/pages | yes |
| [wb2osz/direwolf](https://github.com/wb2osz/direwolf) | software packet-radio TNC | yes |

### Software-defined radio core (`radio.sdr`)

**Fused capability:** Hear the spectrum: one SDR abstraction (SoapySDR) over RTL-SDR/HackRF/bladeRF, DSP (GNU Radio, liquid-dsp), receivers and protocol reverse engineering - powering Aureon's RF watch.

**Realised in:** aureon rf gsm consumes kalibrate-rtl output (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [osmocom/rtl-sdr](https://github.com/osmocom/rtl-sdr) | RTL2832U SDR driver | yes |
| [rtlsdrblog/rtl-sdr-blog](https://github.com/rtlsdrblog/rtl-sdr-blog) | improved RTL-SDR driver | yes |
| [greatscottgadgets/hackrf](https://github.com/greatscottgadgets/hackrf) | HackRF tools/firmware |  |
| [Nuand/bladeRF](https://github.com/Nuand/bladeRF) | bladeRF tools |  |
| [pothosware/SoapySDR](https://github.com/pothosware/SoapySDR) | SDR abstraction | yes |
| [gnuradio/gnuradio](https://github.com/gnuradio/gnuradio) | signal processing framework | yes |
| [jgaeddert/liquid-dsp](https://github.com/jgaeddert/liquid-dsp) | DSP library |  |
| [AlexandreRouma/SDRPlusPlus](https://github.com/AlexandreRouma/SDRPlusPlus) | SDR receiver | yes |
| [gqrx-sdr/gqrx](https://github.com/gqrx-sdr/gqrx) | SDR receiver |  |
| [f4exb/sdrangel](https://github.com/f4exb/sdrangel) | SDR receiver/transmitter suite |  |
| [jketterl/openwebrx](https://github.com/jketterl/openwebrx) | web SDR receiver |  |
| [luarvique/openwebrx](https://github.com/luarvique/openwebrx) | OpenWebRX+ fork |  |
| [miek/inspectrum](https://github.com/miek/inspectrum) | signal analysis |  |
| [jopohl/urh](https://github.com/jopohl/urh) | wireless protocol reverse engineering | yes |
| [merbanan/rtl_433](https://github.com/merbanan/rtl_433) | decode 433/868 MHz devices (find hidden transmitters) | yes |
| [EliasOenal/multimon-ng](https://github.com/EliasOenal/multimon-ng) | pager/digital mode decoder |  |

### Aviation, weather & space reception (`radio.aviation-space`)

**Fused capability:** Situational awareness from the sky: aircraft, balloons, satellites - optional Node personality.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [antirez/dump1090](https://github.com/antirez/dump1090) | ADS-B decoder |  |
| [flightaware/dump1090](https://github.com/flightaware/dump1090) | FlightAware dump1090 |  |
| [flightaware/piaware](https://github.com/flightaware/piaware) | FlightAware feeder |  |
| [flightaware/piaware_builder](https://github.com/flightaware/piaware_builder) | piaware build |  |
| [wiedehopf/readsb](https://github.com/wiedehopf/readsb) | ADS-B decoder |  |
| [wiedehopf/tar1090](https://github.com/wiedehopf/tar1090) | aircraft map |  |
| [wiedehopf/graphs1090](https://github.com/wiedehopf/graphs1090) | ADS-B statistics |  |
| [ADSBexchange/adsbx-update](https://github.com/ADSBexchange/adsbx-update) | ADSBx feeder |  |
| [dirkhh/adsb-feeder-image](https://github.com/dirkhh/adsb-feeder-image) | multi-feeder image |  |
| [sdr-enthusiasts/docker-adsb-ultrafeeder](https://github.com/sdr-enthusiasts/docker-adsb-ultrafeeder) | containerised feeder |  |
| [szpajder/dumpvdl2](https://github.com/szpajder/dumpvdl2) | VDL2 decoder |  |
| [TLeconte/acarsdec](https://github.com/TLeconte/acarsdec) | ACARS decoder |  |
| [charlie-foxtrot/RTLSDR-Airband](https://github.com/charlie-foxtrot/RTLSDR-Airband) | airband audio |  |
| [szpajder/RTLSDR-Airband](https://github.com/szpajder/RTLSDR-Airband) | airband (old home) |  |
| [altillimity/SatDump](https://github.com/altillimity/SatDump) | satellite decoder |  |
| [SatDump/SatDump](https://github.com/SatDump/SatDump) | satellite decoder (current) |  |
| [dbdexter-dev/meteor_demod](https://github.com/dbdexter-dev/meteor_demod) | Meteor-M demodulator |  |
| [projecthorus/radiosonde_auto_rx](https://github.com/projecthorus/radiosonde_auto_rx) | weather balloon tracking |  |
| [projecthorus/horusdemodlib](https://github.com/projecthorus/horusdemodlib) | Horus telemetry |  |
| [dl9rdz/rdz_ttgo_sonde](https://github.com/dl9rdz/rdz_ttgo_sonde) | radiosonde on ESP32 |  |

### Amateur radio & emergency comms (`radio.ham`)

**Fused capability:** Licensed long-range comms when everything else is down: digital voice, Winlink email, WSPR/FT8 propagation, rig control.

**Realised in:** catalog only (pairs with network.offgrid)

| Project | Best capability taken | Pinned |
|---|---|---|
| [AndyTaylorTweet/Pi-Star_DV_Dash](https://github.com/AndyTaylorTweet/Pi-Star_DV_Dash) | digital-voice hotspot dashboard |  |
| [ChristopheJacquet/PiFmRds](https://github.com/ChristopheJacquet/PiFmRds) | FM + RDS transmitter (licensed use) |  |
| [AllStarLink/ASL3](https://github.com/AllStarLink/ASL3) | linked repeater network |  |
| [g4klx/MMDVM](https://github.com/g4klx/MMDVM) | digital voice modem firmware |  |
| [g4klx/MMDVMHost](https://github.com/g4klx/MMDVMHost) | digital voice host |  |
| [Hamlib/Hamlib](https://github.com/Hamlib/Hamlib) | rig control |  |
| [la5nta/pat](https://github.com/la5nta/pat) | Winlink email over radio |  |
| [kgoba/ft8_lib](https://github.com/kgoba/ft8_lib) | FT8 weak-signal mode |  |
| [Guenael/rtlsdr-wsprd](https://github.com/Guenael/rtlsdr-wsprd) | WSPR receiver |  |
| [F5OEO/rpitx](https://github.com/F5OEO/rpitx) | GPIO RF transmitter (licensed use) |  |
| [F5OEO/librpitx](https://github.com/F5OEO/librpitx) | rpitx library |  |
| [markondej/fm_transmitter](https://github.com/markondej/fm_transmitter) | GPIO FM transmitter (licensed use) |  |

## NETWORK

### Private filtered DNS (`network.dns`)

**Fused capability:** AdGuard's encrypted DoH/DoT for phones + Pi-hole's blocklists + unbound recursion = no ISP or provider sees your queries.

**Realised in:** deploy/shield (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [AdguardTeam/AdGuardHome](https://github.com/AdguardTeam/AdGuardHome) | DoH/DoT filtering server | yes |
| [pi-hole/pi-hole](https://github.com/pi-hole/pi-hole) | DNS sinkhole | yes |
| [pi-hole/FTL](https://github.com/pi-hole/FTL) | fast DNS engine |  |
| [pi-hole/web](https://github.com/pi-hole/web) | Pi-hole dashboard |  |
| [pi-hole/docker-pi-hole](https://github.com/pi-hole/docker-pi-hole) | containerised Pi-hole |  |
| [NLnetLabs/unbound](https://github.com/NLnetLabs/unbound) | recursive DNSSEC resolver | yes |

### VPN & mesh overlay (`network.vpn`)

**Fused capability:** WireGuard speed + wg-easy QR onboarding + Tailscale NAT traversal + headscale self-hosting + ZeroTier/Yggdrasil fallback meshes.

**Realised in:** deploy/shield wg-easy (built); profiles

| Project | Best capability taken | Pinned |
|---|---|---|
| [WireGuard/wireguard-tools](https://github.com/WireGuard/wireguard-tools) | fast modern VPN | yes |
| [wg-easy/wg-easy](https://github.com/wg-easy/wg-easy) | WireGuard UI with QR codes | yes |
| [angristan/wireguard-install](https://github.com/angristan/wireguard-install) | one-script WireGuard server |  |
| [pivpn/pivpn](https://github.com/pivpn/pivpn) | guided VPN server |  |
| [OpenVPN/openvpn](https://github.com/OpenVPN/openvpn) | compatible fallback VPN |  |
| [Nyr/openvpn-install](https://github.com/Nyr/openvpn-install) | one-script OpenVPN |  |
| [tailscale/tailscale](https://github.com/tailscale/tailscale) | NAT-traversing mesh | yes |
| [juanfont/headscale](https://github.com/juanfont/headscale) | self-hosted Tailscale control | yes |
| [ZeroTier/ZeroTierOne](https://github.com/ZeroTier/ZeroTierOne) | virtual L2 network |  |
| [yggdrasil-network/yggdrasil-go](https://github.com/yggdrasil-network/yggdrasil-go) | encrypted IPv6 mesh | yes |
| [cloudflare/cloudflared](https://github.com/cloudflare/cloudflared) | outbound-only tunnels | yes |

### Anonymity (`network.anonymity`)

**Fused capability:** Tor + I2P routers, transparent torification, onion file sharing.

**Realised in:** catalog net layer; Termux tor

| Project | Best capability taken | Pinned |
|---|---|---|
| [torproject/tor](https://github.com/torproject/tor) | onion routing | yes |
| [PurpleI2P/i2pd](https://github.com/PurpleI2P/i2pd) | lightweight I2P | yes |
| [i2p/i2p.i2p](https://github.com/i2p/i2p.i2p) | Java I2P router |  |
| [brainfucksec/kalitorify](https://github.com/brainfucksec/kalitorify) | transparent Tor proxy | yes |
| [breadtk/onion_pi](https://github.com/breadtk/onion_pi) | Tor access point |  |
| [onionshare/onionshare](https://github.com/onionshare/onionshare) | anonymous file sharing | yes |

### Access point & connectivity (`network.access`)

**Fused capability:** Node as a secure travel router: captive WiFi onboarding, hotspot sharing, AP management.

**Realised in:** catalog net layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [RaspAP/raspap-webgui](https://github.com/RaspAP/raspap-webgui) | router/AP web UI | yes |
| [billz/raspap-webgui](https://github.com/billz/raspap-webgui) | RaspAP (original) |  |
| [balena-io/wifi-connect](https://github.com/balena-io/wifi-connect) | captive-portal WiFi setup |  |
| [balena-os/wifi-connect](https://github.com/balena-os/wifi-connect) | wifi-connect (moved) |  |
| [jasbur/RaspiWiFi](https://github.com/jasbur/RaspiWiFi) | AP-mode WiFi setup |  |
| [sabhiram/raspberry-wifi-conf](https://github.com/sabhiram/raspberry-wifi-conf) | WiFi config via AP |  |
| [lakinduakash/linux-wifi-hotspot](https://github.com/lakinduakash/linux-wifi-hotspot) | laptop hotspot | yes |
| [oblique/create_ap](https://github.com/oblique/create_ap) | one-command AP |  |
| [netbootxyz/netboot.xyz](https://github.com/netbootxyz/netboot.xyz) | network-boot any OS installer |  |

### Sync, sharing & transfer (`network.storage`)

**Fused capability:** Syncthing P2P between phone and laptop, rclone-crypt backups anywhere, SMB/AFP for legacy, IPFS for content addressing, torrent clients for large public data.

**Realised in:** profiles (syncthing); profile node backups (rclone)

| Project | Best capability taken | Pinned |
|---|---|---|
| [Prowlarr/Prowlarr](https://github.com/Prowlarr/Prowlarr) | indexer manager |  |
| [syncthing/syncthing](https://github.com/syncthing/syncthing) | P2P encrypted sync | yes |
| [rclone/rclone](https://github.com/rclone/rclone) | encrypted cloud backup | yes |
| [samba-team/samba](https://github.com/samba-team/samba) | Windows file sharing |  |
| [netatalk/netatalk](https://github.com/netatalk/netatalk) | AFP/Time Machine |  |
| [ipfs/kubo](https://github.com/ipfs/kubo) | content-addressed storage |  |
| [qbittorrent/qBittorrent](https://github.com/qbittorrent/qBittorrent) | BitTorrent client |  |
| [transmission/transmission](https://github.com/transmission/transmission) | light BitTorrent daemon |  |
| [Radarr/Radarr](https://github.com/Radarr/Radarr) | media library automation |  |
| [Sonarr/Sonarr](https://github.com/Sonarr/Sonarr) | series library automation |  |

### Sovereign money nodes (`network.crypto-nodes`)

**Fused capability:** Validate your own transactions with full nodes - no third-party wallet servers learning your addresses.

**Realised in:** catalog only (optional Node personality)

| Project | Best capability taken | Pinned |
|---|---|---|
| [bitcoin/bitcoin](https://github.com/bitcoin/bitcoin) | full node |  |
| [ElementsProject/lightning](https://github.com/ElementsProject/lightning) | Core Lightning |  |
| [lightningnetwork/lnd](https://github.com/lightningnetwork/lnd) | LND Lightning |  |
| [monero-project/monero](https://github.com/monero-project/monero) | private-by-default node |  |

## FREEDOM

### Personal cloud (`freedom.cloud`)

**Fused capability:** Replace Google/Apple/Microsoft services: files, photos, docs, notes, wiki, finance, recipes, RSS - all on the Node, behind Caddy TLS and WireGuard.

**Realised in:** deploy/cloud (built): Immich, Nextcloud, Vaultwarden, Caddy

| Project | Best capability taken | Pinned |
|---|---|---|
| [nextcloud/server](https://github.com/nextcloud/server) | files/calendar/contacts | yes |
| [nextcloud/all-in-one](https://github.com/nextcloud/all-in-one) | one-container Nextcloud |  |
| [owncloud/core](https://github.com/owncloud/core) | ownCloud file sync |  |
| [haiwen/seafile](https://github.com/haiwen/seafile) | fast block-level file sync |  |
| [immich-app/immich](https://github.com/immich-app/immich) | phone photo backup with local ML | yes |
| [PhotoPrism/photoprism](https://github.com/PhotoPrism/photoprism) | AI photo library |  |
| [paperless-ngx/paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) | OCR document archive | yes |
| [BookStackApp/BookStack](https://github.com/BookStackApp/BookStack) | structured wiki |  |
| [requarks/wiki](https://github.com/requarks/wiki) | Wiki.js |  |
| [Jermolene/TiddlyWiki5](https://github.com/Jermolene/TiddlyWiki5) | single-file notebook |  |
| [FreshRSS/FreshRSS](https://github.com/FreshRSS/FreshRSS) | RSS reader |  |
| [miniflux/v2](https://github.com/miniflux/v2) | minimal RSS reader |  |
| [wallabag/wallabag](https://github.com/wallabag/wallabag) | read-it-later |  |
| [mealie-recipes/mealie](https://github.com/mealie-recipes/mealie) | recipe manager |  |
| [actualbudget/actual](https://github.com/actualbudget/actual) | local-first budgeting |  |
| [firefly-iii/firefly-iii](https://github.com/firefly-iii/firefly-iii) | personal finance |  |
| [filebrowser/filebrowser](https://github.com/filebrowser/filebrowser) | web file manager |  |

### Own communications (`freedom.comms`)

**Fused capability:** Encrypted chat, video and voice you host: Matrix federation, Jitsi calls, Mumble low-latency voice, community servers.

**Realised in:** catalog cloud layer (deploy planned)

| Project | Best capability taken | Pinned |
|---|---|---|
| [element-hq/synapse](https://github.com/element-hq/synapse) | Matrix homeserver | yes |
| [matrix-org/synapse](https://github.com/matrix-org/synapse) | Synapse (previous home) |  |
| [jitsi/jitsi-meet](https://github.com/jitsi/jitsi-meet) | video conferencing | yes |
| [mumble-voip/mumble](https://github.com/mumble-voip/mumble) | low-latency voice |  |
| [RocketChat/Rocket.Chat](https://github.com/RocketChat/Rocket.Chat) | team chat |  |
| [zulip/zulip](https://github.com/zulip/zulip) | threaded team chat |  |
| [mastodon/mastodon](https://github.com/mastodon/mastodon) | federated social |  |
| [LemmyNet/lemmy](https://github.com/LemmyNet/lemmy) | federated forums |  |

### Web serving & reverse proxy (`freedom.web`)

**Fused capability:** Caddy's automatic TLS + Traefik's container discovery + Nginx speed; NPM for click-ops.

**Realised in:** deploy/cloud Caddyfile (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [caddyserver/caddy](https://github.com/caddyserver/caddy) | automatic HTTPS | yes |
| [traefik/traefik](https://github.com/traefik/traefik) | dynamic container routing |  |
| [nginx/nginx](https://github.com/nginx/nginx) | high-performance server |  |
| [apache/httpd](https://github.com/apache/httpd) | module-rich server |  |
| [NginxProxyManager/nginx-proxy-manager](https://github.com/NginxProxyManager/nginx-proxy-manager) | GUI reverse proxy |  |

### Databases (`freedom.data`)

**Fused capability:** Reliable storage engines behind every Aureon service.

**Realised in:** deploy/cloud (postgres, redis)

| Project | Best capability taken | Pinned |
|---|---|---|
| [postgres/postgres](https://github.com/postgres/postgres) | relational DB with extensions |  |
| [MariaDB/server](https://github.com/MariaDB/server) | MySQL-compatible DB |  |
| [redis/redis](https://github.com/redis/redis) | in-memory cache/queue |  |
| [influxdata/influxdb](https://github.com/influxdata/influxdb) | time-series metrics |  |

### Business apps (`freedom.business`)

**Fused capability:** ERP/CRM/accounting if the Node runs a small business.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [frappe/erpnext](https://github.com/frappe/erpnext) | ERP |  |
| [odoo/odoo](https://github.com/odoo/odoo) | business suite |  |

### Own dev platform (`freedom.dev`)

**Fused capability:** Private git, browser IDE, notebooks, automation - code from phone or laptop against the Node.

**Realised in:** catalog cloud layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [go-gitea/gitea](https://github.com/go-gitea/gitea) | lightweight git forge | yes |
| [gogs/gogs](https://github.com/gogs/gogs) | minimal git service |  |
| [coder/code-server](https://github.com/coder/code-server) | VS Code in browser | yes |
| [VSCodium/vscodium](https://github.com/VSCodium/vscodium) | telemetry-free VS Code | yes |
| [microsoft/vscode](https://github.com/microsoft/vscode) | VS Code source |  |
| [jupyter/notebook](https://github.com/jupyter/notebook) | notebooks |  |
| [jupyterlab/jupyterlab](https://github.com/jupyterlab/jupyterlab) | notebook IDE |  |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | workflow automation | yes |
| [huginn/huginn](https://github.com/huginn/huginn) | agents that watch the web |  |

## PERFORM

### Remote access & rescue (`freedom.remote`)

**Fused capability:** Reach any device from any device: RustDesk remote desktop, Guacamole in a browser, VNC/RDP, plus below-OS rescue via PiKVM/TinyPilot.

**Realised in:** aureon rescue (built) for PiKVM; profiles RustDesk

| Project | Best capability taken | Pinned |
|---|---|---|
| [rustdesk/rustdesk](https://github.com/rustdesk/rustdesk) | self-hostable remote desktop | yes |
| [apache/guacamole-server](https://github.com/apache/guacamole-server) | clientless browser remote desktop | yes |
| [novnc/noVNC](https://github.com/novnc/noVNC) | VNC in the browser |  |
| [TigerVNC/tigervnc](https://github.com/TigerVNC/tigervnc) | fast VNC |  |
| [LibVNC/x11vnc](https://github.com/LibVNC/x11vnc) | share an existing X display |  |
| [neutrinolabs/xrdp](https://github.com/neutrinolabs/xrdp) | RDP server for Linux |  |
| [pikvm/kvmd](https://github.com/pikvm/kvmd) | KVM-over-IP daemon (ATX, HID, MSD) | yes |
| [pikvm/os](https://github.com/pikvm/os) | PiKVM OS | yes |
| [pikvm/pikvm](https://github.com/pikvm/pikvm) | PiKVM hardware/project |  |
| [pikvm/ustreamer](https://github.com/pikvm/ustreamer) | low-latency MJPEG streamer | yes |
| [tiny-pilot/tinypilot](https://github.com/tiny-pilot/tinypilot) | simple KVM-over-IP | yes |
| [cockpit-project/cockpit](https://github.com/cockpit-project/cockpit) | web Linux admin | yes |
| [webmin/webmin](https://github.com/webmin/webmin) | web system admin |  |

### Dashboards (`freedom.dashboard`)

**Fused capability:** One start page for every Aureon service.

**Realised in:** catalog (homepage planned in deploy)

| Project | Best capability taken | Pinned |
|---|---|---|
| [gethomepage/homepage](https://github.com/gethomepage/homepage) | service dashboard with widgets | yes |
| [bastienwirtz/homer](https://github.com/bastienwirtz/homer) | static dashboard |  |
| [Lissy93/dashy](https://github.com/Lissy93/dashy) | configurable dashboard |  |
| [linuxserver/Heimdall](https://github.com/linuxserver/Heimdall) | app launcher |  |

### Observability & health (`perform.observe`)

**Fused capability:** Per-second metrics + ML anomaly detection (Netdata), long-term Prometheus/Grafana, uptime alerts, TUI monitors on every device.

**Realised in:** deploy/shield netdata (built); aureon audit perf checks (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [netdata/netdata](https://github.com/netdata/netdata) | per-second metrics + anomaly ML | yes |
| [prometheus/prometheus](https://github.com/prometheus/prometheus) | metrics TSDB + alerting | yes |
| [prometheus/node_exporter](https://github.com/prometheus/node_exporter) | host metrics | yes |
| [grafana/grafana](https://github.com/grafana/grafana) | dashboards | yes |
| [influxdata/telegraf](https://github.com/influxdata/telegraf) | metrics collection agent |  |
| [louislam/uptime-kuma](https://github.com/louislam/uptime-kuma) | uptime monitoring | yes |
| [nicolargo/glances](https://github.com/nicolargo/glances) | cross-platform monitor + API | yes |
| [aristocratos/btop](https://github.com/aristocratos/btop) | rich resource TUI | yes |
| [ClementTsang/bottom](https://github.com/ClementTsang/bottom) | cross-platform TUI | yes |
| [htop-dev/htop](https://github.com/htop-dev/htop) | process viewer |  |
| [XavierBerger/RPi-Monitor](https://github.com/XavierBerger/RPi-Monitor) | Pi health web UI |  |

### Containers, VMs & clusters (`perform.compute`)

**Fused capability:** Sandbox and scale: rootless Podman, Incus system containers/VMs, k3s clusters across Node + laptops, Ansible to provision all of it.

**Realised in:** deploy/* compose (built); ops layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [containers/podman](https://github.com/containers/podman) | rootless containers | yes |
| [moby/moby](https://github.com/moby/moby) | Docker engine |  |
| [docker/compose](https://github.com/docker/compose) | multi-container apps | yes |
| [docker/docker-install](https://github.com/docker/docker-install) | Docker install script |  |
| [lxc/lxc](https://github.com/lxc/lxc) | system containers |  |
| [lxc/incus](https://github.com/lxc/incus) | containers + VMs manager | yes |
| [k3s-io/k3s](https://github.com/k3s-io/k3s) | lightweight Kubernetes | yes |
| [k3s-io/k3s-ansible](https://github.com/k3s-io/k3s-ansible) | k3s via Ansible |  |
| [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) | Kubernetes |  |
| [canonical/microk8s](https://github.com/canonical/microk8s) | snap Kubernetes |  |
| [rancher/rancher](https://github.com/rancher/rancher) | cluster management |  |
| [hashicorp/nomad](https://github.com/hashicorp/nomad) | simple orchestrator |  |
| [openfaas/faas](https://github.com/openfaas/faas) | functions as a service |  |
| [openfaas/faasd](https://github.com/openfaas/faasd) | FaaS without Kubernetes |  |
| [portainer/portainer](https://github.com/portainer/portainer) | container UI | yes |
| [containrrr/watchtower](https://github.com/containrrr/watchtower) | container auto-update | yes |
| [ansible/ansible](https://github.com/ansible/ansible) | agentless provisioning | yes |
| [geerlingguy/ansible-role-docker_arm](https://github.com/geerlingguy/ansible-role-docker_arm) | Docker on ARM role |  |
| [geerlingguy/pi-cluster](https://github.com/geerlingguy/pi-cluster) | Pi cluster playbooks |  |
| [geerlingguy/raspberry-pi-dramble](https://github.com/geerlingguy/raspberry-pi-dramble) | Pi Kubernetes cluster |  |
| [geerlingguy/turing-pi-2-cluster](https://github.com/geerlingguy/turing-pi-2-cluster) | Turing Pi cluster |  |
| [alexellis/arkade](https://github.com/alexellis/arkade) | Kubernetes app installer |  |
| [alexellis/k3sup](https://github.com/alexellis/k3sup) | k3s over SSH |  |
| [balena-io/balena-cli](https://github.com/balena-io/balena-cli) | fleet deploys |  |

### Run any software anywhere (`perform.compat`)

**Fused capability:** x86 on ARM (FEX, box64/box86), Windows apps on Linux (Wine, Hangover), GL on mobile GPUs (gl4es), full emulation (QEMU), packaged sandboxes (Flatpak/Snap).

**Realised in:** profile laptop-linux steps (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [FEX-Emu/FEX](https://github.com/FEX-Emu/FEX) | fast x86-64 on ARM64 | yes |
| [ptitSeb/box64](https://github.com/ptitSeb/box64) | x86-64 Linux userspace on ARM64 | yes |
| [ptitSeb/box86](https://github.com/ptitSeb/box86) | x86 Linux userspace on ARM | yes |
| [ptitSeb/gl4es](https://github.com/ptitSeb/gl4es) | OpenGL on GLES | yes |
| [wine-mirror/wine](https://github.com/wine-mirror/wine) | Windows API on Linux | yes |
| [AndreRH/hangover](https://github.com/AndreRH/hangover) | Windows x86 apps on ARM | yes |
| [qemu/qemu](https://github.com/qemu/qemu) | full-system emulation | yes |
| [dhruvvyas90/qemu-rpi-kernel](https://github.com/dhruvvyas90/qemu-rpi-kernel) | Pi kernels for QEMU |  |
| [carlosperate/docker-qemu-rpi-os](https://github.com/carlosperate/docker-qemu-rpi-os) | Pi OS in Docker |  |
| [lukechilds/dockerpi](https://github.com/lukechilds/dockerpi) | Pi in a container |  |
| [flatpak/flatpak](https://github.com/flatpak/flatpak) | sandboxed desktop apps | yes |
| [snapcore/snapd](https://github.com/snapcore/snapd) | confined snap packages |  |

### Fast, light desktop & UI (`perform.desktop`)

**Fused capability:** Low-RAM Wayland sessions, kiosk lockdown mode, efficient terminal tools, and UI toolkits for Aureon's own screens.

**Realised in:** profile laptop-linux (sway/labwc)

| Project | Best capability taken | Pinned |
|---|---|---|
| [swaywm/sway](https://github.com/swaywm/sway) | tiling Wayland compositor | yes |
| [labwc/labwc](https://github.com/labwc/labwc) | light stacking compositor | yes |
| [WayfireWM/wayfire](https://github.com/WayfireWM/wayfire) | 3D compositor that stays light | yes |
| [cage-kiosk/cage](https://github.com/cage-kiosk/cage) | single-app kiosk | yes |
| [lxqt/lxqt](https://github.com/lxqt/lxqt) | light Qt desktop |  |
| [lxde/lxpanel](https://github.com/lxde/lxpanel) | light panel |  |
| [neovim/neovim](https://github.com/neovim/neovim) | fast extensible editor | yes |
| [vim/vim](https://github.com/vim/vim) | ubiquitous editor |  |
| [tmux/tmux](https://github.com/tmux/tmux) | terminal multiplexer | yes |
| [jesseduffield/lazygit](https://github.com/jesseduffield/lazygit) | git TUI | yes |
| [ranger/ranger](https://github.com/ranger/ranger) | TUI file manager | yes |
| [cmus/cmus](https://github.com/cmus/cmus) | TUI music player |  |
| [geany/geany](https://github.com/geany/geany) | light IDE |  |
| [LVGL/lvgl](https://github.com/LVGL/lvgl) | embedded GUI library |  |
| [lvgl/lv_port_linux](https://github.com/lvgl/lv_port_linux) | LVGL on Linux framebuffer |  |
| [slint-ui/slint](https://github.com/slint-ui/slint) | declarative native UI |  |
| [ardera/flutter-pi](https://github.com/ardera/flutter-pi) | Flutter without X/Wayland |  |
| [sony/flutter-elinux](https://github.com/sony/flutter-elinux) | Flutter for embedded Linux |  |
| [kivy/kivy](https://github.com/kivy/kivy) | Python touch UI |  |
| [dividuum/info-beamer](https://github.com/dividuum/info-beamer) | GPU-accelerated signage |  |
| [info-beamer/package-sdk](https://github.com/info-beamer/package-sdk) | info-beamer packages |  |

### Game & desktop streaming (`perform.stream`)

**Fused capability:** Laptop-phone fusion: stream the laptop desktop/games to the phone at low latency.

**Realised in:** profiles laptop-windows / phone-android (Sunshine + Moonlight)

| Project | Best capability taken | Pinned |
|---|---|---|
| [LizardByte/Sunshine](https://github.com/LizardByte/Sunshine) | low-latency game/desktop streaming host | yes |
| [moonlight-stream/moonlight-qt](https://github.com/moonlight-stream/moonlight-qt) | Moonlight desktop/mobile client | yes |
| [moonlight-stream/moonlight-embedded](https://github.com/moonlight-stream/moonlight-embedded) | Moonlight for embedded |  |

## INTELLIGENCE

### Local LLM brain (`intel.llm`)

**Fused capability:** Private assistant + security analyst: llama.cpp efficiency, Ollama model management, Open WebUI chat/RAG, LocalAI OpenAI-compatible API, llamafile portability.

**Realised in:** deploy/ai (built), aureon analyst (built)

| Project | Best capability taken | Pinned |
|---|---|---|
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | quantised LLM inference everywhere | yes |
| [ollama/ollama](https://github.com/ollama/ollama) | model manager + API | yes |
| [open-webui/open-webui](https://github.com/open-webui/open-webui) | chat UI + RAG | yes |
| [mudler/LocalAI](https://github.com/mudler/LocalAI) | OpenAI-compatible local API | yes |
| [Mozilla-Ocho/llamafile](https://github.com/Mozilla-Ocho/llamafile) | single-file LLM | yes |
| [nomic-ai/gpt4all](https://github.com/nomic-ai/gpt4all) | desktop local chat |  |
| [leon-ai/leon](https://github.com/leon-ai/leon) | personal assistant framework |  |

### Offline voice (`intel.voice`)

**Fused capability:** Wake word -> speech-to-text -> LLM -> text-to-speech fully offline, glued by the Wyoming protocol.

**Realised in:** catalog ai layer (voice pipeline planned)

| Project | Best capability taken | Pinned |
|---|---|---|
| [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | fast offline STT | yes |
| [openai/whisper](https://github.com/openai/whisper) | accurate STT reference |  |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2 STT | yes |
| [alphacep/vosk-api](https://github.com/alphacep/vosk-api) | tiny STT for phones | yes |
| [mozilla/DeepSpeech](https://github.com/mozilla/DeepSpeech) | legacy STT |  |
| [rhasspy/piper](https://github.com/rhasspy/piper) | fast neural TTS | yes |
| [coqui-ai/TTS](https://github.com/coqui-ai/TTS) | high-quality TTS |  |
| [dscripka/openWakeWord](https://github.com/dscripka/openWakeWord) | open wake words | yes |
| [picovoice/porcupine](https://github.com/picovoice/porcupine) | efficient wake word |  |
| [picovoice/picovoice](https://github.com/picovoice/picovoice) | on-device voice platform |  |
| [rhasspy/rhasspy](https://github.com/rhasspy/rhasspy) | offline voice assistant |  |
| [rhasspy/rhasspy3](https://github.com/rhasspy/rhasspy3) | modular voice pipeline |  |
| [rhasspy/wyoming](https://github.com/rhasspy/wyoming) | voice service protocol | yes |
| [rhasspy/wyoming-faster-whisper](https://github.com/rhasspy/wyoming-faster-whisper) | Wyoming STT server |  |
| [rhasspy/wyoming-openwakeword](https://github.com/rhasspy/wyoming-openwakeword) | Wyoming wake word |  |
| [rhasspy/wyoming-satellite](https://github.com/rhasspy/wyoming-satellite) | remote voice satellites |  |
| [OpenVoiceOS/ovos-core](https://github.com/OpenVoiceOS/ovos-core) | open voice assistant | yes |
| [OpenVoiceOS/ovos-installer](https://github.com/OpenVoiceOS/ovos-installer) | OVOS installer |  |
| [OpenVoiceOS/raspOVOS](https://github.com/OpenVoiceOS/raspOVOS) | OVOS image |  |
| [MycroftAI/mycroft-core](https://github.com/MycroftAI/mycroft-core) | Mycroft assistant |  |
| [MycroftAI/enclosure-picroft](https://github.com/MycroftAI/enclosure-picroft) | Mycroft on Pi |  |
| [NeonGeckoCom/NeonCore](https://github.com/NeonGeckoCom/NeonCore) | Neon assistant |  |
| [kalliope-project/kalliope](https://github.com/kalliope-project/kalliope) | modular assistant |  |
| [alexa/avs-device-sdk](https://github.com/alexa/avs-device-sdk) | Alexa SDK (reference) |  |
| [googlesamples/assistant-sdk-python](https://github.com/googlesamples/assistant-sdk-python) | Google Assistant SDK (reference) |  |

### Vision & presence (`intel.vision`)

**Fused capability:** Camera intelligence for physical security: YOLO detection, Frigate NVR, face presence, MediaPipe pose/hands.

**Realised in:** EXTENSIONS camera presence; catalog ai layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [opencv/opencv](https://github.com/opencv/opencv) | computer vision core | yes |
| [opencv/opencv_contrib](https://github.com/opencv/opencv_contrib) | extra CV modules |  |
| [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) | YOLO detection | yes |
| [blakeblackshear/frigate](https://github.com/blakeblackshear/frigate) | AI NVR | yes |
| [ageitgey/face_recognition](https://github.com/ageitgey/face_recognition) | face recognition | yes |
| [davisking/dlib](https://github.com/davisking/dlib) | face landmarks + ML |  |
| [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | on-device vision pipelines | yes |
| [EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi](https://github.com/EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi) | TFLite detection recipe |  |
| [edgeimpulse/edge-impulse-linux-cli](https://github.com/edgeimpulse/edge-impulse-linux-cli) | edge model deploy |  |
| [edgeimpulse/linux-sdk-python](https://github.com/edgeimpulse/linux-sdk-python) | edge inference SDK |  |

### AI acceleration (`intel.accel`)

**Fused capability:** Use whatever silicon exists: NPUs (Hailo, Intel NPU via OpenVINO), TPUs (Coral), GPUs (Vulkan ncnn), CPUs (ONNX Runtime, LiteRT, TVM).

**Realised in:** profile notes; catalog ai layer

| Project | Best capability taken | Pinned |
|---|---|---|
| [PaddlePaddle/Paddle-Lite](https://github.com/PaddlePaddle/Paddle-Lite) | lightweight mobile inference |  |
| [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) | cross-hardware inference | yes |
| [openvinotoolkit/openvino](https://github.com/openvinotoolkit/openvino) | Intel CPU/GPU/NPU | yes |
| [google-ai-edge/LiteRT](https://github.com/google-ai-edge/LiteRT) | on-device ML runtime | yes |
| [tensorflow/tensorflow](https://github.com/tensorflow/tensorflow) | training + TFLite |  |
| [pytorch/pytorch](https://github.com/pytorch/pytorch) | training framework |  |
| [apache/tvm](https://github.com/apache/tvm) | model compiler for any target |  |
| [Tencent/ncnn](https://github.com/Tencent/ncnn) | Vulkan mobile inference | yes |
| [google-coral/edgetpu](https://github.com/google-coral/edgetpu) | Edge TPU runtime |  |
| [google-coral/pycoral](https://github.com/google-coral/pycoral) | Edge TPU Python API | yes |
| [google-coral/tflite](https://github.com/google-coral/tflite) | Coral TFLite examples |  |
| [hailo-ai/hailort](https://github.com/hailo-ai/hailort) | Hailo NPU runtime | yes |
| [hailo-ai/hailort-drivers](https://github.com/hailo-ai/hailort-drivers) | Hailo PCIe driver |  |
| [hailo-ai/tappas](https://github.com/hailo-ai/tappas) | Hailo pipelines |  |
| [hailo-ai/hailo-apps-infra](https://github.com/hailo-ai/hailo-apps-infra) | Hailo app infra |  |
| [hailo-ai/hailo-rpi5-examples](https://github.com/hailo-ai/hailo-rpi5-examples) | Hailo on Pi 5 |  |

### Robotics & drones (`intel.robotics`)

**Fused capability:** Autonomy stack for future Aureon field units: ROS 2, ArduPilot, MAVLink, long-range video links.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [PX4/PX4-Autopilot](https://github.com/PX4/PX4-Autopilot) | professional drone autopilot |  |
| [ros/ros_comm](https://github.com/ros/ros_comm) | ROS 1 communications |  |
| [ros2/ros2](https://github.com/ros2/ros2) | ROS 2 |  |
| [ros2/rclpy](https://github.com/ros2/rclpy) | ROS 2 Python |  |
| [ArduPilot/ardupilot](https://github.com/ArduPilot/ardupilot) | autopilot |  |
| [ArduPilot/MAVProxy](https://github.com/ArduPilot/MAVProxy) | ground station |  |
| [mavlink/MAVSDK](https://github.com/mavlink/MAVSDK) | drone SDK |  |
| [mavlink-router/mavlink-router](https://github.com/mavlink-router/mavlink-router) | MAVLink routing |  |
| [OpenHD/OpenHD](https://github.com/OpenHD/OpenHD) | long-range HD video link |  |
| [rodizio1/EZ-WifiBroadcast](https://github.com/rodizio1/EZ-WifiBroadcast) | WiFi broadcast video |  |
| [svpcom/wfb-ng](https://github.com/svpcom/wfb-ng) | WiFi broadcast next-gen |  |
| [bluerobotics/BlueOS](https://github.com/bluerobotics/BlueOS) | underwater vehicle OS |  |
| [bluerobotics/companion](https://github.com/bluerobotics/companion) | ROV companion |  |
| [autorope/donkeycar](https://github.com/autorope/donkeycar) | self-driving RC car |  |
| [DexterInd/BrickPi3](https://github.com/DexterInd/BrickPi3) | LEGO robotics |  |
| [DexterInd/GoPiGo3](https://github.com/DexterInd/GoPiGo3) | robot car |  |
| [Freenove/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi](https://github.com/Freenove/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi) | robot car kit |  |
| [PetoiCamp/OpenCat](https://github.com/PetoiCamp/OpenCat) | quadruped robot |  |
| [sunfounder/picar-x](https://github.com/sunfounder/picar-x) | robot car |  |
| [sunfounder/robot-hat](https://github.com/sunfounder/robot-hat) | robot HAT |  |

## HOME

### Device automation & presence (`home.automation`)

**Fused capability:** Aureon reacts to the physical world: Home Assistant automations, Zigbee/Z-Wave without vendor clouds, MQTT bus, Node-RED flows - e.g. lock laptops when you leave, alert on door sensors.

**Realised in:** catalog cloud layer (home-assistant)

| Project | Best capability taken | Pinned |
|---|---|---|
| [home-assistant/core](https://github.com/home-assistant/core) | home automation engine | yes |
| [home-assistant/frontend](https://github.com/home-assistant/frontend) | HA UI |  |
| [home-assistant/addons](https://github.com/home-assistant/addons) | HA add-ons |  |
| [home-assistant/supervised-installer](https://github.com/home-assistant/supervised-installer) | HA supervised install |  |
| [openhab/openhab-core](https://github.com/openhab/openhab-core) | openHAB engine |  |
| [openhab/openhab-distro](https://github.com/openhab/openhab-distro) | openHAB distribution |  |
| [domoticz/domoticz](https://github.com/domoticz/domoticz) | light home automation |  |
| [ioBroker/ioBroker](https://github.com/ioBroker/ioBroker) | integration platform |  |
| [nymea/nymea](https://github.com/nymea/nymea) | IoT edge server |  |
| [homebridge/homebridge](https://github.com/homebridge/homebridge) | HomeKit for anything |  |
| [homebridge/homebridge-config-ui-x](https://github.com/homebridge/homebridge-config-ui-x) | Homebridge UI |  |
| [node-red/node-red](https://github.com/node-red/node-red) | flow-based wiring |  |
| [node-red/node-red-nodes](https://github.com/node-red/node-red-nodes) | extra nodes |  |
| [node-red/linux-installers](https://github.com/node-red/linux-installers) | Node-RED installer |  |
| [node-red/raspbian-deb-package](https://github.com/node-red/raspbian-deb-package) | Node-RED packaging |  |
| [Koenkk/zigbee2mqtt](https://github.com/Koenkk/zigbee2mqtt) | Zigbee without vendor hubs |  |
| [zigbee2mqtt/hassio-zigbee2mqtt](https://github.com/zigbee2mqtt/hassio-zigbee2mqtt) | Z2M HA add-on |  |
| [zwave-js/node-zwave-js](https://github.com/zwave-js/node-zwave-js) | Z-Wave driver |  |
| [zwave-js/zwave-js-ui](https://github.com/zwave-js/zwave-js-ui) | Z-Wave control panel |  |
| [eclipse-mosquitto/mosquitto](https://github.com/eclipse-mosquitto/mosquitto) | MQTT broker |  |
| [eclipse/mosquitto](https://github.com/eclipse/mosquitto) | Mosquitto (old home) |  |
| [emqx/emqx](https://github.com/emqx/emqx) | scalable MQTT broker |  |
| [esphome/esphome](https://github.com/esphome/esphome) | YAML firmware for ESP sensors |  |
| [arendst/Tasmota](https://github.com/arendst/Tasmota) | open firmware for smart plugs |  |
| [mysensors/MySensors](https://github.com/mysensors/MySensors) | DIY wireless sensors |  |
| [thingsboard/thingsboard](https://github.com/thingsboard/thingsboard) | IoT platform |  |
| [weewx/weewx](https://github.com/weewx/weewx) | weather station |  |
| [MagicMirrorOrg/MagicMirror](https://github.com/MagicMirrorOrg/MagicMirror) | smart mirror |  |
| [MichMich/MagicMirror](https://github.com/MichMich/MagicMirror) | MagicMirror (old home) |  |
| [sdetweil/MagicMirror_scripts](https://github.com/sdetweil/MagicMirror_scripts) | MagicMirror install scripts |  |

## MEDIA

### Media, music & cameras (`media.center`)

**Fused capability:** Own your media and cameras: Jellyfin streaming, multi-room audio, AirPlay/Spotify endpoints, camera NVR, photo sync.

**Realised in:** catalog (Immich in deploy/cloud)

| Project | Best capability taken | Pinned |
|---|---|---|
| [xbmc/xbmc](https://github.com/xbmc/xbmc) | Kodi media center |  |
| [jellyfin/jellyfin](https://github.com/jellyfin/jellyfin) | media server | yes |
| [jellyfin/jellyfin-web](https://github.com/jellyfin/jellyfin-web) | Jellyfin UI |  |
| [navidrome/navidrome](https://github.com/navidrome/navidrome) | music streaming server | yes |
| [MusicPlayerDaemon/MPD](https://github.com/MusicPlayerDaemon/MPD) | music daemon |  |
| [mopidy/mopidy](https://github.com/mopidy/mopidy) | extensible music server |  |
| [jaedb/Iris](https://github.com/jaedb/Iris) | Mopidy UI |  |
| [LMS-Community/slimserver](https://github.com/LMS-Community/slimserver) | Lyrion music server |  |
| [ralph-irving/squeezelite](https://github.com/ralph-irving/squeezelite) | Squeezebox player |  |
| [owntone/owntone-server](https://github.com/owntone/owntone-server) | AirPlay/Remote server |  |
| [badaix/snapcast](https://github.com/badaix/snapcast) | synchronous multi-room audio |  |
| [mikebrady/shairport-sync](https://github.com/mikebrady/shairport-sync) | AirPlay receiver |  |
| [dtcooper/raspotify](https://github.com/dtcooper/raspotify) | Spotify Connect |  |
| [librespot-org/librespot](https://github.com/librespot-org/librespot) | open Spotify client |  |
| [spocon/spocon](https://github.com/spocon/spocon) | Spotify Connect daemon |  |
| [Arkq/bluez-alsa](https://github.com/Arkq/bluez-alsa) | Bluetooth audio |  |
| [balena-io-experimental/balena-sound](https://github.com/balena-io-experimental/balena-sound) | multi-room audio (old) |  |
| [balena-labs-projects/balena-sound](https://github.com/balena-labs-projects/balena-sound) | multi-room audio |  |
| [volumio/Volumio2](https://github.com/volumio/Volumio2) | music player |  |
| [volumio/volumio3-backend](https://github.com/volumio/volumio3-backend) | Volumio backend |  |
| [MiczFlor/RPi-Jukebox-RFID](https://github.com/MiczFlor/RPi-Jukebox-RFID) | RFID jukebox |  |
| [mpv-player/mpv](https://github.com/mpv-player/mpv) | GPU-accelerated player | yes |
| [popcornmix/omxplayer](https://github.com/popcornmix/omxplayer) | legacy HW player |  |
| [sonic-pi-net/sonic-pi](https://github.com/sonic-pi-net/sonic-pi) | live-coded music |  |
| [bluenviron/mediamtx](https://github.com/bluenviron/mediamtx) | universal media server (RTSP/WebRTC) |  |
| [aler9/rtsp-simple-server](https://github.com/aler9/rtsp-simple-server) | mediamtx (old name) |  |
| [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc) | camera streaming hub |  |
| [ayufan/camera-streamer](https://github.com/ayufan/camera-streamer) | low-latency Pi camera streaming |  |
| [jacksonliam/mjpg-streamer](https://github.com/jacksonliam/mjpg-streamer) | MJPEG streaming |  |
| [Motion-Project/motion](https://github.com/Motion-Project/motion) | motion detection |  |
| [motioneye-project/motioneye](https://github.com/motioneye-project/motioneye) | camera web UI |  |
| [ccrisan/motioneye](https://github.com/ccrisan/motioneye) | motionEye (old home) |  |
| [kerberos-io/agent](https://github.com/kerberos-io/agent) | video surveillance agent |  |
| [ZoneMinder/zoneminder](https://github.com/ZoneMinder/zoneminder) | full NVR |  |
| [silvanmelchior/RPi_Cam_Web_Interface](https://github.com/silvanmelchior/RPi_Cam_Web_Interface) | Pi camera web UI |  |

### Gaming & emulation (`media.play`)

**Fused capability:** Turn idle hardware into a console: RetroArch cores, standalone emulators, source ports.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [libretro/RetroArch](https://github.com/libretro/RetroArch) | unified emulator frontend |  |
| [libretro/libretro-super](https://github.com/libretro/libretro-super) | build all cores |  |
| [libretro/beetle-psx-libretro](https://github.com/libretro/beetle-psx-libretro) | accurate PS1 |  |
| [libretro/fbneo](https://github.com/libretro/fbneo) | arcade |  |
| [libretro/mame](https://github.com/libretro/mame) | MAME core |  |
| [libretro/mupen64plus-libretro-nx](https://github.com/libretro/mupen64plus-libretro-nx) | N64 core |  |
| [libretro/pcsx_rearmed](https://github.com/libretro/pcsx_rearmed) | fast PS1 on ARM |  |
| [libretro/snes9x](https://github.com/libretro/snes9x) | SNES |  |
| [Aloshi/EmulationStation](https://github.com/Aloshi/EmulationStation) | game launcher UI |  |
| [RetroPie/EmulationStation](https://github.com/RetroPie/EmulationStation) | RetroPie launcher |  |
| [batocera-linux/batocera-emulationstation](https://github.com/batocera-linux/batocera-emulationstation) | Batocera launcher |  |
| [BlitterStudio/amiberry](https://github.com/BlitterStudio/amiberry) | Amiga |  |
| [midwan/amiberry](https://github.com/midwan/amiberry) | Amiberry (old home) |  |
| [dolphin-emu/dolphin](https://github.com/dolphin-emu/dolphin) | GameCube/Wii |  |
| [PCSX2/pcsx2](https://github.com/PCSX2/pcsx2) | PS2 |  |
| [hrydgard/ppsspp](https://github.com/hrydgard/ppsspp) | PSP |  |
| [flyinghead/flycast](https://github.com/flyinghead/flycast) | Dreamcast |  |
| [mupen64plus/mupen64plus-core](https://github.com/mupen64plus/mupen64plus-core) | N64 |  |
| [DOSBox-Staging/dosbox-staging](https://github.com/DOSBox-Staging/dosbox-staging) | DOS |  |
| [scummvm/scummvm](https://github.com/scummvm/scummvm) | adventure games |  |
| [chocolate-doom/chocolate-doom](https://github.com/chocolate-doom/chocolate-doom) | faithful Doom |  |
| [fabiangreffrath/crispy-doom](https://github.com/fabiangreffrath/crispy-doom) | enhanced Doom |  |
| [ioquake/ioq3](https://github.com/ioquake/ioq3) | Quake III |  |
| [Novum/vkQuake](https://github.com/Novum/vkQuake) | Vulkan Quake |  |
| [yquake2/yquake2](https://github.com/yquake2/yquake2) | Quake II |  |
| [OpenRCT2/OpenRCT2](https://github.com/OpenRCT2/OpenRCT2) | RollerCoaster Tycoon 2 engine |  |
| [OpenTTD/OpenTTD](https://github.com/OpenTTD/OpenTTD) | transport sim |  |
| [luanti-org/luanti](https://github.com/luanti-org/luanti) | voxel engine |  |
| [minetest/minetest](https://github.com/minetest/minetest) | voxel engine (old name) |  |

## MAKE

### 3D printing, CNC & laser (`make.fabrication`)

**Fused capability:** Run fabrication from the Node: Klipper speed + Moonraker API + Mainsail/Fluidd UI + AI failure detection.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [prusa3d/PrusaSlicer](https://github.com/prusa3d/PrusaSlicer) | slicer |  |
| [Klipper3d/klipper](https://github.com/Klipper3d/klipper) | high-speed printer firmware |  |
| [DangerKlippers/danger-klipper](https://github.com/DangerKlippers/danger-klipper) | Klipper fork |  |
| [KalicoCrew/kalico](https://github.com/KalicoCrew/kalico) | Klipper fork (Kalico) |  |
| [Arksine/moonraker](https://github.com/Arksine/moonraker) | Klipper API |  |
| [mainsail-crew/mainsail](https://github.com/mainsail-crew/mainsail) | Klipper web UI |  |
| [fluidd-core/fluidd](https://github.com/fluidd-core/fluidd) | Klipper web UI |  |
| [mainsail-crew/crowsnest](https://github.com/mainsail-crew/crowsnest) | printer webcams |  |
| [mainsail-crew/sonar](https://github.com/mainsail-crew/sonar) | WiFi keepalive |  |
| [jordanruthe/KlipperScreen](https://github.com/jordanruthe/KlipperScreen) | touchscreen UI |  |
| [KlipperScreen/KlipperScreen](https://github.com/KlipperScreen/KlipperScreen) | KlipperScreen (current) |  |
| [dw-0/kiauh](https://github.com/dw-0/kiauh) | Klipper installer |  |
| [Frix-x/klippain-shaketune](https://github.com/Frix-x/klippain-shaketune) | resonance tuning |  |
| [kyleisah/Klipper-Adaptive-Meshing-Purging](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging) | adaptive mesh |  |
| [Donkie/Spoolman](https://github.com/Donkie/Spoolman) | filament inventory |  |
| [OctoPrint/OctoPrint](https://github.com/OctoPrint/OctoPrint) | printer host |  |
| [OctoPrint/OctoPi-UpToDate](https://github.com/OctoPrint/OctoPi-UpToDate) | current OctoPi builds |  |
| [OctoPrint/octoprint-docker](https://github.com/OctoPrint/octoprint-docker) | OctoPrint container |  |
| [TheSpaghettiDetective/obico-server](https://github.com/TheSpaghettiDetective/obico-server) | AI print-failure detection |  |
| [MarlinFirmware/Marlin](https://github.com/MarlinFirmware/Marlin) | printer firmware |  |
| [SoftFever/OrcaSlicer](https://github.com/SoftFever/OrcaSlicer) | slicer |  |
| [Ultimaker/Cura](https://github.com/Ultimaker/Cura) | slicer |  |
| [gnea/grbl](https://github.com/gnea/grbl) | CNC firmware |  |
| [grblHAL/core](https://github.com/grblHAL/core) | modern CNC firmware |  |
| [LinuxCNC/linuxcnc](https://github.com/LinuxCNC/linuxcnc) | real-time CNC control |  |
| [cncjs/cncjs](https://github.com/cncjs/cncjs) | CNC web UI |  |
| [vlachoudis/bCNC](https://github.com/vlachoudis/bCNC) | CNC sender |  |

### Astronomy (`make.astro`)

**Fused capability:** Telescope control and astrophotography from the Node.

**Realised in:** catalog only

| Project | Best capability taken | Pinned |
|---|---|---|
| [indilib/indi](https://github.com/indilib/indi) | device control protocol |  |
| [indilib/indi-3rdparty](https://github.com/indilib/indi-3rdparty) | INDI drivers |  |
| [aaronwmorris/indi-allsky](https://github.com/aaronwmorris/indi-allsky) | all-sky camera via INDI |  |
| [KDE/kstars](https://github.com/KDE/kstars) | planetarium + Ekos |  |
| [Stellarium/stellarium](https://github.com/Stellarium/stellarium) | planetarium |  |
| [OpenPHDGuiding/phd2](https://github.com/OpenPHDGuiding/phd2) | autoguiding |  |
| [pchev/ccdciel](https://github.com/pchev/ccdciel) | capture software |  |
| [dstndstn/astrometry.net](https://github.com/dstndstn/astrometry.net) | plate solving |  |
| [astropy/astropy](https://github.com/astropy/astropy) | astronomy Python |  |
| [OpenAstroTech/OpenAstroTracker-Firmware](https://github.com/OpenAstroTech/OpenAstroTracker-Firmware) | DIY tracker firmware |  |
