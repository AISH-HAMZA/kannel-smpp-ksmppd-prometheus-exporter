# Kannel, smppbox & KSMPPD Prometheus Exporter – SMPP / SMS gateway monitoring with Grafana

[![CI](https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-exporter-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-dashboards-F46800?logo=grafana&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

**Open-source monitoring for SMS gateways that speak SMPP.** This project turns the built-in status pages of
**Kannel bearerbox**, **Kannel smppbox** and **KSMPPD** into Prometheus metrics, and ships ready-made Grafana
dashboards and alert rules on top of them.

* **What you see:** traffic per gateway server, per customer (ESME) and per operator link (SMSC) – messages sent (MT),
  received (MO) and delivery reports (DLR), throughput against TPS limits, queues, failures, connection state and
  uptime – from a fleet overview down to a single customer or link.
* **How it works:** a small Python exporter reads each gateway's HTTP status page and exposes the numbers on a
  `/metrics` endpoint. Run it on the gateway server itself, or run **one** exporter centrally that watches many
  gateway servers. Nothing has to be installed on or changed in the gateways.
* **Why:** spot a failing operator link, a customer hitting its TPS limit or a growing queue *before* your customers
  notice – with alerts sent through Prometheus Alertmanager.

Production-tested on busy A2P SMS platforms. Works with Prometheus-compatible stacks (VictoriaMetrics, Mimir, Thanos).

![Kannel bearerbox Grafana dashboard: SMSC operator links, MT and DLR throughput per SMSC-ID, failure rates and SMSC usernames](docs/images/kannel-smsc-links.png)

![Architecture of the SMPP Prometheus exporter: Kannel smppbox, KSMPPD and Kannel bearerbox gateways scraped centrally, stored in Prometheus, shown in Grafana, alerted by Alertmanager](docs/images/architecture.svg)


## Screenshots

<sub>Real production dashboards; server, customer, operator and IP names replaced with dummy values. Click to enlarge.</sub>

| Kannel bearerbox | KSMPPD | Kannel smppbox |
|---|---|---|
| [![Kannel overview: servers up, MT/DLR/MO rates, failure %, SMSC links online, queues](docs/images/kannel-overview.png)](docs/images/kannel-overview.png) | [![KSMPPD overview: TPS limit vs achieved TPS, utilisation and headroom per customer (ESME)](docs/images/ksmppd-overview-tps-limits.png)](docs/images/ksmppd-overview-tps-limits.png) | [![smppbox overview: sessions per customer, submit and deliver rates, open acks, store size](docs/images/smppbox-overview.png)](docs/images/smppbox-overview.png) |
| [![Kannel gateways: build info, gateway health and peak MT/DLR/MO per server and SMSC route](docs/images/kannel-gateways-peak-throughput.png)](docs/images/kannel-gateways-peak-throughput.png) | [![KSMPPD servers and peak throughput per server, customer and bind](docs/images/ksmppd-servers-peak-throughput.png)](docs/images/ksmppd-servers-peak-throughput.png) | [![smppbox gateways: build info and peak throughput per server, customer and SMPP session](docs/images/smppbox-gateways-peak-throughput.png)](docs/images/smppbox-gateways-peak-throughput.png) |
| [![Kannel SMSC operator links: state, MT/DLR per link, top-10 SMSC-IDs by traffic and failures](docs/images/kannel-smsc-links.png)](docs/images/kannel-smsc-links.png) | [![KSMPPD customer overview table and top-10 customers by MT, errors and error %](docs/images/ksmppd-customers-overview.png)](docs/images/ksmppd-customers-overview.png) | [![smppbox server health (CPU, memory, sessions) and customer (ESME) connection overview](docs/images/smppbox-servers-customers.png)](docs/images/smppbox-servers-customers.png) |
| [![Kannel traffic: MT, DLR and MO per bearerbox server, bearerbox load, queues and waiting DLRs](docs/images/kannel-traffic-per-server.png)](docs/images/kannel-traffic-per-server.png) | [![KSMPPD per-customer submit, deliver, error rate, achieved TPS and DLR ratio](docs/images/ksmppd-customer-traffic-errors.png)](docs/images/ksmppd-customer-traffic-errors.png) | [![smppbox top-10 customers by volume and failures, submit and deliver rate per customer](docs/images/smppbox-customer-traffic.png)](docs/images/smppbox-customer-traffic.png) |
| [![Kannel SMSC usernames: operator account overview, availability, MT and DLR per SMSC username](docs/images/kannel-smsc-username-overview.png)](docs/images/kannel-smsc-username-overview.png) | [![KSMPPD SMPP binds: transceiver/transmitter/receiver binds, bind details and connections by source IP](docs/images/ksmppd-binds-sessions.png)](docs/images/ksmppd-binds-sessions.png) | [![smppbox traffic: overall throughput, submit and deliver rate per server, gateway load and queues](docs/images/smppbox-traffic.png)](docs/images/smppbox-traffic.png) |

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
git clone https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter.git
cd kannel-smpp-ksmppd-prometheus-exporter/deploy/docker
docker compose up -d --build
```

Open **http://localhost:3000** (admin / admin) → folder *SMS Gateways*. Prometheus: http://localhost:9090.

## Deploy only what you run

Each exporter is independent – install just the one for your gateway, **on the gateway server itself** (same node)
or **on one monitoring server for many gateways** (central). One command does it: files, config, systemd service
and a test scrape.

| Your gateway | Same node (on the gateway server) | Central (one server, many gateways) | Guide |
|---|---|---|---|
| **Kannel bearerbox** | `sudo ./deploy/install.sh kannel --local --password 'PW'` | `sudo ./deploy/install.sh kannel --target kannel-a=http://192.0.2.30:13000/status.xml?password=PW` | [deploy-kannel.md](docs/deploy-kannel.md) |
| **Kannel smppbox** | `sudo ./deploy/install.sh smppbox --local --password 'PW'` | `sudo ./deploy/install.sh smppbox --target smppbox-a=http://192.0.2.10:14000/status.xml?password=PW` | [deploy-smppbox.md](docs/deploy-smppbox.md) |
| **KSMPPD** | `sudo ./deploy/install.sh ksmppd --local --password 'PW'` | `sudo ./deploy/install.sh ksmppd --target ksmppd-a=http://192.0.2.20:14000/esme-status.xml?password=PW` | [deploy-ksmppd.md](docs/deploy-ksmppd.md) |

```bash
git clone https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter.git && cd kannel-smpp-ksmppd-prometheus-exporter
sudo ./deploy/install.sh kannel --local --password 'STATUS_PASSWORD'      # example: Kannel, same node
```

Repeat `--target NAME=URL` for every gateway in central mode. Then add the printed scrape job to Prometheus and import
`dashboards/<gateway>_dashboard.json` into Grafana. Manual install, Docker and all options: [docs/installation.md](docs/installation.md).

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

[Deploy Kannel](docs/deploy-kannel.md) · [Deploy smppbox](docs/deploy-smppbox.md) · [Deploy KSMPPD](docs/deploy-ksmppd.md) ·
[Installation](docs/installation.md) · [Configuration](docs/configuration.md) · [Metrics](docs/metrics.md) ·
[Architecture](docs/architecture.md) · [Troubleshooting](docs/troubleshooting.md) · [FAQ](docs/faq.md) ·
[Design notes](docs/design-notes.md) · [Changelog](CHANGELOG.md)

## Roadmap

- [ ] Grafana.com dashboard listings
- [ ] Prebuilt image on GitHub Container Registry
- [ ] Jasmin SMS gateway and OpenSMPPBox support
- [ ] Optional per-target labels (site, environment)

Ideas welcome in [Discussions](https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter/discussions).

## Contributing

Bug reports with a sanitised status page are gold. See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE).

---

⭐ **If this saves you a night of debugging an SMS gateway, please star the repo** – it helps other telecom
engineers find it.
