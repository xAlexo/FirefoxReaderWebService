#!/bin/sh
set -eu

if [ "$#" -eq 0 ]; then
  echo "ERROR: no command provided" >&2
  exit 64
fi

TOR_LOG_FILE="/tmp/tor-bootstrap.log"

cleanup() {
  if [ -n "${TOR_PID:-}" ] && kill -0 "$TOR_PID" 2>/dev/null; then
    kill "$TOR_PID" 2>/dev/null || true
    wait "$TOR_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

# Append Tor bridge lines from environment variables when USE_BRIDGES=1.
# Bridges bypass direct Tor connections — used in censored networks.
# Set TOR_BRIDGE_1..TOR_BRIDGE_10 to obfs4 bridge lines, e.g.:
#   TOR_BRIDGE_1="obfs4 1.2.3.4:443 <fingerprint> cert=<cert> iat-mode=0"
if [ "${USE_BRIDGES:-0}" = "1" ]; then
  {
    echo "UseBridges 1"
    echo "ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy"
    i=1
    while [ "$i" -le 10 ]; do
      # Indirect variable expansion without eval (safe against injection)
      line=""
      case "$i" in
        1) line="${TOR_BRIDGE_1:-}" ;;
        2) line="${TOR_BRIDGE_2:-}" ;;
        3) line="${TOR_BRIDGE_3:-}" ;;
        4) line="${TOR_BRIDGE_4:-}" ;;
        5) line="${TOR_BRIDGE_5:-}" ;;
        6) line="${TOR_BRIDGE_6:-}" ;;
        7) line="${TOR_BRIDGE_7:-}" ;;
        8) line="${TOR_BRIDGE_8:-}" ;;
        9) line="${TOR_BRIDGE_9:-}" ;;
        10) line="${TOR_BRIDGE_10:-}" ;;
      esac
      [ -n "$line" ] && echo "Bridge $line"
      i=$((i + 1))
    done
  } >> /etc/tor/torrc
  echo "Appended Tor bridge configuration to torrc"
fi

# When PROXIES is set, route Tor's own OR connections through the external
# SOCKS5 proxy (bypasses networks where Tor-direct is blocked).
# Uses the FIRST entry only (Tor supports a single Socks5Proxy).
# Schemes socks5h:// and socks5:// are stripped; host:port retained.
# Optional user:pass@ prefix → Socks5ProxyUsername/Password (RFC 1929).
# Guard: skip if the proxy points at the local Tor SocksPort (self-loop).
if [ -n "${PROXIES:-}" ]; then
  FIRST_PROXY="${PROXIES%%,*}"
  # strip scheme
  NOPROXY="${FIRST_PROXY#socks5h://}"
  NOPROXY="${NOPROXY#socks5://}"
  # extract optional user:pass@
  AUTH=""
  case "$NOPROXY" in
    *@*)
      AUTH="${NOPROXY%%@*}"
      NOPROXY="${NOPROXY#*@}"
      ;;
  esac
  # Guard against self-proxy loop: skip if proxy is local Tor SocksPort
  case "$NOPROXY" in
    127.0.0.1:9050|localhost:9050)
      echo "Skipping Socks5Proxy: PROXIES points at local Tor (self-loop guard)"
      ;;
    *)
      {
        echo "Socks5Proxy $NOPROXY"
        if [ -n "$AUTH" ] && [ "$AUTH" != "${AUTH%%:*}" ]; then
          USER="${AUTH%%:*}"
          PASS="${AUTH#*:}"
          echo "Socks5ProxyUsername $USER"
          echo "Socks5ProxyPassword $PASS"
        elif [ -n "$AUTH" ]; then
          echo "Socks5ProxyUsername $AUTH"
        fi
      } >> /etc/tor/torrc
      echo "Appended Tor Socks5Proxy ($NOPROXY) to torrc"
      ;;
  esac
fi

tor -f /etc/tor/torrc > "$TOR_LOG_FILE" 2>&1 &
TOR_PID="$!"

echo "Waiting for Tor bootstrap..."

BOOTSTRAP_TIMEOUT_SECONDS="${BOOTSTRAP_TIMEOUT_SECONDS:-120}"
START_TIME="$(date +%s)"

while true; do
  if ! kill -0 "$TOR_PID" 2>/dev/null; then
    echo "ERROR: Tor exited before bootstrap" >&2
    cat "$TOR_LOG_FILE" >&2
    exit 70
  fi

  if grep -q "Bootstrapped 100%" "$TOR_LOG_FILE"; then
    break
  fi

  NOW="$(date +%s)"
  ELAPSED="$((NOW - START_TIME))"

  if [ "$ELAPSED" -ge "$BOOTSTRAP_TIMEOUT_SECONDS" ]; then
    echo "ERROR: Tor bootstrap timeout after ${BOOTSTRAP_TIMEOUT_SECONDS}s" >&2
    cat "$TOR_LOG_FILE" >&2
    exit 75
  fi

  sleep 1
done

echo "Tor bootstrapped."

until nc -z 127.0.0.1 9050; do
  sleep 1
done

echo "Tor SOCKS5 is ready on 127.0.0.1:9050"
echo "Starting application: $*"

trap - INT TERM EXIT

"$@" &
APP_PID="$!"

forward_signal() {
  kill "$APP_PID" 2>/dev/null || true
  kill "$TOR_PID" 2>/dev/null || true
}

trap forward_signal INT TERM

set +e
wait "$APP_PID"
APP_EXIT_CODE="$?"
set -e

kill "$TOR_PID" 2>/dev/null || true
wait "$TOR_PID" 2>/dev/null || true

exit "$APP_EXIT_CODE"
