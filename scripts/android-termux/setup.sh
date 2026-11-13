#!/data/data/com.termux/files/usr/bin/bash
# Aureon toolbox for Android via Termux (install Termux from F-Droid, not Play Store). No root needed.
set -e
pkg update -y
pkg install -y git python openssh nmap tor wireguard-tools radare2 btop neovim tmux \
               clang cmake rclone syncthing yara
pip install --upgrade holehe sherlock-project

# Offline LLM on the phone (llama.cpp). 3-4B GGUF models run on 8GB phones.
if [ ! -d ~/llama.cpp ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/llama.cpp
  cmake -S ~/llama.cpp -B ~/llama.cpp/build -DGGML_NATIVE=ON
  cmake --build ~/llama.cpp/build -j"$(nproc)" --target llama-cli llama-server
fi

cat <<'EOF'

Aureon Termux toolbox installed.
  nmap -sn 192.168.1.0/24                 # what is on this WiFi with you?
  tor &                                    # local SOCKS on 127.0.0.1:9050
  ~/llama.cpp/build/bin/llama-server -m model.gguf   # offline assistant at :8080
  holehe you@example.com                   # where is YOUR email registered
Spyware scanning (MVT) runs from the laptop over ADB: see docs/PHONE.md
EOF
