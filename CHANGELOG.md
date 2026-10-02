# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Each exporter also carries its own `__version__`.

## [Unreleased]

## [1.0.0] - 2026-10-03

First public release. Bundles smppbox exporter 1.2.0, KSMPPD exporter 1.2.0 and Kannel bearerbox exporter 1.1.0.

### Added
- **smppbox exporter** (port 9877) for Kannel / Kannel-HA smppbox `status.xml`: gateway, store, logins,
  per-customer, per-bind-type (transceiver / transmitter / receiver), per-source-IP and optional per-session
  metrics, plugin chains (DB pools, SQL queue), customer connected/disconnected state with timestamps.
- **KSMPPD exporter** (port 9878) for `esme-status.xml` and plain-text `esme-status`, plus the hidden `/uptime.xml`.
  Per-customer TPS limit, achieved TPS (inbound MT + rejected, outbound DLR + MO), utilisation and headroom.
- **Kannel bearerbox exporter** (port 9879) for vanilla Kannel 1.4.x (apt), SVN builds and Kannel-HA:
  bearerbox, SMSC links and routes, boxes, queues, loads, DLR ratio, SMSC connection details
  (protocol, host, port, receive port, SMSC username, system-type) parsed from the SMSC name.
- Generated Grafana dashboards for all three gateways with hover help on every panel.
- Prometheus alert rules (smppbox 9, KSMPPD 9, Kannel 11).
- Docker image, `docker compose` demo stack with a mock gateway, systemd units, CI, tests and documentation.

### Fixed (during pre-release production testing)
- smppbox: values in the millions/billions after an exporter restart – the first scrape now only sets a baseline.
- smppbox: a session missing from a single scrape was re-counted from zero on return – vanished sessions are
  remembered for 1 h; only genuinely new sessions count from zero; per-scrape jump cap `max_customer_rate`.
- smppbox: empty customer rows from servers that stopped reporting are hidden.
- KSMPPD: uptime URL was built incorrectly.
- KSMPPD: TPS model corrected – the limit applies to the whole customer, not per bind.
- Kannel: duplicate SMSC admin-ids (`instances = N`) made unique (`#2`, `#3`).
- Kannel: a wrong status password returns HTTP 200 `<gateway>Denied</gateway>` – now reported as down.
- Kannel: SMSC state timeline coloured everything red – now threshold based.
- All dashboards: split table rows – every table query is wrapped in `max by (<keys>)`.

[Unreleased]: https://github.com/AISH-HAMZA/smpp-prometheus-exporter/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/AISH-HAMZA/smpp-prometheus-exporter/releases/tag/v1.0.0
