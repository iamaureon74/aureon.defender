#!/usr/bin/env bash
# Aureon Linux performance tuning. Dry-run by default.
#   sudo ./perf.sh --apply
set -euo pipefail
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
run() { if [ $APPLY -eq 1 ]; then echo "+ $*"; eval "$@"; else echo "would run: $*"; fi; }
[ $APPLY -eq 1 ] && [ "$(id -u)" -ne 0 ] && { echo "--apply needs root"; exit 1; }

RAM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
echo "RAM: ${RAM_MB} MB"

echo "== zram (compressed RAM swap: more usable memory, less SSD wear)"
if command -v apt-get >/dev/null; then run "apt-get install -y zram-tools"
  run "printf 'ALGO=zstd\nPERCENT=50\n' > /etc/default/zramswap && systemctl restart zramswap"
else echo "   install zram-generator and set zram-size = ram / 2, compression-algorithm = zstd"; fi
run "printf 'vm.swappiness=100\nvm.page-cluster=0\nvm.vfs_cache_pressure=50\n' > /etc/sysctl.d/91-aureon-perf.conf && sysctl --system >/dev/null"

echo "== CPU power profile"
if command -v powerprofilesctl >/dev/null; then
  echo "   on AC: powerprofilesctl set performance ; on battery: balanced"
else
  echo "   install power-profiles-daemon (or tuned / TLP - pick one, not several)"
fi

echo "== I/O scheduler"
for d in /sys/block/nvme*n1 /sys/block/sd?; do
  [ -e "$d/queue/scheduler" ] || continue
  echo "   $(basename "$d"): $(cat "$d/queue/scheduler")  (nvme: none, sata ssd: mq-deadline)"
done

echo "== SSD TRIM"
run "systemctl enable --now fstrim.timer"

echo "== Faster boot: show the slowest units"
command -v systemd-analyze >/dev/null && systemd-analyze blame | head -8 || true

case "$(uname -m)" in
  aarch64) echo "== ARM laptop: install FEX-Emu for x86 apps, box64 for x86_64 CLI tools" ;;
esac
[ $APPLY -eq 0 ] && echo "(dry run - add --apply to make changes)"
