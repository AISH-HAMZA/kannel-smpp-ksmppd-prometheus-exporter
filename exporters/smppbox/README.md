# smppbox exporter (Kannel / Kannel-HA smppbox)

`smpp_exporter.py` – v1.2.0 – port **9877** – scrapes `status.xml` of every smppbox.

## Direction convention (smppbox point of view)
* **received** = PDUs from the ESME/customer (submit_sm, MT)  ·  **sent** = PDUs to the customer (deliver_sm: DLR/MO)
* load triplets `(a,b,c)` = last 1 min / 5 min / since start

## Metrics (prefix `smppbox_`)
| Area | Metrics |
|---|---|
| scrape | `up`, `scrape_duration_seconds`, `scrape_errors_total`, `scrapes_total`, `last_scrape_success_timestamp_seconds` |
| gateway | `gateway_info{version,build,hostname,host_ip,os_release,mysql_client,state,resp_mode}`, `gateway_running`, `uptime_seconds`, `cpu_seconds_total`, `memory_bytes`, `bearerbox_connected`, `messages_total{side,direction}`, `queued_messages`, `load_messages_per_second{side,direction,window}`, `store_size_messages`, `store_status`, `logins_configured`, `logins_online`, `sessions_active`, `sessions_active_by_type{type}` |
| login (customer) | `login_info`, `login_online`, `login_sessions{type}`, `login_sessions_max{type}` |
| customer (from sessions) | `esme_active_sessions{type}`, `esme_messages_received/sent/failed_total`, `esme_resp_pdus_total`, `esme_open_acks`, `esme_reported_in/out_rate`, `esme_connected_ips`, `esme_session_uptime_max/min_seconds`, `esme_connected`, `esme_state_since_timestamp_seconds`, `esme_last_connected_timestamp_seconds` |
| customer × bind type (trcv/trans/recv) | `esme_type_messages_received/sent/failed_total`, `esme_type_resp_pdus_total`, `esme_type_open_acks`, `esme_type_reported_in/out_rate`, `esme_type_session_uptime_max/min_seconds`, `esme_type_connects_total`, `esme_type_disconnects_total` |
| customer × source IP | `esme_ip_sessions`, `esme_ip_messages_received/sent/failed_total`, `esme_ip_reported_in/out_rate` |
| per session (`per_session_metrics: true`) | `session_online_seconds`, `session_received/sent/failed`, `session_open_acks`, `session_in_rate`, `session_out_rate` |
| plugins | `plugin_info`, `plugin_active`, `plugin_chain_plugins`, `plugin_db_connections_idle/max`, `plugin_sql_queue` |

## Counter design (important)
smppbox only reports **per-session** counters, which reset when a customer reconnects. The exporter keeps
monotonic per-customer totals by adding per-session deltas (`SessionAccumulator`):
* first scrape after exporter start = baseline only (otherwise billions of historic messages look like a burst)
* a session missing from one/two scrapes is remembered for 1 h and continues from its last value
* a genuinely new session (age < 2×interval+30 s) is counted from zero; older unknown sessions = baseline
* any jump above `max_customer_rate` × window is discarded as a glitch
These fixed the "billions / 24K msg/s" spikes seen in v1.0/v1.1.

## Dashboard (`../../dashboards/smppbox_dashboard.json`, uid `kannel-smppbox`)
Variables: datasource, SMPP server, SMSC-ID, bind type, customer (ESME).
Sections: Gateways & peak throughput (build info, peak in/out overall / per server / per customer / per session) ·
Overview · Traffic · Servers · Customers (overview table, top-10s, rates, failure %, connection history, sessions) ·
Customer connections by bind type · Source IPs · Plugins & DB · Exporter health. Every panel has hover help.
Customer tables only list customers of servers that currently report (ghost rows of removed servers are hidden).

Rebuild: `python3 tools/gen_smppbox_dashboard.py` (hover texts in `tools/smppbox_desc.py`).
