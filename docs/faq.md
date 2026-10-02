# FAQ

## Glossary (SMPP in 2 minutes)

| Term | Meaning |
|---|---|
| **SMPP** | *Short Message Peer-to-Peer* – the TCP protocol used between SMS companies and mobile operators. |
| **SMSC** | *Short Message Service Centre* – the operator system that delivers SMS to phones. In Kannel an "SMSC" is a link to one. |
| **ESME** | *External Short Messaging Entity* – a client that connects to an SMPP server, e.g. your customer. Identified by its **system-id**. |
| **MT** | *Mobile Terminated* – a message sent **to** a phone (`submit_sm`). |
| **MO** | *Mobile Originated* – a message sent **from** a phone (`deliver_sm`). |
| **DLR** | *Delivery report* – the receipt saying whether an MT reached the phone. |
| **TPS** | *Transactions per second* – the throughput limit agreed with a customer or operator. |
| **Bind** | An SMPP session. **Transmitter** (TX) only sends, **receiver** (RX) only receives, **transceiver** (TRX) does both. |
| **bearerbox** | Kannel's core process: routes messages between SMSC links and boxes. |
| **smppbox** | Kannel add-on that lets customers connect to Kannel via SMPP. |
| **KSMPPD** | A standalone SMPP server that, like smppbox, sits in front of Kannel. |
| **Kannel-HA** | A high-availability Kannel variant whose status page has extra fields (HA routes, per-box counters). |

## Which exporter do I need?

* Customers connect to you via SMPP through **smppbox** → smppbox exporter.
* Customers connect via **KSMPPD** → KSMPPD exporter.
* You run **Kannel bearerbox** with SMSC links to operators → Kannel exporter.

Most Kannel installations use the Kannel exporter plus one of the other two.

## Does it need anything installed on the gateways?

No. It only reads the HTTP status page that the gateway already serves.

## How is this different from other Kannel exporters?

One exporter process scrapes **many** gateways (central mode), it also covers **smppbox and KSMPPD**,
handles Kannel-HA fields, keeps per-customer counters correct across reconnects, parses SMSC usernames, and ships
with full Grafana dashboards and alert rules.

## Which Kannel versions are supported?

Vanilla Kannel 1.4.x (Debian/Ubuntu packages, tested with 1.4.5), SVN builds and Kannel-HA. If your status page
differs, open an issue with a sanitised `status.xml`.

## How much load does it put on the gateway?

One HTTP request per gateway per `scrape_interval` (default 15 s) – the same as opening the status page in a browser.

## How many gateways can one exporter handle?

Dozens. Targets are scraped in parallel (`max_workers`, default 16). Cardinality grows with customers and sessions;
keep `per_session_metrics` off if you have thousands of sessions.

## Can I use VictoriaMetrics / Grafana Mimir / Thanos instead of Prometheus?

Yes – anything that scrapes Prometheus `/metrics` and speaks PromQL works with the dashboards.

## Does it work on Windows?

The exporters are plain Python and run anywhere; the systemd units are Linux-only. Use Docker on Windows/macOS.
