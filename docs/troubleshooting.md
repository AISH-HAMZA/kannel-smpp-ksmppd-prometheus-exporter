# Troubleshooting

Start every investigation with a one-shot scrape – it prints the error for each target:

```bash
python3 /opt/smpp-exporter/kannel/kannel_exporter.py -c /opt/smpp-exporter/kannel/config.yml --once 2>&1 | grep -E "WARNING|_up\{"
journalctl -u kannel_exporter -n 50
```

## `*_up` is 0

| Log message | Cause | Fix |
|---|---|---|
| `answered 'Denied' - wrong status/admin password` | Wrong password. Kannel returns **HTTP 200** with `<gateway>Denied</gateway>`, KSMPPD returns `Denied`. | Use `status-password` (or `admin-password`) from the gateway config. URL-encode special characters (`&` → `%26`). |
| `timed out` / `Connection refused` | Firewall, wrong port, or admin port bound to `127.0.0.1`. | `curl` the URL from the exporter host. Check `admin-port`/`admin-interface`, or use [per-node mode](installation.md#3-per-node-deployment). |
| `not a Kannel status.xml page` | URL points to `/status` (HTML) or another service. | Use `/status.xml`. |
| `no 'Unique known ESME's'` (KSMPPD) | URL is not the esme-status page. | Use `/esme-status.xml` or `/esme-status`. |
| `CERTIFICATE_VERIFY_FAILED` | Self-signed HTTPS admin port. | Add `insecure: true` to the target. |

## Grafana table rows are split / duplicated

Grafana's *merge* transformation only joins series with **identical label sets**. If you add your own table queries,
wrap each one in `max by (<key labels>) (...)` – e.g. `max by (server, esme) (rate(...))`. Raw series also carry
`job`/`instance`, aggregated ones do not, and that splits the rows. The shipped dashboards already do this.

## Empty panels

* *"No data"* right after install: rates need at least two scrapes – wait 1–2 minutes.
* The smppbox **session peak** table needs `per_session_metrics: true`.
* Check the dashboard variables (server, customer, bind type) – a stale selection hides everything; pick *All*.
* Check *Status → Targets* in Prometheus: the job must be UP and the `job` name can be anything.

## Huge spikes or values in the billions (smppbox)

smppbox counters are per session and reset on reconnect; the exporter turns them into monotonic counters
(see [design notes](design-notes.md)). Versions before 1.2.0 could produce spikes after a restart or a missed
scrape. Upgrade, then delete the bad data from Prometheus.

## Deleting bad series from Prometheus

Prometheus needs the admin API: start it with `--web.enable-admin-api` (Debian: add it to `ARGS` in
`/etc/default/prometheus`, then restart). Grafana cannot delete data.

```bash
# delete everything from one job, or narrow it with more labels and a time range
curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]={job="smppbox_exporter"}'
curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]={__name__=~"smppbox_esme_.*",server="smppbox-a"}&start=2026-10-01T00:00:00Z&end=2026-10-01T06:00:00Z'
curl -X POST http://localhost:9090/api/v1/admin/tsdb/clean_tombstones
```

## Counter resets after a gateway restart

Normal. `rate()` and `increase()` handle resets. KSMPPD and Kannel counters start at 0 when the gateway restarts;
the dashboards show restarts as annotations.

## Ghost customers / servers

A removed gateway keeps showing in `increase()[range]` columns until the range has passed. The customer tables
only list servers that currently report. Lower `series_retention` to forget vanished customers faster.

## The exporter is slow

Each scrape cycle fetches all targets in parallel (`max_workers`). One slow gateway only delays itself – lower its
`timeout`. On Windows/IPv6 hosts use `127.0.0.1` instead of `localhost` to avoid a 2-second IPv6 fallback.
