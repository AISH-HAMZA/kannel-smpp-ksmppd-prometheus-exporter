# Architecture

![SMPP Prometheus exporter architecture: Kannel smppbox, KSMPPD and Kannel bearerbox status pages scraped by central exporters, stored in Prometheus, visualised in Grafana and alerted via Alertmanager](images/architecture.svg)

```mermaid
flowchart LR
  subgraph G["SMS / SMPP gateways (many servers)"]
    S1["Kannel smppbox<br/>/status.xml"]
    K1["KSMPPD<br/>/esme-status.xml + /uptime.xml"]
    B1["Kannel bearerbox<br/>/status.xml"]
  end
  subgraph M["Monitoring node"]
    E1["smppbox exporter :9877"]
    E2["ksmppd exporter :9878"]
    E3["kannel exporter :9879"]
  end
  S1 -- HTTP + status password --> E1
  K1 -- HTTP + status password --> E2
  B1 -- HTTP + status password --> E3
  E1 & E2 & E3 -- /metrics --> P[(Prometheus)]
  P --> GR[Grafana dashboards]
  P -- alert rules --> AM[Alertmanager] --> N[E-mail / Slack / SMS]
```

## Data flow

1. **Gateways** expose an admin/status HTTP page protected by a status password. Nothing is installed on them.
2. **Exporters** (one per gateway type) poll every configured gateway in parallel every `scrape_interval` seconds,
   parse the XML/text, keep state (counters that survive reconnects, connection state, link flaps) and serve the latest
   result on `/metrics`. Every series gets a `server` label.
3. **Prometheus** scrapes the three `/metrics` endpoints and evaluates the alert rules from `alerts/`.
4. **Grafana** shows the generated dashboards: overall → per server → per customer (ESME) / per SMSC link drill-down.
5. **Alertmanager** routes the alerts (gateway down, link down, queue growing, customer disconnected, TPS limit, …).

## Docker demo stack

![Docker demo stack: mock gateway container feeding three exporter containers, Prometheus and Grafana with auto-provisioned dashboards](images/docker-demo.svg)

```mermaid
flowchart LR
  MG["mock-gateway :8080<br/>fake smppbox / KSMPPD / Kannel pages"] --> X1[smppbox-exporter :9877] & X2[ksmppd-exporter :9878] & X3[kannel-exporter :9879]
  X1 & X2 & X3 --> PR["prometheus :9090<br/>+ alerts/"] --> GF["grafana :3000<br/>datasource + dashboards provisioned"]
```

## Repository layout

```
exporters/<gw>/        exporter (single Python file), config.example.yml, README with metric table
dashboards/            generated Grafana dashboards + provisioning examples
alerts/                Prometheus alert rules
deploy/systemd/        systemd units
deploy/docker/         Dockerfile, docker-compose demo, Prometheus + Grafana provisioning
deploy/prometheus/     scrape config example
tools/                 dashboard generators (python3 tools/gen_<gw>_dashboard.py)
examples/              mock gateway + fictional sample status pages
tests/                 pytest: parsers, counter logic, end-to-end, dashboards
docs/                  installation, configuration, metrics, troubleshooting, FAQ, design notes
```

Why the exporters are built this way: [design-notes.md](design-notes.md).
