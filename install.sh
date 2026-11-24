#!/usr/bin/env bash
# Install firepro-power to /usr/local and (with --enable) apply it at every boot.
#   sudo ./install.sh [--enable]      sudo ./install.sh --uninstall
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo $0 $*" >&2; exit 1; }
cd "$(dirname "$(readlink -f "$0")")"
if [ "${1:-}" = --uninstall ]; then
    systemctl disable --now firepro-power.service 2>/dev/null || true
    rm -f /usr/local/sbin/firepro-power /etc/systemd/system/firepro-power.service
    rm -rf /usr/local/lib/firepro-power
    systemctl daemon-reload
    echo "removed (kept /etc/default/firepro-power; limits return to stock at the next reboot)"
    exit 0
fi
install -D -m 755 firepro-power /usr/local/sbin/firepro-power
install -D -m 644 pptable.py /usr/local/lib/firepro-power/pptable.py
install -D -m 644 firepro-power.service /etc/systemd/system/firepro-power.service
[ -f /etc/default/firepro-power ] || install -D -m 644 firepro-power.default /etc/default/firepro-power
systemctl daemon-reload
if [ "${1:-}" = --enable ]; then
    systemctl enable firepro-power.service
    echo "installed; settings from /etc/default/firepro-power apply at every boot"
else
    echo "installed; run 'sudo firepro-power set 110' by hand, or 'sudo systemctl enable firepro-power' for every boot"
fi
