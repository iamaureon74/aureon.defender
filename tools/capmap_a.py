"""Capability map part A: every catalog project -> its best capability -> one Aureon capability.

Format per capability: (id, domain, name, fused, realised, members)
  fused    - what Aureon gets by combining the members' best features
  realised - where it lives in Aureon (module / deploy stack / profile / catalog-only)
  members  - "owner/repo: best capability" lines
"""

CAPS_A = [
("system.image", "SYSTEM", "Aureon OS image factory",
 "One pipeline that builds signed, minimal, reproducible images for Node, laptop and phone: pi-gen stages + Buildroot minimalism + Yocto layers + Nix reproducibility + first-boot automation + safe flashing.",
 "tools/ (planned: images/), profile node step 1",
 """
Drewsif/PiShrink: shrink images to minimum size, auto-expand on boot
archlinuxarm/PKGBUILDs: Arch Linux ARM package recipes
raspberrypi/pi-gen-micro: tiny initramfs-style images
raspberrypi/rpi-image-gen: declarative YAML image layers
RPi-Distro/pi-gen: staged Debian image build
guysoft/CustomPiOS: distro-from-modules framework
buildroot/buildroot: minimal read-only embedded rootfs
agherzan/meta-raspberrypi: Yocto BSP layer
balena-os/meta-balena: OTA-updatable container OS layer
balena-os/balena-raspberrypi: device-specific Yocto integration
armbian/build: one build system for hundreds of ARM boards
void-linux/void-mklive: live/installer ISO creation
void-linux/void-packages: clean cross-compiling package templates
NixOS/nixos-hardware: per-device hardware quirks as code
nvmd/nixos-raspberrypi: Nix flakes for Pi boards
hypriot/image-builder-rpi: container-ready image recipe
TOLDOTECHNIK/buildroot-webkit: kiosk browser appliance image
sakaki-/gentoo-on-rpi-64bit: source-optimised 64-bit userland
manjaro-arm/rpi4-images: rolling-release ARM images
android-rpi/local_manifests: AOSP device manifests
lineage-rpi/android_local_manifest: LineageOS device tree layout
openfyde/overlay-rpi4-openfyde: ChromiumOS board overlay
FydeOS/chromium_os-raspberry_pi: verified-boot ChromiumOS build
nmcclain/raspberian-firstboot: run-once first-boot script hook
davidferguson/pibakery: visual block-based image customisation
seamusdemora/RonR-RPi-image-utils: shrink/backup running images
raspberrypi/rpi-imager: verified image download + OS customisation
balena-io/etcher: validated flashing that refuses system disks
hypriot/flash: one-command flash with cloud-init
raspberrypi/noobs: multi-OS boot menu installer
raspberrypi/scriptexecutor: scripted provisioning during boot
"""),

("system.firmware", "SYSTEM", "Firmware, boot & secure-boot chain",
 "A verified boot chain: signed EEPROM/bootloader + UEFI for standard OSes + USB recovery + kernel/userland tooling, with key provisioning done once at the factory step.",
 "profile node; catalog base layer",
 """
raspberrypi/firmware: GPU firmware + boot blobs
raspberrypi/rpi-firmware: packaged firmware updates
RPi-Distro/firmware: Debian-packaged firmware
raspberrypi/rpi-eeprom: updatable signed bootloader EEPROM
raspberrypi/rpi-sb-provisioner: secure-boot key provisioning at scale
raspberrypi/usbboot: USB device boot / recovery
raspberrypi/rpi-update: bleeding-edge kernel/firmware fetch
pftf/RPi3: UEFI firmware for Pi 3
pftf/RPi4: UEFI firmware for Pi 4 (boots generic ARM distros)
worproject/rpi5-uefi: UEFI firmware for Pi 5
raspberrypi/linux: maintained ARM kernel with board drivers
raspberrypi/userland: VideoCore userspace libraries
raspberrypi/utils: vcgencmd/pinctrl/eeprom tools
raspberrypi/tools: cross-compilation toolchains
RPi-Distro/raspberrypi-sys-mods: system tweaks/udev rules
RPi-Distro/raspi-config: one-screen system configuration
raspberrypi/rc_gui: GUI system configuration
raspberrypi/rpi-keyboard-config: keyboard firmware configuration
raspberrypi/hats: HAT EEPROM identification spec
raspberrypi/pico-bootrom-rp2040: RP2040 mask-ROM bootloader source
raspberrypi/pico-bootrom-rp2350: RP2350 secure-boot ROM source
"""),

("system.appliance", "SYSTEM", "Appliance OS personalities",
 "Aureon Node can take any of these single-purpose personalities (router, NAS, media, home hub, node box) while keeping the Aureon shield underneath; the best idea taken from each is the one-click appliance UX.",
 "deploy/* stacks; profile node",
 """
Itai-Nelken/PiApps-terminal_bash-edition: terminal app store
jmcerrejon/PiKISS: one-menu installer for hundreds of apps
jiangcuo/Proxmox-Port: Proxmox VE ported to ARM64
MichaIng/DietPi: optimised minimal Debian + software menu
openwrt/openwrt: router firmware with package system
home-assistant/operating-system: appliance OS with supervisor + OTA
LibreELEC/LibreELEC.tv: just-enough-OS for media
osmc/osmc: polished media appliance
libretro/Lakka-LibreELEC: console-like gaming appliance
batocera-linux/batocera.linux: plug-and-play retro gaming OS
RetroPie/RetroPie-Setup: script-built emulation station
moode-player/moode: audiophile player appliance
volumio/Build: music appliance image build
volumio/volumio3-os: music OS base
hifiberry/hifiberry-os: DSP audio appliance
motioneye-project/motioneyeos: camera NVR appliance
guysoft/OctoPi: 3D-printer host appliance
mainsail-crew/MainsailOS: Klipper printer appliance
guysoft/FullPageOS: boot-to-fullscreen-browser kiosk
getumbrel/umbrel: home-server app store OS
IceWhaleTech/CasaOS: friendly personal-cloud dashboard
IceWhaleTech/ZimaOS: NAS-focused personal cloud OS
YunoHost/yunohost: self-hosting OS with SSO and app catalog
nextcloud/nextcloudpi: Nextcloud appliance with auto-config
openmediavault/openmediavault: NAS web management
OpenMediaVault-Plugin-Developers/installScript: OMV install on existing OS
openhab/openhabian: home-automation appliance
homebridge/homebridge-raspbian-image: HomeKit bridge appliance
colloqi/piSignage: digital-signage player
colloqi/pisignage-server: signage fleet server
Screenly/Anthias: open digital signage
Start9Labs/start-os: sovereign personal server OS
Start9Labs/embassy-os: earlier Start9 server OS
mynodebtc/mynode: Bitcoin/Lightning node appliance
raspiblitz/raspiblitz: Lightning node appliance
rootzoll/raspiblitz: Lightning node (original repo)
raspibolt/raspibolt: hand-built hardened Bitcoin node guide
PiRogueToolSuite/pirogue-os: mobile-forensics appliance
PiRogueToolSuite/deb-packages: PiRogue packaging
BlackArch/blackarch: 2800+ security tools repo
jiangcuo/pxvirt: Proxmox VE on ARM
pimox/pimox7: Proxmox 7 on Pi
evilsocket/pwnagotchi: autonomous WiFi-learning pet (audit)
jayofelony/pwnagotchi: maintained pwnagotchi fork
infinition/Bjorn: autonomous network audit appliance
AllskyTeam/allsky: all-sky camera appliance
thomasjacquin/allsky: all-sky camera (original)
rlancaste/AstroPi3: astrophotography setup script
billw2/rpi-clone: live clone to a new disk
framps/raspiBackup: scheduled full-system backups
Botspot/pi-apps: curated ARM app store
"""),

("system.research-os", "SYSTEM", "Alternative & research kernels",
 "Ideas Aureon borrows for hardening: Plan 9 per-process namespaces, OpenBSD pledge/unveil minimalism, capability-style isolation, bare-metal tiny trusted computing bases for the Key.",
 "docs/ARCHITECTURE.md (design references); key/",
 """
9front/9front: per-process namespaces, everything-is-a-file
plan9foundation/plan9: original Plan 9 distributed OS
inferno-os/inferno-os: portable VM-based distributed OS
haiku/haiku: responsive single-user desktop OS
freebsd/freebsd-src: jails + Capsicum capabilities
NetBSD/src: maximally portable BSD
openbsd/src: pledge/unveil, secure-by-default
rsta2/circle: bare-metal C++ environment
ultibohub/Core: bare-metal Pascal unikernel
ultibohub/FPC: Free Pascal for Ultibo
RT-Thread/rt-thread: IoT RTOS with rich components
rust-embedded/rust-raspberrypi-OS-tutorials: memory-safe kernel in Rust
s-matyukevich/raspberry-pi-os: Linux-like kernel teaching OS
bztsrc/raspi3-tutorial: bare-metal peripherals tutorial
dwelch67/raspberrypi: bare-metal examples
dwelch67/raspberrypi-three: bare-metal Pi 3 examples
mrvn/RaspberryPi-baremetal: minimal bare-metal kernel
jncronin/rpi-boot: multiboot-style loader
ms-iot/samples: Windows IoT samples
"""),

("system.knowledge", "LEARN", "Platform knowledge base",
 "Searchable offline docs + known-issue trackers fed into the local AI (RAG) so the assistant answers hardware questions without the internet.",
 "deploy/offgrid kiwix + deploy/ai open-webui documents",
 """
Gadgetoid/Pinout.xyz: interactive GPIO pinout reference
pinout-xyz/Pinout.xyz: Pinout.xyz (current home)
raspberrypi/documentation: official hardware/software documentation
raspberrypi/bookworm-feedback: known issues for Bookworm
raspberrypi/trixie-feedback: known issues for Trixie
raspberrypi/pico-feedback: known Pico issues
"""),

("hardware.camera", "HARDWARE", "Camera & vision capture",
 "Low-latency camera capture with hardware ISP feeding Aureon's AI presence detection and NVR.",
 "deploy (Frigate in EXTENSIONS); ai layer",
 """
raspberrypi/libcamera: modern camera stack
raspberrypi/libpisp: Pi 5 ISP back-end
raspberrypi/picamera2: Python camera API
raspberrypi/rpicam-apps: camera CLI apps
raspberrypi/imx500-models: on-sensor AI camera models
"""),

("hardware.io", "HARDWARE", "GPIO, sensors & displays",
 "One HAL for buttons, tamper switches, sensors, LEDs and small screens on the Node and Key: libgpiod for correctness, gpiozero for simplicity, luma/e-paper for status screens.",
 "key/firmware (GP14/GP15); Node status display (planned)",
 """
PiSupply/PiJuice: battery UPS HAT - Node survives power cuts and shuts down cleanly
RaspberryPiFoundation/python-build-hat: LEGO motor/sensor HAT
RPi-Distro/python-gpiozero: packaged gpiozero
raspberrypi/rpi-sense: Sense HAT driver
adafruit/Adafruit_Blinka: CircuitPython APIs on Linux
adafruit/Adafruit_CircuitPython_Bundle: hundreds of sensor drivers
adafruit/Adafruit_CircuitPython_DHT: DHT temperature/humidity
adafruit/Adafruit_Python_DHT: legacy DHT driver
adafruit/Raspberry-Pi-Installer-Scripts: one-line HAT installers
astro-pi/python-sense-hat: Sense HAT Python API
brgl/libgpiod: correct kernel GPIO character-device access
dotnet/iot: .NET device bindings
fivdi/onoff: Node.js GPIO with interrupts
fivdi/pigpio: Node.js pigpio wrapper
geerlingguy/raspberry-pi-pcie-devices: tested PCIe device database
golemparts/rppal: Rust peripheral access
goodtft/LCD-show: SPI LCD drivers
gpiozero/gpiozero: simplest device-oriented GPIO API
hzeller/rpi-rgb-led-matrix: fast LED matrix driving
jgarff/rpi_ws281x: DMA-driven addressable LEDs
joan2937/lg: GPIO for Pi 5 (RP1)
joan2937/pigpio: hardware-timed PWM/servo/waveforms
juj/fbcp-ili9341: high-fps SPI display driver
nebrius/raspi-io: Johnny-Five IO plugin
notro/fbtft: framebuffer for small TFTs
periph/host: Go peripheral drivers
pi4j/pi4j-v2: Java GPIO
pimoroni/bme280-python: environment sensor
pimoroni/displayhatmini-python: small IPS display HAT
pimoroni/enviroplus-python: air-quality monitoring
pimoroni/fanshim-python: temperature-driven fan control
pimoroni/inky: e-paper status displays
pimoroni/st7789-python: SPI LCD driver
pimoroni/unicornhatmini-python: RGB LED matrix
rm-hull/luma.led_matrix: LED matrix text/graphics
rm-hull/luma.oled: OLED status displays
rpi-ws281x/rpi-ws281x-python: Python addressable LEDs
rwaldron/johnny-five: JS robotics/IoT framework
stianeikeland/go-rpio: Go GPIO via /dev/mem
tasanakorn/rpi-fbcp: framebuffer mirroring
Tieske/rpi-gpio: Lua GPIO
waveshareteam/e-Paper: e-paper drivers
WiringPi/WiringPi: classic C GPIO library
"""),

("hardware.key", "HARDWARE", "Aureon Key microcontroller platform",
 "The Key firmware stack: pico-sdk + TinyUSB for USB identity, Embassy/rp-hal for memory-safe Rust, Zephyr for crypto/secure boot, MicroPython for rapid features, Wokwi for CI simulation.",
 "key/firmware/main.py (built); aureon/keyagent.py, aureon/hidguard.py (built)",
 """
Wren6991/PicoDVI: DVI video out from RP2040
sekigon-gonnoc/Pico-PIO-USB: USB host via PIO - lets a future Key sit inline as a USB firewall
adafruit/circuitpython: USB-drive-editable firmware
arduino/ArduinoCore-mbed: Arduino on RP2040 via mbed
carlk3/no-OS-FatFS-SD-SPI-RPi-Pico: SD card logging without an OS
dhylands/rshell: remote shell to MicroPython boards
earlephilhower/arduino-pico: fast Arduino core for RP2040/RP2350
embassy-rs/embassy: async memory-safe Rust firmware
FreeRTOS/FreeRTOS-Kernel: SMP real-time kernel
hathach/tinyusb: USB device/host stack (HID, CDC, MSC)
micropython/micropython: Python on microcontrollers
micropython/micropython-lib: MicroPython packages
pimoroni/pico-boilerplate: project template
pimoroni/pimoroni-pico: drivers for Pico add-ons
raspberrypi/debugprobe: SWD/UART debug probe firmware
raspberrypi/openocd: on-chip debugging
raspberrypi/pico-examples: reference code for every peripheral
raspberrypi/pico-extras: extra audio/sleep/scanvideo libs
raspberrypi/pico-micropython-examples: MicroPython examples
raspberrypi/pico-playground: experimental demos
raspberrypi/pico-sdk: official C SDK
raspberrypi/pico-setup: toolchain setup
raspberrypi/pico-setup-windows: Windows toolchain installer
raspberrypi/pico-vscode: VS Code integration
raspberrypi/picotool: flash/inspect/sign binaries
rp-rs/rp-hal: Rust HAL
tinygo-org/tinygo: Go on microcontrollers
wokwi/rp2040js: RP2040 emulator for CI
zephyrproject-rtos/zephyr: RTOS with crypto + MCUboot secure boot
dbisu/pico-ducky: HID injection - studied to build the detector
"""),
]
