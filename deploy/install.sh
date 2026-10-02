#!/usr/bin/env bash
# install.sh - install ONE SMPP Prometheus exporter (smppbox | ksmppd | kannel) as a systemd service.
#
# Same node (exporter runs on the gateway server itself, scrapes 127.0.0.1):
#   sudo ./deploy/install.sh kannel  --local --password 'STATUS_PASSWORD'
#
# Central (one monitoring node scrapes many gateway servers):
#   sudo ./deploy/install.sh kannel \
#        --target kannel-a=http://192.0.2.30:13000/status.xml?password=STATUS_PASSWORD \
#        --target kannel-b=http://192.0.2.31:13000/status.xml?password=STATUS_PASSWORD
#
# Other options:
#   --url URL           status URL for --local mode (default: 127.0.0.1 + default admin port, see below)
#   --name NAME         server label for --local mode (default: short hostname)
#   --port PORT         /metrics port (default: smppbox 9877, ksmppd 9878, kannel 9879)
#   --listen ADDRESS    /metrics bind address (default 0.0.0.0)
#   --force-config      overwrite an existing config.yml (default: keep it on upgrade)
#   --uninstall         stop the service and remove it (config is kept unless --purge)
#   --purge             with --uninstall: also delete /opt/smpp-exporter/<exporter>
#   --no-systemd        only install files (containers, non-systemd hosts, testing)
#   --prefix DIR        install below DIR instead of / (testing)
set -euo pipefail

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
die() { echo "ERROR: $*" >&2; exit 1; }
say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }

[ $# -ge 1 ] || usage 1
case "$1" in -h|--help) usage 0 ;; esac
GW="$1"; shift
case "$GW" in
  smppbox) SCRIPT=smpp_exporter.py;   PORT=9877; PAGE=status.xml;      ADMIN=14000 ;;
  ksmppd)  SCRIPT=ksmppd_exporter.py; PORT=9878; PAGE=esme-status.xml; ADMIN=14000 ;;
  kannel)  SCRIPT=kannel_exporter.py; PORT=9879; PAGE=status.xml;      ADMIN=13000 ;;
  *) die "first argument must be smppbox, ksmppd or kannel (got '$GW')" ;;
esac

LOCAL=0; URL=""; NAME="$(hostname -s 2>/dev/null || hostname)"; PASSWORD=""; LISTEN=0.0.0.0
FORCE=0; UNINSTALL=0; PURGE=0; SYSTEMD=1; PREFIX=""; TARGETS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --local) LOCAL=1 ;;
    --url) URL="$2"; shift ;;
    --name) NAME="$2"; shift ;;
    --password) PASSWORD="$2"; shift ;;
    --target|-t) TARGETS+=("$2"); shift ;;
    --port) PORT="$2"; shift ;;
    --listen) LISTEN="$2"; shift ;;
    --force-config) FORCE=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    --no-systemd) SYSTEMD=0 ;;
    --prefix) PREFIX="${2%/}"; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
  shift
done

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$PREFIX/opt/smpp-exporter/$GW"
UNIT="$PREFIX/etc/systemd/system/${GW}_exporter.service"
[ -n "$PREFIX" ] || [ "$(id -u)" -eq 0 ] || die "run as root (sudo)"

if [ "$UNINSTALL" -eq 1 ]; then
  if [ "$SYSTEMD" -eq 1 ] && command -v systemctl >/dev/null; then
    systemctl disable --now "${GW}_exporter" 2>/dev/null || true
  fi
  rm -f "$UNIT"; [ "$SYSTEMD" -eq 1 ] && command -v systemctl >/dev/null && systemctl daemon-reload
  if [ "$PURGE" -eq 1 ]; then rm -rf "$DEST"; say "removed $DEST"; else say "kept $DEST (use --purge to delete)"; fi
  say "${GW}_exporter uninstalled"; exit 0
fi

# ---- targets -------------------------------------------------------------------------------------------------------
if [ "$LOCAL" -eq 1 ]; then
  if [ -z "$URL" ]; then
    [ -n "$PASSWORD" ] || die "--local needs --password STATUS_PASSWORD (or a full --url)"
    URL="http://127.0.0.1:$ADMIN/$PAGE?password=$PASSWORD"
  fi
  TARGETS+=("$NAME=$URL")
fi
if [ ${#TARGETS[@]} -eq 0 ] && { [ ! -f "$DEST/config.yml" ] || [ "$FORCE" -eq 1 ]; }; then
  die "no gateway given: use --local --password ... (same node) or --target NAME=URL (central), see --help"
fi
for t in "${TARGETS[@]}"; do case "$t" in *=http://*|*=https://*) ;; *) die "target must look like NAME=http://host:port/$PAGE?password=...: $t" ;; esac; done

# ---- python dependencies -------------------------------------------------------------------------------------------
PY="${PYTHON:-$(command -v python3 || true)}"; [ -n "$PY" ] || die "python3 not found (apt install python3 / dnf install python3)"
if ! "$PY" -c 'import prometheus_client, yaml' 2>/dev/null; then
  say "installing Python packages prometheus_client + PyYAML"
  if command -v apt-get >/dev/null; then apt-get install -y -q python3-prometheus-client python3-yaml >/dev/null
  elif command -v dnf >/dev/null; then dnf install -y -q python3-prometheus_client python3-pyyaml >/dev/null || "$PY" -m pip install -q -r "$REPO/requirements.txt"
  else "$PY" -m pip install -q -r "$REPO/requirements.txt"; fi
fi
"$PY" -c 'import prometheus_client, yaml' 2>/dev/null || die "could not install prometheus_client / PyYAML - run: pip3 install -r requirements.txt"

# ---- files ---------------------------------------------------------------------------------------------------------
say "installing $GW exporter to $DEST"
mkdir -p "$DEST"
install -m 0755 "$REPO/exporters/$GW/$SCRIPT" "$DEST/$SCRIPT"
if [ -f "$DEST/config.yml" ] && [ "$FORCE" -eq 0 ]; then
  say "keeping existing $DEST/config.yml (use --force-config to rewrite it)"
  [ ${#TARGETS[@]} -eq 0 ] || echo "    note: --target/--local ignored because the config already exists"
else
  {
    sed -n '1,/^targets:/p' "$REPO/exporters/$GW/config.example.yml" \
      | sed "s/^port: [0-9]*/port: $PORT/; s/^listen_address: .*/listen_address: $LISTEN/"
    for t in "${TARGETS[@]}"; do printf '  - name: %s\n    url: %s\n' "${t%%=*}" "${t#*=}"; done
  } > "$DEST/config.yml"
  say "wrote $DEST/config.yml with ${#TARGETS[@]} target(s)"
fi
if [ -z "$PREFIX" ]; then
  GROUP="$(getent group nogroup >/dev/null && echo nogroup || echo nobody)"
  chown -R root:"$GROUP" "$DEST"; chmod 0640 "$DEST/config.yml"
fi

# ---- test once -----------------------------------------------------------------------------------------------------
say "test scrape (--once):"
OUT="$("$PY" "$DEST/$SCRIPT" -c "$DEST/config.yml" --once 2>&1 || true)"
echo "$OUT" | grep -E "^${GW}_up\{|WARNING|ERROR" | sed 's/^/    /' || true
echo "$OUT" | grep -q "^${GW}_up{.*} 0" && echo "    -> at least one gateway is DOWN: check URL/password (see docs/troubleshooting.md)"

# ---- systemd -------------------------------------------------------------------------------------------------------
if [ "$SYSTEMD" -eq 1 ]; then
  command -v systemctl >/dev/null || die "systemctl not found - re-run with --no-systemd and start the exporter yourself"
  sed "s#^ExecStart=.*#ExecStart=$PY $DEST/$SCRIPT --config $DEST/config.yml#" \
    "$REPO/deploy/systemd/${GW}_exporter.service" > "$UNIT"
  systemctl daemon-reload
  systemctl enable --now "${GW}_exporter" >/dev/null
  systemctl restart "${GW}_exporter"
  sleep 2
  systemctl is-active --quiet "${GW}_exporter" || die "service failed: journalctl -u ${GW}_exporter -n 50"
  say "${GW}_exporter is running on :$PORT  ->  curl -s localhost:$PORT/metrics | grep ${GW}_up"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-THIS_HOST}"
cat <<EOF

Next steps
  1. Prometheus (prometheus.yml -> scrape_configs):
       - job_name: ${GW}_exporter
         static_configs:
           - targets: ['$IP:$PORT']
  2. Grafana: Dashboards > New > Import > upload dashboards/${GW}_dashboard.json
  3. Alerts (optional): copy alerts/${GW}_alerts.yml to Prometheus and add it under rule_files:
  Add/remove gateways later: edit $DEST/config.yml, then  systemctl reload ${GW}_exporter
EOF
