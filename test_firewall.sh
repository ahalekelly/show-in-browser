#!/bin/bash
# Run with sudo; network namespaces isolate these checks from the host network.
set -euo pipefail
cd "$(dirname "$0")"
SERVER="report-server-$$"
CLIENT="report-client-$$"
SERVER_PID=
cleanup() {
    if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID"; wait "$SERVER_PID" || true; fi
    ip netns delete "$CLIENT"
    ip netns delete "$SERVER"
}
ip netns add "$SERVER"
ip netns add "$CLIENT"
trap cleanup EXIT
ip -n "$SERVER" link set lo up
ip -n "$CLIENT" link set lo up
ip netns exec "$SERVER" nft -f systemd/show-in-browser.nft
# Loading again must preserve one rule, without requiring tailscale0 to exist.
ip netns exec "$SERVER" nft -f systemd/show-in-browser.nft
ip netns exec "$SERVER" env XDG_RUNTIME_DIR=/tmp python3 serve.py &
SERVER_PID=$!
for attempt in {1..30}; do
    if ip netns exec "$SERVER" curl -fsS http://127.0.0.1:8377/ >/dev/null 2>&1; then break; fi
    sleep 0.1
done
ip netns exec "$SERVER" curl -fsS http://127.0.0.1:8377/
connect_interface() {
    ip -n "$SERVER" link add "$1" type veth peer name client netns "$CLIENT"
    ip -n "$SERVER" address add 192.0.2.1/24 dev "$1"
    ip -n "$CLIENT" address add 192.0.2.2/24 dev client
    ip -n "$SERVER" link set "$1" up
    ip -n "$CLIENT" link set client up
}
connect_interface lan0
if ip netns exec "$CLIENT" curl -fsS --max-time 2 http://192.0.2.1:8377/; then
    echo 'FAIL: LAN access was allowed' >&2
    exit 1
fi
ip -n "$SERVER" link delete lan0
for attempt in 1 2; do
    connect_interface tailscale0
    ip netns exec "$CLIENT" curl -fsS --max-time 2 http://192.0.2.1:8377/
    ip -n "$SERVER" link delete tailscale0
    ip netns exec "$SERVER" curl -fsS http://127.0.0.1:8377/
done
echo 'PASS: LAN blocked; localhost available; Tailscale interface can appear and be recreated'
