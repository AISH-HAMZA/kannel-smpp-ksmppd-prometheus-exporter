# Kannel bearerbox exporter

**Deploy:** `sudo ./deploy/install.sh kannel --local --password PW` (on the Kannel bearerbox server) or `--target NAME=URL` (central) – see [docs/deploy-kannel.md](../../docs/deploy-kannel.md).

`kannel_exporter.py` – v1.1.0 – port **9879** – scrapes the bearerbox `status.xml`.
Works for vanilla Kannel 1.4.x (apt), SVN builds (`svn-r5336M`) and Kannel-HA (`svn-b-r430`).
Verified against the Kannel 1.4.5 source (`gw/bearerbox.c`, `gw/bb_smscconn.c`) and tested live with the real
apt Kannel 1.4.5 (bearerbox + smsbox + fakesmsc + a dead SMPP link with `instances = 2`).

## Semantics
* gateway: sms received = MO from SMSCs · sms sent = MT to SMSCs · dlr received = DLRs from SMSCs ·
  dlr queued = DLRs waiting in dlr-storage · storesize = store (-1 = disabled)
* SMSC link: sms sent = MT · sms received = MO · failed = MT failed · queued = MT waiting · dlr received
* status: `online <s>` | `connecting` | `re-connecting` | `disconnected` | `dead`
  → `kannel_smsc_state` 4 / 3 / 2 / 1 / 0
* load triplet = last 60 s / 300 s / since start
* repeated admin-ids (instances) are made unique: `name`, `name#2`, `name#3`
* SMSC name `SMPP:198.51.100.7:2775/2775:ESME_DEMO_01:smpp` → protocol, host, port, receive port,
  **SMSC username** (system-id), system-type (`kannel_smsc_connection_info`)
* a wrong password returns HTTP 200 `<gateway>Denied</gateway>` → detected, `kannel_up = 0`
* Kannel-HA extras: `sms_ha_route`, SMSC `queue_type`, per-box open acks / ack buffer / failed / traffic / load

## Metrics (prefix `kannel_`)
| Area | Metrics |
|---|---|
| scrape | `up`, `scrape_duration_seconds`, `scrape_errors_total`, `scrapes_total`, `last_scrape_success_timestamp_seconds` |
| gateway | `gateway_info{product,flavour,build_type,version,build,hostname,host_ip,os_release,dlr_storage}`, `gateway_state{state}`, `uptime_seconds`, `sms_total{direction}`, `sms_queued`, `dlr_total`, `dlr_queued`, `wdp_total`, `wdp_queued`, `sms_store_size`, `sms_ha_route`, `load_messages_per_second{type,direction,window}`, `smscs_configured`, `smscs_online`, `boxes_connected{box_type}` |
| SMSC link (labels smsc_id, admin_id) | `smsc_info`, `smsc_connection_info{protocol,host,port,receive_port,username,system_type}`, `smsc_online`, `smsc_state`, `smsc_online_seconds`, `smsc_state_since_timestamp_seconds`, `smsc_state_drops_total`, `smsc_sms_total{direction}`, `smsc_dlr_total{direction}`, `smsc_failed_total`, `smsc_queued`, `smsc_load_messages_per_second{type,direction,window}` |
| boxes | `box_info`, `box_online`, `box_uptime_seconds`, `box_queue`, HA: `box_open_acks`, `box_ack_buffer`, `box_failed_total`, `box_messages_total{type,direction}`, `box_load_messages_per_second` |

## Dashboard (`../../dashboards/kannel_dashboard.json`, uid `kannel-bearerbox`)
Variables: server, SMSC-ID (route), link (admin-id), SMSC username, box.
Sections: Gateways & peak throughput (build info SVN vs apt, health, peak MT/DLR/MO per server/route/link) ·
Overview · Traffic · SMSC / operator links (state counters, route availability history, *links with problems*
history, links table with username/host/port, top-10s, DLR ratio capped at 200 %) ·
SMSC usernames (gauges, overview table, history) · Boxes · Exporter health.

Rebuild: `python3 tools/gen_kannel_dashboard.py` (uses `tools/_helpers.py`).
