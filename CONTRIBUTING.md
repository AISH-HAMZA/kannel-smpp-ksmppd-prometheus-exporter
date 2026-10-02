# Contributing

Thanks for helping to make SMS gateway monitoring better! Bug reports, sanitised status pages from other gateway
versions, new panels and docs fixes are all welcome.

## Development setup

```bash
git clone https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter.git
cd kannel-smpp-ksmppd-prometheus-exporter
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest            # lint + parser, end-to-end and dashboard tests
python3 examples/mock_gateway.py  # fake gateways on :8080 for manual testing
```

## Ground rules

* **Exporters are single-file Python 3** using only `prometheus_client` and `PyYAML`. Keep them dependency-light so
  they can be copied onto any monitoring host.
* **Dashboards are generated.** Edit `tools/gen_<gw>_dashboard.py` (smppbox hover texts: `tools/smppbox_desc.py`) and
  run `python3 tools/gen_<gw>_dashboard.py`. Never hand-edit `dashboards/*.json` – CI fails if JSON and generator differ.
* **Grafana tables:** every table query must return identical label sets – wrap it in `max by (<keys>)`, otherwise
  rows split (see [design notes](docs/design-notes.md)).
* **Alert rules** must pass `promtool check rules alerts/*.yml`.
* **Changing metrics?** Bump the exporter's `__version__`, update the metric table in its README and `CHANGELOG.md`.
* **New gateway version / parser bug?** Add a *sanitised* page to `examples/pages/` and a test in `tests/`.
* **Never commit real data**: no real IPs (use `192.0.2.x`, `198.51.100.x`, `203.0.113.x`), passwords, hostnames,
  customer or operator names.

## Commits and pull requests

We use [Conventional Commits](https://www.conventionalcommits.org/): `feat(kannel): …`, `fix(smppbox): …`,
`docs: …`, `ci: …`, `chore: …`. Keep PRs small and focused and fill in the PR checklist.
