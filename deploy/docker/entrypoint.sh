#!/bin/sh
# Starts the exporter selected by $EXPORTER with the config at $CONFIG. Extra arguments are passed through,
# e.g.  docker run ... kannel-smpp-ksmppd-prometheus-exporter --once
set -e
case "$EXPORTER" in
  smppbox) exec python /app/exporters/smppbox/smpp_exporter.py --config "$CONFIG" "$@" ;;
  ksmppd)  exec python /app/exporters/ksmppd/ksmppd_exporter.py --config "$CONFIG" "$@" ;;
  kannel)  exec python /app/exporters/kannel/kannel_exporter.py --config "$CONFIG" "$@" ;;
  mock)    exec python /app/examples/mock_gateway.py "$@" ;;
  *) echo "EXPORTER must be smppbox, ksmppd, kannel or mock (got '$EXPORTER')" >&2; exit 2 ;;
esac
