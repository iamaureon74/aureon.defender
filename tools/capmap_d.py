"""Capability map part D (see capmap_a.py for format)."""

CAPS_D = [
("home.automation", "HOME", "Device automation & presence",
 "Aureon reacts to the physical world: Home Assistant automations, Zigbee/Z-Wave without vendor clouds, MQTT bus, Node-RED flows - e.g. lock laptops when you leave, alert on door sensors.",
 "catalog cloud layer (home-assistant)",
 """
home-assistant/core: home automation engine
home-assistant/frontend: HA UI
home-assistant/addons: HA add-ons
home-assistant/supervised-installer: HA supervised install
openhab/openhab-core: openHAB engine
openhab/openhab-distro: openHAB distribution
domoticz/domoticz: light home automation
ioBroker/ioBroker: integration platform
nymea/nymea: IoT edge server
homebridge/homebridge: HomeKit for anything
homebridge/homebridge-config-ui-x: Homebridge UI
node-red/node-red: flow-based wiring
node-red/node-red-nodes: extra nodes
node-red/linux-installers: Node-RED installer
node-red/raspbian-deb-package: Node-RED packaging
Koenkk/zigbee2mqtt: Zigbee without vendor hubs
zigbee2mqtt/hassio-zigbee2mqtt: Z2M HA add-on
zwave-js/node-zwave-js: Z-Wave driver
zwave-js/zwave-js-ui: Z-Wave control panel
eclipse-mosquitto/mosquitto: MQTT broker
eclipse/mosquitto: Mosquitto (old home)
emqx/emqx: scalable MQTT broker
esphome/esphome: YAML firmware for ESP sensors
arendst/Tasmota: open firmware for smart plugs
mysensors/MySensors: DIY wireless sensors
thingsboard/thingsboard: IoT platform
weewx/weewx: weather station
MagicMirrorOrg/MagicMirror: smart mirror
MichMich/MagicMirror: MagicMirror (old home)
sdetweil/MagicMirror_scripts: MagicMirror install scripts
"""),

("radio.sdr", "RADIO", "Software-defined radio core",
 "Hear the spectrum: one SDR abstraction (SoapySDR) over RTL-SDR/HackRF/bladeRF, DSP (GNU Radio, liquid-dsp), receivers and protocol reverse engineering - powering Aureon's RF watch.",
 "aureon rf gsm consumes kalibrate-rtl output (built)",
 """
osmocom/rtl-sdr: RTL2832U SDR driver
rtlsdrblog/rtl-sdr-blog: improved RTL-SDR driver
greatscottgadgets/hackrf: HackRF tools/firmware
Nuand/bladeRF: bladeRF tools
pothosware/SoapySDR: SDR abstraction
gnuradio/gnuradio: signal processing framework
jgaeddert/liquid-dsp: DSP library
AlexandreRouma/SDRPlusPlus: SDR receiver
gqrx-sdr/gqrx: SDR receiver
f4exb/sdrangel: SDR receiver/transmitter suite
jketterl/openwebrx: web SDR receiver
luarvique/openwebrx: OpenWebRX+ fork
miek/inspectrum: signal analysis
jopohl/urh: wireless protocol reverse engineering
merbanan/rtl_433: decode 433/868 MHz devices (find hidden transmitters)
EliasOenal/multimon-ng: pager/digital mode decoder
"""),

("radio.aviation-space", "RADIO", "Aviation, weather & space reception",
 "Situational awareness from the sky: aircraft, balloons, satellites - optional Node personality.",
 "catalog only",
 """
antirez/dump1090: ADS-B decoder
flightaware/dump1090: FlightAware dump1090
flightaware/piaware: FlightAware feeder
flightaware/piaware_builder: piaware build
wiedehopf/readsb: ADS-B decoder
wiedehopf/tar1090: aircraft map
wiedehopf/graphs1090: ADS-B statistics
ADSBexchange/adsbx-update: ADSBx feeder
dirkhh/adsb-feeder-image: multi-feeder image
sdr-enthusiasts/docker-adsb-ultrafeeder: containerised feeder
szpajder/dumpvdl2: VDL2 decoder
TLeconte/acarsdec: ACARS decoder
charlie-foxtrot/RTLSDR-Airband: airband audio
szpajder/RTLSDR-Airband: airband (old home)
altillimity/SatDump: satellite decoder
SatDump/SatDump: satellite decoder (current)
dbdexter-dev/meteor_demod: Meteor-M demodulator
projecthorus/radiosonde_auto_rx: weather balloon tracking
projecthorus/horusdemodlib: Horus telemetry
dl9rdz/rdz_ttgo_sonde: radiosonde on ESP32
"""),

("radio.ham", "RADIO", "Amateur radio & emergency comms",
 "Licensed long-range comms when everything else is down: digital voice, Winlink email, WSPR/FT8 propagation, rig control.",
 "catalog only (pairs with network.offgrid)",
 """
AndyTaylorTweet/Pi-Star_DV_Dash: digital-voice hotspot dashboard
ChristopheJacquet/PiFmRds: FM + RDS transmitter (licensed use)
AllStarLink/ASL3: linked repeater network
g4klx/MMDVM: digital voice modem firmware
g4klx/MMDVMHost: digital voice host
Hamlib/Hamlib: rig control
la5nta/pat: Winlink email over radio
kgoba/ft8_lib: FT8 weak-signal mode
Guenael/rtlsdr-wsprd: WSPR receiver
F5OEO/rpitx: GPIO RF transmitter (licensed use)
F5OEO/librpitx: rpitx library
markondej/fm_transmitter: GPIO FM transmitter (licensed use)
"""),

("media.center", "MEDIA", "Media, music & cameras",
 "Own your media and cameras: Jellyfin streaming, multi-room audio, AirPlay/Spotify endpoints, camera NVR, photo sync.",
 "catalog (Immich in deploy/cloud)",
 """
xbmc/xbmc: Kodi media center
jellyfin/jellyfin: media server
jellyfin/jellyfin-web: Jellyfin UI
navidrome/navidrome: music streaming server
MusicPlayerDaemon/MPD: music daemon
mopidy/mopidy: extensible music server
jaedb/Iris: Mopidy UI
LMS-Community/slimserver: Lyrion music server
ralph-irving/squeezelite: Squeezebox player
owntone/owntone-server: AirPlay/Remote server
badaix/snapcast: synchronous multi-room audio
mikebrady/shairport-sync: AirPlay receiver
dtcooper/raspotify: Spotify Connect
librespot-org/librespot: open Spotify client
spocon/spocon: Spotify Connect daemon
Arkq/bluez-alsa: Bluetooth audio
balena-io-experimental/balena-sound: multi-room audio (old)
balena-labs-projects/balena-sound: multi-room audio
volumio/Volumio2: music player
volumio/volumio3-backend: Volumio backend
MiczFlor/RPi-Jukebox-RFID: RFID jukebox
mpv-player/mpv: GPU-accelerated player
popcornmix/omxplayer: legacy HW player
sonic-pi-net/sonic-pi: live-coded music
bluenviron/mediamtx: universal media server (RTSP/WebRTC)
aler9/rtsp-simple-server: mediamtx (old name)
AlexxIT/go2rtc: camera streaming hub
ayufan/camera-streamer: low-latency Pi camera streaming
jacksonliam/mjpg-streamer: MJPEG streaming
Motion-Project/motion: motion detection
motioneye-project/motioneye: camera web UI
ccrisan/motioneye: motionEye (old home)
kerberos-io/agent: video surveillance agent
ZoneMinder/zoneminder: full NVR
silvanmelchior/RPi_Cam_Web_Interface: Pi camera web UI
"""),

("media.play", "MEDIA", "Gaming & emulation",
 "Turn idle hardware into a console: RetroArch cores, standalone emulators, source ports.",
 "catalog only",
 """
libretro/RetroArch: unified emulator frontend
libretro/libretro-super: build all cores
libretro/beetle-psx-libretro: accurate PS1
libretro/fbneo: arcade
libretro/mame: MAME core
libretro/mupen64plus-libretro-nx: N64 core
libretro/pcsx_rearmed: fast PS1 on ARM
libretro/snes9x: SNES
Aloshi/EmulationStation: game launcher UI
RetroPie/EmulationStation: RetroPie launcher
batocera-linux/batocera-emulationstation: Batocera launcher
BlitterStudio/amiberry: Amiga
midwan/amiberry: Amiberry (old home)
dolphin-emu/dolphin: GameCube/Wii
PCSX2/pcsx2: PS2
hrydgard/ppsspp: PSP
flyinghead/flycast: Dreamcast
mupen64plus/mupen64plus-core: N64
DOSBox-Staging/dosbox-staging: DOS
scummvm/scummvm: adventure games
chocolate-doom/chocolate-doom: faithful Doom
fabiangreffrath/crispy-doom: enhanced Doom
ioquake/ioq3: Quake III
Novum/vkQuake: Vulkan Quake
yquake2/yquake2: Quake II
OpenRCT2/OpenRCT2: RollerCoaster Tycoon 2 engine
OpenTTD/OpenTTD: transport sim
luanti-org/luanti: voxel engine
minetest/minetest: voxel engine (old name)
"""),

("make.fabrication", "MAKE", "3D printing, CNC & laser",
 "Run fabrication from the Node: Klipper speed + Moonraker API + Mainsail/Fluidd UI + AI failure detection.",
 "catalog only",
 """
prusa3d/PrusaSlicer: slicer
Klipper3d/klipper: high-speed printer firmware
DangerKlippers/danger-klipper: Klipper fork
KalicoCrew/kalico: Klipper fork (Kalico)
Arksine/moonraker: Klipper API
mainsail-crew/mainsail: Klipper web UI
fluidd-core/fluidd: Klipper web UI
mainsail-crew/crowsnest: printer webcams
mainsail-crew/sonar: WiFi keepalive
jordanruthe/KlipperScreen: touchscreen UI
KlipperScreen/KlipperScreen: KlipperScreen (current)
dw-0/kiauh: Klipper installer
Frix-x/klippain-shaketune: resonance tuning
kyleisah/Klipper-Adaptive-Meshing-Purging: adaptive mesh
Donkie/Spoolman: filament inventory
OctoPrint/OctoPrint: printer host
OctoPrint/OctoPi-UpToDate: current OctoPi builds
OctoPrint/octoprint-docker: OctoPrint container
TheSpaghettiDetective/obico-server: AI print-failure detection
MarlinFirmware/Marlin: printer firmware
SoftFever/OrcaSlicer: slicer
Ultimaker/Cura: slicer
gnea/grbl: CNC firmware
grblHAL/core: modern CNC firmware
LinuxCNC/linuxcnc: real-time CNC control
cncjs/cncjs: CNC web UI
vlachoudis/bCNC: CNC sender
"""),

("make.astro", "MAKE", "Astronomy",
 "Telescope control and astrophotography from the Node.",
 "catalog only",
 """
indilib/indi: device control protocol
indilib/indi-3rdparty: INDI drivers
aaronwmorris/indi-allsky: all-sky camera via INDI
KDE/kstars: planetarium + Ekos
Stellarium/stellarium: planetarium
OpenPHDGuiding/phd2: autoguiding
pchev/ccdciel: capture software
dstndstn/astrometry.net: plate solving
astropy/astropy: astronomy Python
OpenAstroTech/OpenAstroTracker-Firmware: DIY tracker firmware
"""),

("learn.code", "LEARN", "Learning & creating",
 "Teach and build on the platform: block coding, beginner IDEs, offline school content, office suite.",
 "catalog only (Kolibri pairs with offline Kiwix)",
 """
arduino/arduino-cli: Arduino builds from CLI
arduino/arduino-ide: Arduino IDE
astro-pi/python-sense-emu: Sense HAT emulator
RPi-Distro/python-sense-emu: packaged emulator
fritzing/fritzing-app: circuit design
google/blockly: block programming
KDE/gcompris: kids education suite
learningequality/kolibri: offline learning platform
kiwix/kiwix-tools: offline Wikipedia server
kiwix/kiwix-hotspot: offline content hotspot
iiab/iiab: Internet-in-a-Box offline library
LibreOffice/core: office suite
lordmauve/pgzero: zero-boilerplate games
martinohanlon/mcpi: Minecraft Pi API
martinohanlon/minecraft-stuff: Minecraft helpers
microsoft/pxt: MakeCode
microsoft/pxt-microbit: MakeCode micro:bit
mu-editor/mu: beginner Python editor
processing/processing4: creative coding
pygame-community/pygame-ce: games in Python
pygame/pygame: pygame
RaspberryPiFoundation/editor-api: code editor backend
RaspberryPiFoundation/editor-ui: code editor UI
scratchfoundation/scratch-desktop: Scratch desktop
scratchfoundation/scratch-gui: Scratch UI
thonny/thonny: beginner Python IDE
"""),
]
