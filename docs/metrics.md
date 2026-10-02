# Metrics reference

Generated from the live output of each exporter against the mock gateway (`examples/mock_gateway.py`).
Every series carries a `server` label (the target `name` from the config). Counters end in `_total`.
Per-exporter design details: [smppbox](../exporters/smppbox/README.md) · [KSMPPD](../exporters/ksmppd/README.md) · [Kannel](../exporters/kannel/README.md).

## smppbox exporter (Kannel / Kannel-HA smppbox) - port 9877

| Metric | Type | Labels | Description |
|---|---|---|---|
| `smppbox_bearerbox_connected` | gauge | `server` | 1 if smppbox is connected to bearerbox |
| `smppbox_cpu_seconds_total` | counter | `server` | CPU time consumed by smppbox |
| `smppbox_esme_active_sessions` | gauge | `esme`, `server`, `smsc_id`, `type` | Active sessions per customer by bind type |
| `smppbox_esme_connected` | gauge | `esme`, `server`, `smsc_id` | 1 = customer has at least one bound session (connected), 0 = disconnected |
| `smppbox_esme_connected_ips` | gauge | `esme`, `server`, `smsc_id` | Distinct source IPs the customer is bound from |
| `smppbox_esme_ip_messages_failed_total` | counter | `esme`, `ip`, `server`, `smsc_id` | Failed messages for the customer IP |
| `smppbox_esme_ip_messages_received_total` | counter | `esme`, `ip`, `server`, `smsc_id` | Messages received from the customer IP |
| `smppbox_esme_ip_messages_sent_total` | counter | `esme`, `ip`, `server`, `smsc_id` | Messages sent to the customer IP |
| `smppbox_esme_ip_reported_in_rate` | gauge | `esme`, `ip`, `server`, `smsc_id` | smppbox reported inbound msg/s from the customer IP |
| `smppbox_esme_ip_reported_out_rate` | gauge | `esme`, `ip`, `server`, `smsc_id` | smppbox reported outbound msg/s to the customer IP |
| `smppbox_esme_ip_sessions` | gauge | `esme`, `ip`, `server`, `smsc_id` | Active sessions per customer source IP |
| `smppbox_esme_last_connected_timestamp_seconds` | gauge | `esme`, `server`, `smsc_id` | Unix time the customer was last seen with at least one session |
| `smppbox_esme_messages_failed_total` | counter | `esme`, `server`, `smsc_id` | Failed messages for the customer |
| `smppbox_esme_messages_received_total` | counter | `esme`, `server`, `smsc_id` | Messages received from the customer (submit_sm) |
| `smppbox_esme_messages_sent_total` | counter | `esme`, `server`, `smsc_id` | Messages sent to the customer (deliver_sm: DLR/MO) |
| `smppbox_esme_open_acks` | gauge | `esme`, `server`, `smsc_id` | Open (unacknowledged) PDUs for the customer |
| `smppbox_esme_reported_in_rate` | gauge | `esme`, `server`, `smsc_id` | smppbox reported inbound msg/s from the customer |
| `smppbox_esme_reported_out_rate` | gauge | `esme`, `server`, `smsc_id` | smppbox reported outbound msg/s to the customer |
| `smppbox_esme_resp_pdus_total` | counter | `esme`, `server`, `smsc_id` | Response PDUs for the customer |
| `smppbox_esme_session_uptime_max_seconds` | gauge | `esme`, `server`, `smsc_id` | Age of the oldest session of the customer |
| `smppbox_esme_session_uptime_min_seconds` | gauge | `esme`, `server`, `smsc_id` | Age of the newest session (low = recent reconnect) |
| `smppbox_esme_state_since_timestamp_seconds` | gauge | `esme`, `server`, `smsc_id` | Unix time the customer entered its current connected/disconnected state (as seen by the exporter) |
| `smppbox_esme_type_connects_total` | counter | `esme`, `server`, `smsc_id`, `type` | New binds (session connects) seen per customer bind type |
| `smppbox_esme_type_disconnects_total` | counter | `esme`, `server`, `smsc_id`, `type` | Sessions that disappeared (unbind/drop) per customer bind type |
| `smppbox_esme_type_messages_failed_total` | counter | `esme`, `server`, `smsc_id`, `type` | Failed messages per customer bind type |
| `smppbox_esme_type_messages_received_total` | counter | `esme`, `server`, `smsc_id`, `type` | Messages received from the customer per bind type |
| `smppbox_esme_type_messages_sent_total` | counter | `esme`, `server`, `smsc_id`, `type` | Messages sent to the customer per bind type |
| `smppbox_esme_type_open_acks` | gauge | `esme`, `server`, `smsc_id`, `type` | Open (unacknowledged) PDUs per customer bind type |
| `smppbox_esme_type_reported_in_rate` | gauge | `esme`, `server`, `smsc_id`, `type` | smppbox reported inbound msg/s per customer bind type |
| `smppbox_esme_type_reported_out_rate` | gauge | `esme`, `server`, `smsc_id`, `type` | smppbox reported outbound msg/s per customer bind type |
| `smppbox_esme_type_resp_pdus_total` | counter | `esme`, `server`, `smsc_id`, `type` | Response PDUs per customer bind type |
| `smppbox_esme_type_session_uptime_max_seconds` | gauge | `esme`, `server`, `smsc_id`, `type` | Age of oldest session per customer bind type |
| `smppbox_esme_type_session_uptime_min_seconds` | gauge | `esme`, `server`, `smsc_id`, `type` | Age of newest session per customer bind type |
| `smppbox_exporter_build_info` | gauge | `version` | Exporter version |
| `smppbox_exporter_scrape_interval_seconds` | gauge |  | Configured scrape interval |
| `smppbox_exporter_targets` | gauge |  | Configured scrape targets |
| `smppbox_gateway_info` | gauge | `build`, `host_ip`, `hostname`, `mysql_client`, `os_release`, `product`, `resp_mode`, `server`, `state`, `version` | smppbox build / host information (value always 1) |
| `smppbox_gateway_running` | gauge | `server` | 1 if smppbox reports state 'running' |
| `smppbox_last_scrape_success_timestamp_seconds` | gauge | `server` | Unix time of the last successful scrape |
| `smppbox_load_messages_per_second` | gauge | `direction`, `server`, `side`, `window` | Gateway reported load (msg/s) for window 1m/5m/overall |
| `smppbox_login_info` | gauge | `esme`, `flags`, `keyword`, `resp_mode`, `server`, `shortcode`, `smsc_id`, `state` | Configured login (value always 1) |
| `smppbox_login_online` | gauge | `esme`, `server`, `smsc_id` | 1 if the customer login is online |
| `smppbox_login_sessions` | gauge | `esme`, `server`, `smsc_id`, `type` | Bound sessions per bind type as reported on the login |
| `smppbox_login_sessions_max` | gauge | `esme`, `server`, `smsc_id`, `type` | Maximum allowed sessions per bind type |
| `smppbox_logins_configured` | gauge | `server` | Configured ESME logins |
| `smppbox_logins_online` | gauge | `server` | Configured ESME logins currently online |
| `smppbox_memory_bytes` | gauge | `server` | Memory used by smppbox |
| `smppbox_messages_total` | counter | `direction`, `server`, `side` | Messages counted by smppbox. side=bearerbox/esme, direction=received/sent |
| `smppbox_plugin_active` | gauge | `chain`, `plugin`, `position`, `server` | 1 if the plugin state is 'active' |
| `smppbox_plugin_chain_plugins` | gauge | `chain`, `server` | Number of plugins in a trigger chain |
| `smppbox_plugin_db_connections_idle` | gauge | `chain`, `plugin`, `position`, `server` | Idle database connections of a DB plugin |
| `smppbox_plugin_db_connections_max` | gauge | `chain`, `plugin`, `position`, `server` | Size of the DB connection pool of a DB plugin |
| `smppbox_plugin_info` | gauge | `args`, `async`, `chain`, `plugin`, `position`, `server`, `state` | Loaded plugin (value always 1) |
| `smppbox_plugin_sql_queue` | gauge | `chain`, `plugin`, `position`, `server` | SQL statements waiting in queue |
| `smppbox_queued_messages` | gauge | `direction`, `server`, `side` | Messages currently queued |
| `smppbox_scrape_duration_seconds` | gauge | `server` | Duration of the last status page scrape |
| `smppbox_scrape_errors_total` | counter | `server` | Failed status page scrapes since exporter start |
| `smppbox_scrapes_total` | counter | `server` | Status page scrapes since exporter start |
| `smppbox_session_failed` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Failed on session (per-session, high cardinality) |
| `smppbox_session_in_rate` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Reported inbound msg/s (per-session, high cardinality) |
| `smppbox_session_online_seconds` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Session age (per-session, high cardinality) |
| `smppbox_session_open_acks` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Open acks on session (per-session, high cardinality) |
| `smppbox_session_out_rate` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Reported outbound msg/s (per-session, high cardinality) |
| `smppbox_session_received` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Messages received on session (per-session, high cardinality) |
| `smppbox_session_sent` | gauge | `esme`, `ip`, `port`, `server`, `smsc_id`, `type` | Messages sent on session (per-session, high cardinality) |
| `smppbox_sessions_active` | gauge | `server` | Active SMPP sessions |
| `smppbox_sessions_active_by_type` | gauge | `server`, `type` | Active SMPP sessions by bind type |
| `smppbox_store_size_messages` | gauge | `server` | Messages in the smppbox store |
| `smppbox_store_status` | gauge | `server` | Store status code as reported |
| `smppbox_up` | gauge | `server` | 1 if the last scrape of the smppbox status page succeeded |
| `smppbox_uptime_seconds` | gauge | `server` | smppbox uptime |

## KSMPPD exporter - port 9878

| Metric | Type | Labels | Description |
|---|---|---|---|
| `ksmppd_bind_dlr_total` | counter | `bind_id`, `esme`, `ip`, `server`, `type` | DLR delivered on the bind |
| `ksmppd_bind_errors_total` | counter | `bind_id`, `esme`, `ip`, `server`, `type` | submit_sm rejected on the bind |
| `ksmppd_bind_load_pdus_per_second` | gauge | `bind_id`, `direction`, `esme`, `ip`, `server`, `type` | Last-second PDU load of the bind |
| `ksmppd_bind_mo_total` | counter | `bind_id`, `esme`, `ip`, `server`, `type` | MO delivered on the bind |
| `ksmppd_bind_mt_total` | counter | `bind_id`, `esme`, `ip`, `server`, `type` | submit_sm accepted on the bind |
| `ksmppd_bind_open_acks` | gauge | `bind_id`, `esme`, `ip`, `server`, `type` | Unacknowledged PDUs on the bind |
| `ksmppd_bind_pdus_total` | counter | `bind_id`, `direction`, `esme`, `ip`, `server`, `type` | PDUs processed on the bind |
| `ksmppd_bind_pending_routing` | gauge | `bind_id`, `esme`, `ip`, `server`, `type` | PDUs of the bind waiting for routing |
| `ksmppd_bind_queued` | gauge | `bind_id`, `direction`, `esme`, `ip`, `server`, `type` | Queued PDUs on the bind |
| `ksmppd_bind_simulate` | gauge | `bind_id`, `esme`, `ip`, `server`, `type` | 1 if the bind runs in simulate mode |
| `ksmppd_bind_uptime_seconds` | gauge | `bind_id`, `esme`, `ip`, `server`, `type` | Bind age |
| `ksmppd_binds_active` | gauge | `server` | Active binds (sessions) on the server |
| `ksmppd_binds_active_by_type` | gauge | `server`, `type` | Active binds by bind type (trx/tx/rx) |
| `ksmppd_esme_bind_connects_total` | counter | `esme`, `server`, `type` | New binds seen by the exporter |
| `ksmppd_esme_bind_disconnects_total` | counter | `esme`, `server`, `type` | Binds that disappeared (unbind / drop) seen by the exporter |
| `ksmppd_esme_bind_uptime_max_seconds` | gauge | `esme`, `server` | Age of the oldest bind |
| `ksmppd_esme_bind_uptime_min_seconds` | gauge | `esme`, `server` | Age of the newest bind (small = recent reconnect) |
| `ksmppd_esme_binds` | gauge | `esme`, `server` | Active binds of the customer |
| `ksmppd_esme_binds_by_type` | gauge | `esme`, `server`, `type` | Active binds of the customer by bind type |
| `ksmppd_esme_connected` | gauge | `esme`, `server` | 1 = customer has at least one bind, 0 = disconnected |
| `ksmppd_esme_connected_ips` | gauge | `esme`, `server` | Distinct source IPs the customer is bound from |
| `ksmppd_esme_dlr_total` | counter | `esme`, `server` | Delivery reports delivered to the customer |
| `ksmppd_esme_errors_total` | counter | `esme`, `server` | submit_sm rejected (error response sent to the customer) |
| `ksmppd_esme_ip_binds` | gauge | `esme`, `ip`, `server` | Active binds per customer source IP |
| `ksmppd_esme_ip_load_pdus_per_second` | gauge | `direction`, `esme`, `ip`, `server` | Last-second PDU load per customer source IP |
| `ksmppd_esme_last_connected_timestamp_seconds` | gauge | `esme`, `server` | Unix time the customer last had a bind |
| `ksmppd_esme_load_pdus_per_second` | gauge | `direction`, `esme`, `server`, `window` | Customer PDU load reported by ksmppd. window=since_start/1s/1m |
| `ksmppd_esme_max_binds` | gauge | `esme`, `server` | Maximum binds allowed for the customer |
| `ksmppd_esme_mo_total` | counter | `esme`, `server` | MO messages delivered to the customer |
| `ksmppd_esme_mt_total` | counter | `esme`, `server` | submit_sm accepted from the customer (MT) |
| `ksmppd_esme_open_acks` | gauge | `esme`, `server` | Unacknowledged PDUs over all binds of the customer |
| `ksmppd_esme_pending_routing` | gauge | `esme`, `server` | PDUs waiting for routing over all binds |
| `ksmppd_esme_queued` | gauge | `direction`, `esme`, `server` | Queued PDUs over all binds. direction=inbound/outbound |
| `ksmppd_esme_simulate_binds` | gauge | `esme`, `server` | Binds running in simulate mode |
| `ksmppd_esme_state_since_timestamp_seconds` | gauge | `esme`, `server` | Unix time the customer entered its current state |
| `ksmppd_esme_throughput_limit` | gauge | `esme`, `server` | max-inbound-load: TPS limit of the customer (all sessions together), 0 = unlimited |
| `ksmppd_esmes_connected` | gauge | `server` | Customers with at least one bind |
| `ksmppd_exporter_build_info` | gauge | `version` | Exporter version |
| `ksmppd_exporter_scrape_interval_seconds` | gauge |  | Configured scrape interval |
| `ksmppd_exporter_targets` | gauge |  | Configured targets |
| `ksmppd_known_esmes` | gauge | `server` | Unique ESMEs (customers) ksmppd knows since start |
| `ksmppd_last_scrape_success_timestamp_seconds` | gauge | `server` | Unix time of the last successful scrape |
| `ksmppd_load_pdus_per_second` | gauge | `direction`, `server`, `window` | Server PDU load reported by ksmppd. window=since_start/1s/1m |
| `ksmppd_messages_total` | counter | `kind`, `server` | Messages summed over all customers. kind=mt/mo/dlr/errors |
| `ksmppd_pdus_total` | counter | `direction`, `server` | All PDUs processed. direction=inbound (from ESMEs) / outbound (to ESMEs) |
| `ksmppd_scrape_duration_seconds` | gauge | `server` | Duration of the last status page scrape |
| `ksmppd_scrape_errors_total` | counter | `server` | Failed status page scrapes since exporter start |
| `ksmppd_scrapes_total` | counter | `server` | Status page scrapes since exporter start |
| `ksmppd_up` | gauge | `server` | 1 if the last scrape of the ksmppd status page succeeded |
| `ksmppd_uptime_seconds` | gauge | `server` | ksmppd uptime (from /uptime.xml) |

## Kannel bearerbox exporter - port 9879

| Metric | Type | Labels | Description |
|---|---|---|---|
| `kannel_box_ack_buffer` | gauge | `box_id`, `box_type`, `server` | Kannel-HA: ack buffer fill of the box |
| `kannel_box_failed_total` | counter | `box_id`, `box_type`, `server` | Kannel-HA: failed messages of the box |
| `kannel_box_info` | gauge | `box_id`, `box_type`, `ip`, `port`, `server`, `ssl`, `status` | Connected box information (value 1) |
| `kannel_box_load_messages_per_second` | gauge | `box_id`, `box_type`, `direction`, `server`, `type`, `window` | Kannel-HA box load. type, direction=incoming/outgoing, window |
| `kannel_box_messages_total` | counter | `box_id`, `box_type`, `direction`, `server`, `type` | Kannel-HA: messages from/to the box. type=sms/dlr direction=received/sent |
| `kannel_box_online` | gauge | `box_id`, `box_type`, `server` | 1 if the box is on-line |
| `kannel_box_open_acks` | gauge | `box_id`, `box_type`, `server` | Kannel-HA: open acks towards the box |
| `kannel_box_queue` | gauge | `box_id`, `box_type`, `server` | Messages queued towards the box |
| `kannel_box_uptime_seconds` | gauge | `box_id`, `box_type`, `server` | Seconds the box has been connected |
| `kannel_boxes_connected` | gauge | `box_type`, `server` | Boxes (smsbox/wapbox/ksmppd/smppbox) connected |
| `kannel_dlr_queued` | gauge | `server` | DLR entries waiting in dlr-storage for their delivery report |
| `kannel_dlr_total` | counter | `direction`, `server` | DLRs counted by bearerbox. direction=received (from SMSCs) / sent |
| `kannel_exporter_build_info` | gauge | `version` | Exporter version |
| `kannel_exporter_targets` | gauge |  | Configured targets |
| `kannel_gateway_info` | gauge | `build`, `build_type`, `dlr_storage`, `flavour`, `host_ip`, `hostname`, `os_release`, `product`, `server`, `version` | bearerbox build / host information (value 1) |
| `kannel_gateway_state` | gauge | `server`, `state` | 1 for the current bearerbox state (running, suspended, isolated, full, shutting down) |
| `kannel_last_scrape_success_timestamp_seconds` | gauge | `server` | Unix time of the last successful scrape |
| `kannel_load_messages_per_second` | gauge | `direction`, `server`, `type`, `window` | bearerbox load. type=sms/dlr, direction=inbound/outbound, window=1m/5m/overall |
| `kannel_scrape_duration_seconds` | gauge | `server` | Duration of the last status page scrape |
| `kannel_scrape_errors_total` | counter | `server` | Failed status page scrapes since exporter start |
| `kannel_scrapes_total` | counter | `server` | Status page scrapes since exporter start |
| `kannel_sms_ha_route` | gauge | `server` | Kannel-HA: SMS waiting for HA routing |
| `kannel_sms_queued` | gauge | `direction`, `server` | SMS waiting in bearerbox queues. direction=received/sent |
| `kannel_sms_store_size` | gauge | `server` | Messages in the store-file / store (-1 = store disabled) |
| `kannel_sms_total` | counter | `direction`, `server` | SMS counted by bearerbox. direction=received (MO from SMSCs) / sent (MT to SMSCs) |
| `kannel_smsc_connection_info` | gauge | `admin_id`, `host`, `port`, `protocol`, `receive_port`, `server`, `smsc_id`, `system_type`, `username` | SMSC link connection details parsed from the name (value 1): protocol, operator host, port, receive port, SMSC username (system-id), system-type |
| `kannel_smsc_dlr_total` | counter | `admin_id`, `direction`, `server`, `smsc_id` | DLRs on the link. direction=received (from operator) / sent |
| `kannel_smsc_failed_total` | counter | `admin_id`, `server`, `smsc_id` | MT messages that failed on the link |
| `kannel_smsc_info` | gauge | `admin_id`, `name`, `queue_type`, `server`, `smsc_id`, `status` | SMSC link information (value 1) |
| `kannel_smsc_load_messages_per_second` | gauge | `admin_id`, `direction`, `server`, `smsc_id`, `type`, `window` | Link load. type=sms/dlr direction=inbound/outbound window=1m/5m/overall |
| `kannel_smsc_online` | gauge | `admin_id`, `server`, `smsc_id` | 1 if the SMSC link is online |
| `kannel_smsc_online_seconds` | gauge | `admin_id`, `server`, `smsc_id` | Seconds the link has been online (0 if not online) |
| `kannel_smsc_queued` | gauge | `admin_id`, `server`, `smsc_id` | MT messages queued for the link |
| `kannel_smsc_sms_total` | counter | `admin_id`, `direction`, `server`, `smsc_id` | SMS on the link. direction=sent (MT to operator) / received (MO from operator) |
| `kannel_smsc_state` | gauge | `admin_id`, `server`, `smsc_id` | SMSC state code: 4 online, 3 re-connecting, 2 connecting, 1 disconnected, 0 dead |
| `kannel_smsc_state_drops_total` | counter | `admin_id`, `server`, `smsc_id` | Times the link left the online state (seen by the exporter) |
| `kannel_smsc_state_since_timestamp_seconds` | gauge | `admin_id`, `server`, `smsc_id` | Unix time the link entered its current state |
| `kannel_smscs_configured` | gauge | `server` | SMSC links configured |
| `kannel_smscs_online` | gauge | `server` | SMSC links online |
| `kannel_up` | gauge | `server` | 1 if the last scrape of the bearerbox status page succeeded |
| `kannel_uptime_seconds` | gauge | `server` | bearerbox uptime |
| `kannel_wdp_queued` | gauge | `direction`, `server` | WDP packets queued. direction=received/sent |
| `kannel_wdp_total` | counter | `direction`, `server` | WDP packets (WAP). direction=received/sent |
