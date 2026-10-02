# SMPP Prometheus Exporter – Kannel, smppbox & KSMPPD monitoring with Grafana

[![CI](https://github.com/AISH-HAMZA/smpp-prometheus-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/AISH-HAMZA/smpp-prometheus-exporter/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-exporter-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-dashboards-F46800?logo=grafana&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

**Production-tested Prometheus exporters, Grafana dashboards and alert rules for SMS / SMPP gateways:
Kannel bearerbox, Kannel smppbox and KSMPPD.** One small Python process watches all your gateway servers, so you can
see every customer (ESME), SMSC link, TPS limit and delivery report on one Grafana screen, and get alerts before
your customers notice.

![Kannel bearerbox Grafana dashboard: SMSC operator links, MT and DLR throughput per SMSC-ID, failure rates and SMSC usernames](docs/images/kannel-smsc-links.png)

![Architecture of the SMPP Prometheus exporter: Kannel smppbox, KSMPPD and Kannel bearerbox gateways scraped centrally, stored in Prometheus, shown in Grafana, alerted by Alertmanager](docs/images/architecture.svg)


## Screenshots

<sub>Real production dashboards; server, customer, operator and IP names replaced with dummy values.</sub>

| Kannel bearerbox | KSMPPD | Kannel smppbox |
|---|---|---|
| [![Kannel overview: servers up, MT/DLR/MO rates, failure %, SMSC links online, queues](docs/images/kannel-overview.png)](docs/images/kannel-overview.png) | [![KSMPPD overview: TPS limit vs achieved TPS, utilisation and headroom per customer (ESME)](docs/images/ksmppd-overview-tps-limits.png)](docs/images/ksmppd-overview-tps-limits.png) | [![smppbox overview: sessions per customer, submit and deliver rates, open acks, store size](docs/images/smppbox-overview.png)](docs/images/smppbox-overview.png) |
| [![Kannel gateways: build info, gateway health and peak MT/DLR/MO throughput per server and SMSC route](docs/images/kannel-gateways-peak-throughput.png)](docs/images/kannel-gateways-peak-throughput.png) | [![KSMPPD servers and peak throughput per server, customer and bind](docs/images/ksmppd-servers-peak-throughput.png)](docs/images/ksmppd-servers-peak-throughput.png) | [![smppbox gateways: build info and peak throughput per server, customer and SMPP session](docs/images/smppbox-gateways-peak-throughput.png)](docs/images/smppbox-gateways-peak-throughput.png) |
| [![Kannel SMSC usernames: queue and DLR ratio per SMSC-ID, MT rate and link availability gauges per operator account](docs/images/kannel-smsc-usernames.png)](docs/images/kannel-smsc-usernames.png) | [![KSMPPD per-customer submit, deliver, error rate and DLR ratio graphs](docs/images/ksmppd-customer-traffic-errors.png)](docs/images/ksmppd-customer-traffic-errors.png) | [![smppbox traffic: overall throughput, submit and deliver rate per server, gateway load and queues](docs/images/smppbox-traffic.png)](docs/images/smppbox-traffic.png) |

## Why?

SMS gateways only have a status page. You can't see traffic history or per-customer throughput on it, and nothing
pages you when an operator link goes down at 3 a.m. These exporters turn those status pages into Prometheus
metrics:

* **Central by design** – one exporter scrapes *many* gateway servers. Nothing is installed on the gateways.
* **Three gateway types** – Kannel bearerbox (1.4.x, SVN, Kannel-HA), Kannel smppbox and KSMPPD.
* **Correct counters** – smppbox session counters reset on every reconnect; the exporter keeps them monotonic,
  without the "billions of messages" spikes ([how](docs/design-notes.md)).
* **Ready-made dashboards** – 70+ panels per gateway with hover help, from overview down to single customer or link.
* **Alert rules included** – gateway down, SMSC link down/flapping, queues growing, customer disconnected, TPS limit.
* **Tiny** – single-file Python, two dependencies (`prometheus_client`, `PyYAML`), Docker image and systemd units.

## 60-second quick start (Docker demo)

No gateway needed. A mock gateway generates realistic, fictional traffic.

```bash
git clone https://github.com/AISH-HAMZA/smpp-prometheus-exporter.git
cd smpp-prometheus-exporter/deploy/docker
docker compose up -d --build
```

Open **http://localhost:3000** (admin / admin) → folder *SMS Gateways*. Prometheus: http://localhost:9090.

## Production install (central mode)

```bash
sudo pip3 install -r requirements.txt
sudo mkdir -p /opt/smpp-exporter/kannel
sudo cp exporters/kannel/kannel_exporter.py /opt/smpp-exporter/kannel/
sudo cp exporters/kannel/config.example.yml /opt/smpp-exporter/kannel/config.yml   # add gateways + status passwords
python3 /opt/smpp-exporter/kannel/kannel_exporter.py -c /opt/smpp-exporter/kannel/config.yml --once | grep _up
sudo cp deploy/systemd/kannel_exporter.service /etc/systemd/system/ && sudo systemctl enable --now kannel_exporter
```

Do the same for `smppbox` / `ksmppd`, add the [scrape jobs](deploy/prometheus/prometheus-scrape.example.yml), import
`dashboards/*.json` into Grafana and copy `alerts/*.yml` to Prometheus.
**Full guide (central, per-node, single-node, Docker):** [docs/installation.md](docs/installation.md).

## The three exporters

| | Kannel bearerbox | Kannel smppbox | KSMPPD |
|---|---|---|---|
| Directory | [`exporters/kannel`](exporters/kannel) | [`exporters/smppbox`](exporters/smppbox) | [`exporters/ksmppd`](exporters/ksmppd) |
| Status page | `/status.xml` | `/status.xml` | `/esme-status.xml` or `/esme-status` + `/uptime.xml` |
| Port | **9879** | **9877** | **9878** |
| Role | core router to operators (SMSC links) | SMPP server for customers | SMPP server for customers |
| Key metrics | SMSC link state & flaps, MT/MO/DLR per link, queues, DLR ratio, SMSC username/host/port, boxes, Kannel-HA extras | per-customer & per-bind-type traffic, connected state, sessions, source IPs, plugins/DB pools, peak throughput | TPS limit vs achieved TPS, utilisation & headroom, MT/MO/DLR/errors, per-bind loads & queues |
| Alert rules | 11 | 9 | 9 |

All metrics: [docs/metrics.md](docs/metrics.md).

## Dashboards

Each dashboard goes from **all gateways → one server → one customer / link**, using variables for server,
customer (ESME), SMSC-ID and bind type:

* **Kannel bearerbox:** overview, SMSC links & routes (availability timeline, links with problems), SMSC usernames,
  queues & loads, boxes, DLR ratio.
* **smppbox:** gateways & peak throughput, traffic, servers, customers (top-10, failure %, connection history),
  connections by bind type, source IPs, plugins & DB.
* **KSMPPD:** overview, customers, TPS limit / utilisation / headroom, binds, errors.

Dashboards are generated by `tools/gen_*_dashboard.py` – see [CONTRIBUTING.md](CONTRIBUTING.md).

## How it works

```mermaid
flowchart LR
  A["smppbox servers"] -- status.xml --> E1["smppbox exporter :9877"]
  B["KSMPPD servers"] -- esme-status.xml --> E2["ksmppd exporter :9878"]
  C["Kannel bearerbox servers"] -- status.xml --> E3["kannel exporter :9879"]
  E1 & E2 & E3 --> P[(Prometheus)] --> G[Grafana]
  P --> AM[Alertmanager]
```

More: [architecture](docs/architecture.md) · [design notes](docs/design-notes.md) · [configuration](docs/configuration.md).

## New to SMPP?

| Term | In one line |
|---|---|
| **SMPP** | The protocol SMS companies and mobile operators use to exchange messages. |
| **SMSC** | The operator's SMS centre; in Kannel, a link to one. |
| **ESME** | A client of an SMPP server – usually your customer (identified by *system-id*). |
| **MT / MO** | Message *to* a phone / message *from* a phone. |
| **DLR** | Delivery report – did the message arrive? |
| **TPS** | Messages per second – the agreed throughput limit. |
| **Bind** | An SMPP session: transmitter (send), receiver (receive) or transceiver (both). |

More in the [FAQ](docs/faq.md).

## Documentation

[Installation](docs/installation.md) · [Configuration](docs/configuration.md) · [Metrics](docs/metrics.md) ·
[Architecture](docs/architecture.md) · [Troubleshooting](docs/troubleshooting.md) · [FAQ](docs/faq.md) ·
[Design notes](docs/design-notes.md) · [Changelog](CHANGELOG.md)

## Roadmap

- [ ] Grafana.com dashboard listings
- [ ] Prebuilt image on GitHub Container Registry
- [ ] Jasmin SMS gateway and OpenSMPPBox support
- [ ] Optional per-target labels (site, environment)

Ideas welcome in [Discussions](https://github.com/AISH-HAMZA/smpp-prometheus-exporter/discussions).

## Contributing

Bug reports with a sanitised status page are gold. See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE).

---

⭐ **If this saves you a night of debugging an SMS gateway, please star the repo** – it helps other telecom
engineers find it.
