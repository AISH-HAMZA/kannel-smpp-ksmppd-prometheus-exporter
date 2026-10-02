# KSMPPD exporter

`ksmppd_exporter.py` – v1.2.0 – port **9878** – scrapes `esme-status.xml` (or the plain-text `esme-status`)
and `uptime.xml` of every ksmppd. Field meanings verified against the ksmppd source (`smpp_esme.c`, `smpp_queues.c`).

## Semantics
* `mt` = submit_sm accepted · `errors` = submit_sm rejected · `mo` / `dlr` = deliveries to the customer
* inbound/outbound processed = **all** PDUs (incl. enquire_link, responses)
* load triplet on summary + customer = since start / last 1 s / last 60 s; bind load = last 1 s
* `max-inbound-load` = **TPS limit of the customer** (same whatever the number of binds)
* bind-type 1 = TX (transmitter), 2 = RX (receiver), 3 = TRX (transceiver)
* customer counters live for the whole ksmppd lifetime (survive bind drops) → exported directly, no accumulator needed

## Metrics (prefix `ksmppd_`)
| Area | Metrics |
|---|---|
| scrape | `up`, `scrape_duration_seconds`, `scrape_errors_total`, `scrapes_total`, `last_scrape_success_timestamp_seconds` |
| server | `uptime_seconds`, `known_esmes`, `esmes_connected`, `binds_active`, `binds_active_by_type{type}`, `pdus_total{direction}`, `load_pdus_per_second{direction,window}`, `messages_total{kind}` |
| customer | `esme_binds`, `esme_max_binds`, `esme_binds_by_type{type}`, `esme_throughput_limit` (TPS limit), `esme_load_pdus_per_second{direction,window}`, `esme_mt/mo/dlr/errors_total`, `esme_connected`, `esme_state_since_timestamp_seconds`, `esme_last_connected_timestamp_seconds`, `esme_open_acks`, `esme_queued{direction}`, `esme_pending_routing`, `esme_connected_ips`, `esme_simulate_binds`, `esme_bind_uptime_max/min_seconds`, `esme_bind_connects_total{type}`, `esme_bind_disconnects_total{type}` |
| customer × IP | `esme_ip_binds`, `esme_ip_load_pdus_per_second{direction}` |
| per bind (`per_bind_metrics: true`) | `bind_uptime_seconds`, `bind_open_acks`, `bind_simulate`, `bind_load_pdus_per_second`, `bind_queued`, `bind_pending_routing`, `bind_pdus_total`, `bind_mt/mo/dlr/errors_total` (labels bind_id, ip, type) |

## TPS model (as agreed)
* **TPS limit** = `max-inbound-load` (whole customer)
* **Achieved TPS** = inbound (MT accepted + rejected) + outbound (DLR + MO) per second, 1-min average
* **Utilisation** = achieved / limit · **Headroom** = limit − achieved

## Dashboard (`../../dashboards/ksmppd_dashboard.json`, uid `ksmppd-monitoring`)
Variables: server, customer, source IP, bind type (Transceiver/Transmitter/Receiver).
Sections: Servers & peak throughput (overall / server / customer / bind) · Overview · TPS limit & utilisation ·
Traffic · Customers · Binds / sessions · Exporter health.

Rebuild: `python3 tools/gen_ksmppd_dashboard.py` (uses `tools/_helpers.py`).
