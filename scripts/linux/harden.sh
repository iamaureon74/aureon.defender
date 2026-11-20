#!/usr/bin/env bash
# Aureon Linux laptop hardening. Dry-run by default; prints what it would do.
#   ./harden.sh                    show plan for all modules
#   sudo ./harden.sh --apply all   apply everything
#   sudo ./harden.sh --apply firewall ips sysctl av dns
set -euo pipefail

APPLY=0; MODS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    all) MODS=(firewall ips sysctl av dns) ;;
    *) MODS+=("$1") ;;
  esac; shift
done
[ ${#MODS[@]} -eq 0 ] && MODS=(firewall ips sysctl av dns)

run() { if [ $APPLY -eq 1 ]; then echo "+ $*"; eval "$@"; else echo "would run: $*"; fi; }

if command -v apt-get >/dev/null; then PKG="apt-get install -y"
elif command -v dnf >/dev/null; then PKG="dnf install -y"
elif command -v pacman >/dev/null; then PKG="pacman -S --noconfirm --needed"
elif command -v zypper >/dev/null; then PKG="zypper install -y"
else echo "unsupported package manager"; exit 1; fi
[ $APPLY -eq 1 ] && [ "$(id -u)" -ne 0 ] && { echo "--apply needs root"; exit 1; }

for m in "${MODS[@]}"; do
  echo "== $m"
  case "$m" in
    firewall)
      run "$PKG ufw"
      run "ufw default deny incoming"
      run "ufw default allow outgoing"
      run "ufw allow in on wg0 2>/dev/null || true"
      run "ufw --force enable"
      echo "   optional per-app outbound control: install OpenSnitch (evilsocket/opensnitch) from its releases"
      ;;
    ips)
      run "$PKG fail2ban"
      run "systemctl enable --now fail2ban"
      echo "   CrowdSec: see https://doc.crowdsec.net (adds repo, then: $PKG crowdsec crowdsec-firewall-bouncer-nftables)"
      ;;
    sysctl)
      run "cat > /etc/sysctl.d/90-aureon.conf <<'EOF'
kernel.kptr_restrict=2
kernel.dmesg_restrict=1
kernel.unprivileged_bpf_disabled=1
net.core.bpf_jit_harden=2
kernel.yama.ptrace_scope=1
kernel.kexec_load_disabled=1
net.ipv4.tcp_syncookies=1
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.conf.all.accept_redirects=0
net.ipv6.conf.all.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.all.accept_source_route=0
net.ipv4.icmp_echo_ignore_broadcasts=1
fs.protected_symlinks=1
fs.protected_hardlinks=1
fs.protected_fifos=2
fs.protected_regular=2
fs.suid_dumpable=0
EOF"
      run "sysctl --system >/dev/null"
      ;;
    av)
      run "$PKG clamav yara"
      run "systemctl enable --now clamav-freshclam 2>/dev/null || freshclam"
      echo "   weekly scan: clamscan -ri --exclude-dir='^/(proc|sys|dev)' /home"
      ;;
    dns)
      run "$PKG unbound"
      run "systemctl enable --now unbound"
      echo "   then point resolv.conf / NetworkManager DNS at 127.0.0.1, or at your Aureon Node"
      ;;
    *) echo "unknown module $m" ;;
  esac
done
[ $APPLY -eq 0 ] && echo "(dry run - add --apply to make changes)"
command -v lynis >/dev/null && echo "Next: sudo lynis audit system" || echo "Next: $PKG lynis && sudo lynis audit system"
