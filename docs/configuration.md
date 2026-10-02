# Configuration reference

Each exporter reads a YAML (or JSON) file given with `-c / --config`. **Command-line flags override the file.**
Start from `exporters/<gw>/config.example.yml`. Reload targets without a restart: `systemctl reload <gw>_exporter`
(or `kill -HUP <pid>`).

## Common options (all three exporters)

| YAML key | CLI flag | Default | Meaning |
|---|---|---|---|
| `listen_address` | `--listen-address` | `0.0.0.0` | Address the `/metrics` HTTP server binds to. Use an internal IP to limit exposure. |
| `port` | `-p`, `--port` | smppbox **9877**, ksmppd **9878**, kannel **9879** | `/metrics` port. |
| `scrape_interval` | `-i`, `--interval` | `15` | Seconds between two scrape cycles of all gateways. Match your Prometheus `scrape_interval`. |
| `timeout` | `--timeout` | `10` | Default HTTP timeout per gateway (s). Can be overridden per target. |
| `max_workers` | `--workers` | `16` | Gateways scraped in parallel. |
| `disable_process_metrics` | `--disable-process-metrics` | `false` | Drop the `python_*` / `process_*` metrics. |
| `log_level` | `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `targets` | `-t NAME=URL` (repeatable) | – | Gateways to scrape, see below. |
| – | `--once` | – | Scrape once, print the metrics to stdout and exit. Perfect for testing. |
| – | `--version` | – | Print the exporter version. |

## Targets

```yaml
targets:
  - name: kannel-a                                                    # required: value of the `server` label
    url: http://192.0.2.30:13000/status.xml?password=CHANGE_ME       # required: status page incl. password
    timeout: 5                                                        # optional, seconds
    insecure: true                                                    # optional: skip TLS verification (https)
    username: admin                                                   # optional: HTTP basic auth
    password: secret                                                  # optional: HTTP basic auth
```

* Keep `name` **stable** – renaming a target creates a new time series.
* Passwords in URLs are masked (`password=***`) in logs and never exported.

## smppbox only

| YAML key | CLI flag | Default | Meaning |
|---|---|---|---|
| `per_session_metrics` | `--per-session` | `false` | Export one series per SMPP session (ip+port). Needed for the *session peak* table. Higher cardinality. |
| `hide_plugin_args` | `--no-plugin-args` | `false` | Do not expose plugin arguments (may contain URLs/regex) as a label. |
| `series_retention` | `--series-retention` | `86400` | Seconds to keep counters of customers/IPs that disappeared. |
| `max_customer_rate` | – | `20000` | msg/s. A per-scrape increase above `rate × window` is discarded as a glitch (see [design notes](design-notes.md)). |

URL: `http://<host>:<smppbox admin port>/status.xml?password=…`

## KSMPPD only

| YAML key | CLI flag | Default | Meaning |
|---|---|---|---|
| `per_bind_metrics` | `--no-per-bind` (disables) | `true` | Per-bind metrics: bind id, IP, type, counters, loads. |
| `fetch_uptime` | `--no-uptime` (disables) | `true` | Also call `/uptime.xml` (same directory and password as the status URL). |
| `series_retention` | `--series-retention` | `86400` | Forget customers not seen for this many seconds. |
| target `uptime: false` | – | – | Skip `/uptime.xml` for one target. |

URL: `http://<host>:<port>/esme-status.xml?password=…` (preferred) or plain-text `/esme-status?password=…` –
both are parsed identically.

## Kannel bearerbox only

No extra options. URL: `http://<host>:<admin-port>/status.xml?password=<status-password or admin-password>`.
Works with vanilla Kannel 1.4.x (Debian/Ubuntu `apt install kannel`), SVN builds and Kannel-HA.

## Environment (Docker image)

| Variable | Default | Meaning |
|---|---|---|
| `EXPORTER` | `kannel` | `smppbox`, `ksmppd`, `kannel` or `mock` (demo gateway) |
| `CONFIG` | `/etc/smpp-exporter/config.yml` | Config file path inside the container |
| `MOCK_PORT`, `MOCK_PASSWORD` | `8080`, `demo` | Mock gateway only |
