"""Capability map part C (see capmap_a.py for format)."""

CAPS_C = [
("freedom.cloud", "FREEDOM", "Personal cloud",
 "Replace Google/Apple/Microsoft services: files, photos, docs, notes, wiki, finance, recipes, RSS - all on the Node, behind Caddy TLS and WireGuard.",
 "deploy/cloud (built): Immich, Nextcloud, Vaultwarden, Caddy",
 """
nextcloud/server: files/calendar/contacts
nextcloud/all-in-one: one-container Nextcloud
owncloud/core: ownCloud file sync
haiwen/seafile: fast block-level file sync
immich-app/immich: phone photo backup with local ML
PhotoPrism/photoprism: AI photo library
paperless-ngx/paperless-ngx: OCR document archive
BookStackApp/BookStack: structured wiki
requarks/wiki: Wiki.js
Jermolene/TiddlyWiki5: single-file notebook
FreshRSS/FreshRSS: RSS reader
miniflux/v2: minimal RSS reader
wallabag/wallabag: read-it-later
mealie-recipes/mealie: recipe manager
actualbudget/actual: local-first budgeting
firefly-iii/firefly-iii: personal finance
filebrowser/filebrowser: web file manager
"""),

("freedom.comms", "FREEDOM", "Own communications",
 "Encrypted chat, video and voice you host: Matrix federation, Jitsi calls, Mumble low-latency voice, community servers.",
 "catalog cloud layer (deploy planned)",
 """
element-hq/synapse: Matrix homeserver
matrix-org/synapse: Synapse (previous home)
jitsi/jitsi-meet: video conferencing
mumble-voip/mumble: low-latency voice
RocketChat/Rocket.Chat: team chat
zulip/zulip: threaded team chat
mastodon/mastodon: federated social
LemmyNet/lemmy: federated forums
"""),

("freedom.web", "FREEDOM", "Web serving & reverse proxy",
 "Caddy's automatic TLS + Traefik's container discovery + Nginx speed; NPM for click-ops.",
 "deploy/cloud Caddyfile (built)",
 """
caddyserver/caddy: automatic HTTPS
traefik/traefik: dynamic container routing
nginx/nginx: high-performance server
apache/httpd: module-rich server
NginxProxyManager/nginx-proxy-manager: GUI reverse proxy
"""),

("freedom.data", "FREEDOM", "Databases",
 "Reliable storage engines behind every Aureon service.",
 "deploy/cloud (postgres, redis)",
 """
postgres/postgres: relational DB with extensions
MariaDB/server: MySQL-compatible DB
redis/redis: in-memory cache/queue
influxdata/influxdb: time-series metrics
"""),

("freedom.business", "FREEDOM", "Business apps",
 "ERP/CRM/accounting if the Node runs a small business.",
 "catalog only",
 """
frappe/erpnext: ERP
odoo/odoo: business suite
"""),

("freedom.dev", "FREEDOM", "Own dev platform",
 "Private git, browser IDE, notebooks, automation - code from phone or laptop against the Node.",
 "catalog cloud layer",
 """
go-gitea/gitea: lightweight git forge
gogs/gogs: minimal git service
coder/code-server: VS Code in browser
VSCodium/vscodium: telemetry-free VS Code
microsoft/vscode: VS Code source
jupyter/notebook: notebooks
jupyterlab/jupyterlab: notebook IDE
n8n-io/n8n: workflow automation
huginn/huginn: agents that watch the web
"""),

("freedom.remote", "PERFORM", "Remote access & rescue",
 "Reach any device from any device: RustDesk remote desktop, Guacamole in a browser, VNC/RDP, plus below-OS rescue via PiKVM/TinyPilot.",
 "aureon rescue (built) for PiKVM; profiles RustDesk",
 """
rustdesk/rustdesk: self-hostable remote desktop
apache/guacamole-server: clientless browser remote desktop
novnc/noVNC: VNC in the browser
TigerVNC/tigervnc: fast VNC
LibVNC/x11vnc: share an existing X display
neutrinolabs/xrdp: RDP server for Linux
pikvm/kvmd: KVM-over-IP daemon (ATX, HID, MSD)
pikvm/os: PiKVM OS
pikvm/pikvm: PiKVM hardware/project
pikvm/ustreamer: low-latency MJPEG streamer
tiny-pilot/tinypilot: simple KVM-over-IP
cockpit-project/cockpit: web Linux admin
webmin/webmin: web system admin
"""),

("freedom.dashboard", "PERFORM", "Dashboards",
 "One start page for every Aureon service.",
 "catalog (homepage planned in deploy)",
 """
gethomepage/homepage: service dashboard with widgets
bastienwirtz/homer: static dashboard
Lissy93/dashy: configurable dashboard
linuxserver/Heimdall: app launcher
"""),

("perform.observe", "PERFORM", "Observability & health",
 "Per-second metrics + ML anomaly detection (Netdata), long-term Prometheus/Grafana, uptime alerts, TUI monitors on every device.",
 "deploy/shield netdata (built); aureon audit perf checks (built)",
 """
netdata/netdata: per-second metrics + anomaly ML
prometheus/prometheus: metrics TSDB + alerting
prometheus/node_exporter: host metrics
grafana/grafana: dashboards
influxdata/telegraf: metrics collection agent
louislam/uptime-kuma: uptime monitoring
nicolargo/glances: cross-platform monitor + API
aristocratos/btop: rich resource TUI
ClementTsang/bottom: cross-platform TUI
htop-dev/htop: process viewer
XavierBerger/RPi-Monitor: Pi health web UI
"""),

("perform.compute", "PERFORM", "Containers, VMs & clusters",
 "Sandbox and scale: rootless Podman, Incus system containers/VMs, k3s clusters across Node + laptops, Ansible to provision all of it.",
 "deploy/* compose (built); ops layer",
 """
containers/podman: rootless containers
moby/moby: Docker engine
docker/compose: multi-container apps
docker/docker-install: Docker install script
lxc/lxc: system containers
lxc/incus: containers + VMs manager
k3s-io/k3s: lightweight Kubernetes
k3s-io/k3s-ansible: k3s via Ansible
kubernetes/kubernetes: Kubernetes
canonical/microk8s: snap Kubernetes
rancher/rancher: cluster management
hashicorp/nomad: simple orchestrator
openfaas/faas: functions as a service
openfaas/faasd: FaaS without Kubernetes
portainer/portainer: container UI
containrrr/watchtower: container auto-update
ansible/ansible: agentless provisioning
geerlingguy/ansible-role-docker_arm: Docker on ARM role
geerlingguy/pi-cluster: Pi cluster playbooks
geerlingguy/raspberry-pi-dramble: Pi Kubernetes cluster
geerlingguy/turing-pi-2-cluster: Turing Pi cluster
alexellis/arkade: Kubernetes app installer
alexellis/k3sup: k3s over SSH
balena-io/balena-cli: fleet deploys
"""),

("perform.compat", "PERFORM", "Run any software anywhere",
 "x86 on ARM (FEX, box64/box86), Windows apps on Linux (Wine, Hangover), GL on mobile GPUs (gl4es), full emulation (QEMU), packaged sandboxes (Flatpak/Snap).",
 "profile laptop-linux steps (built)",
 """
FEX-Emu/FEX: fast x86-64 on ARM64
ptitSeb/box64: x86-64 Linux userspace on ARM64
ptitSeb/box86: x86 Linux userspace on ARM
ptitSeb/gl4es: OpenGL on GLES
wine-mirror/wine: Windows API on Linux
AndreRH/hangover: Windows x86 apps on ARM
qemu/qemu: full-system emulation
dhruvvyas90/qemu-rpi-kernel: Pi kernels for QEMU
carlosperate/docker-qemu-rpi-os: Pi OS in Docker
lukechilds/dockerpi: Pi in a container
flatpak/flatpak: sandboxed desktop apps
snapcore/snapd: confined snap packages
"""),

("perform.desktop", "PERFORM", "Fast, light desktop & UI",
 "Low-RAM Wayland sessions, kiosk lockdown mode, efficient terminal tools, and UI toolkits for Aureon's own screens.",
 "profile laptop-linux (sway/labwc)",
 """
swaywm/sway: tiling Wayland compositor
labwc/labwc: light stacking compositor
WayfireWM/wayfire: 3D compositor that stays light
cage-kiosk/cage: single-app kiosk
lxqt/lxqt: light Qt desktop
lxde/lxpanel: light panel
neovim/neovim: fast extensible editor
vim/vim: ubiquitous editor
tmux/tmux: terminal multiplexer
jesseduffield/lazygit: git TUI
ranger/ranger: TUI file manager
cmus/cmus: TUI music player
geany/geany: light IDE
LVGL/lvgl: embedded GUI library
lvgl/lv_port_linux: LVGL on Linux framebuffer
slint-ui/slint: declarative native UI
ardera/flutter-pi: Flutter without X/Wayland
sony/flutter-elinux: Flutter for embedded Linux
kivy/kivy: Python touch UI
dividuum/info-beamer: GPU-accelerated signage
info-beamer/package-sdk: info-beamer packages
"""),

("perform.stream", "PERFORM", "Game & desktop streaming",
 "Laptop-phone fusion: stream the laptop desktop/games to the phone at low latency.",
 "profiles laptop-windows / phone-android (Sunshine + Moonlight)",
 """
LizardByte/Sunshine: low-latency game/desktop streaming host
moonlight-stream/moonlight-qt: Moonlight desktop/mobile client
moonlight-stream/moonlight-embedded: Moonlight for embedded
"""),

("intel.llm", "INTELLIGENCE", "Local LLM brain",
 "Private assistant + security analyst: llama.cpp efficiency, Ollama model management, Open WebUI chat/RAG, LocalAI OpenAI-compatible API, llamafile portability.",
 "deploy/ai (built), aureon analyst (built)",
 """
ggml-org/llama.cpp: quantised LLM inference everywhere
ollama/ollama: model manager + API
open-webui/open-webui: chat UI + RAG
mudler/LocalAI: OpenAI-compatible local API
Mozilla-Ocho/llamafile: single-file LLM
nomic-ai/gpt4all: desktop local chat
leon-ai/leon: personal assistant framework
"""),

("intel.voice", "INTELLIGENCE", "Offline voice",
 "Wake word -> speech-to-text -> LLM -> text-to-speech fully offline, glued by the Wyoming protocol.",
 "catalog ai layer (voice pipeline planned)",
 """
ggml-org/whisper.cpp: fast offline STT
openai/whisper: accurate STT reference
SYSTRAN/faster-whisper: CTranslate2 STT
alphacep/vosk-api: tiny STT for phones
mozilla/DeepSpeech: legacy STT
rhasspy/piper: fast neural TTS
coqui-ai/TTS: high-quality TTS
dscripka/openWakeWord: open wake words
picovoice/porcupine: efficient wake word
picovoice/picovoice: on-device voice platform
rhasspy/rhasspy: offline voice assistant
rhasspy/rhasspy3: modular voice pipeline
rhasspy/wyoming: voice service protocol
rhasspy/wyoming-faster-whisper: Wyoming STT server
rhasspy/wyoming-openwakeword: Wyoming wake word
rhasspy/wyoming-satellite: remote voice satellites
OpenVoiceOS/ovos-core: open voice assistant
OpenVoiceOS/ovos-installer: OVOS installer
OpenVoiceOS/raspOVOS: OVOS image
MycroftAI/mycroft-core: Mycroft assistant
MycroftAI/enclosure-picroft: Mycroft on Pi
NeonGeckoCom/NeonCore: Neon assistant
kalliope-project/kalliope: modular assistant
alexa/avs-device-sdk: Alexa SDK (reference)
googlesamples/assistant-sdk-python: Google Assistant SDK (reference)
"""),

("intel.vision", "INTELLIGENCE", "Vision & presence",
 "Camera intelligence for physical security: YOLO detection, Frigate NVR, face presence, MediaPipe pose/hands.",
 "EXTENSIONS camera presence; catalog ai layer",
 """
opencv/opencv: computer vision core
opencv/opencv_contrib: extra CV modules
ultralytics/ultralytics: YOLO detection
blakeblackshear/frigate: AI NVR
ageitgey/face_recognition: face recognition
davisking/dlib: face landmarks + ML
google-ai-edge/mediapipe: on-device vision pipelines
EdjeElectronics/TensorFlow-Lite-Object-Detection-on-Android-and-Raspberry-Pi: TFLite detection recipe
edgeimpulse/edge-impulse-linux-cli: edge model deploy
edgeimpulse/linux-sdk-python: edge inference SDK
"""),

("intel.accel", "INTELLIGENCE", "AI acceleration",
 "Use whatever silicon exists: NPUs (Hailo, Intel NPU via OpenVINO), TPUs (Coral), GPUs (Vulkan ncnn), CPUs (ONNX Runtime, LiteRT, TVM).",
 "profile notes; catalog ai layer",
 """
PaddlePaddle/Paddle-Lite: lightweight mobile inference
microsoft/onnxruntime: cross-hardware inference
openvinotoolkit/openvino: Intel CPU/GPU/NPU
google-ai-edge/LiteRT: on-device ML runtime
tensorflow/tensorflow: training + TFLite
pytorch/pytorch: training framework
apache/tvm: model compiler for any target
Tencent/ncnn: Vulkan mobile inference
google-coral/edgetpu: Edge TPU runtime
google-coral/pycoral: Edge TPU Python API
google-coral/tflite: Coral TFLite examples
hailo-ai/hailort: Hailo NPU runtime
hailo-ai/hailort-drivers: Hailo PCIe driver
hailo-ai/tappas: Hailo pipelines
hailo-ai/hailo-apps-infra: Hailo app infra
hailo-ai/hailo-rpi5-examples: Hailo on Pi 5
"""),

("intel.robotics", "INTELLIGENCE", "Robotics & drones",
 "Autonomy stack for future Aureon field units: ROS 2, ArduPilot, MAVLink, long-range video links.",
 "catalog only",
 """
PX4/PX4-Autopilot: professional drone autopilot
ros/ros_comm: ROS 1 communications
ros2/ros2: ROS 2
ros2/rclpy: ROS 2 Python
ArduPilot/ardupilot: autopilot
ArduPilot/MAVProxy: ground station
mavlink/MAVSDK: drone SDK
mavlink-router/mavlink-router: MAVLink routing
OpenHD/OpenHD: long-range HD video link
rodizio1/EZ-WifiBroadcast: WiFi broadcast video
svpcom/wfb-ng: WiFi broadcast next-gen
bluerobotics/BlueOS: underwater vehicle OS
bluerobotics/companion: ROV companion
autorope/donkeycar: self-driving RC car
DexterInd/BrickPi3: LEGO robotics
DexterInd/GoPiGo3: robot car
Freenove/Freenove_4WD_Smart_Car_Kit_for_Raspberry_Pi: robot car kit
PetoiCamp/OpenCat: quadruped robot
sunfounder/picar-x: robot car
sunfounder/robot-hat: robot HAT
"""),
]
