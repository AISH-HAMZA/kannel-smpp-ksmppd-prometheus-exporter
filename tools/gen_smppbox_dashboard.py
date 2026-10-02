#!/usr/bin/env python3
"""Generates smppbox_dashboard.json for Grafana (import via Dashboards > New > Import)."""
import json
import os
HERE = os.path.dirname(os.path.abspath(__file__))

DS = {"type": "prometheus", "uid": "${datasource}"}
S = 'server=~"$server"'
C = 'server=~"$server", smsc_id=~"$smsc_id", esme=~"$esme"'
RI = "$__rate_interval"
_id = [0]
panels = []
Y = [0]


def nid():
    _id[0] += 1
    return _id[0]


def tgt(expr, legend="", ref="A", instant=False, fmt="time_series"):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref, "format": fmt}
    if instant:
        t.update({"instant": True, "range": False})
    return t


def row(title, collapsed=False):
    panels.append({"type": "row", "title": title, "id": nid(), "collapsed": collapsed,
                   "gridPos": {"h": 1, "w": 24, "x": 0, "y": Y[0]}, "panels": []})
    Y[0] += 1


def place(p, x, w, h):
    p["gridPos"] = {"h": h, "w": w, "x": x, "y": Y[0]}
    p["id"] = nid()
    p["datasource"] = DS
    panels.append(p)


def newline(h):
    Y[0] += h


def stat(title, expr, unit="short", color="blue", thresholds=None, desc="", decimals=None, mappings=None,
         spark=True):
    steps = thresholds or [{"color": color, "value": None}]
    p = {"type": "stat", "title": title, "description": desc, "targets": [tgt(expr, instant=not spark)],
         "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
                                      "thresholds": {"mode": "absolute", "steps": steps},
                                      "mappings": mappings or []}, "overrides": []},
         "options": {"colorMode": "background", "graphMode": "area" if spark else "none",
                     "justifyMode": "center", "textMode": "value", "wideLayout": True,
                     "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p


def ts(title, targets, unit="short", desc="", stack=False, fill=12, legend_calcs=("mean", "max", "lastNotNull"),
       overrides=None, min0=True, draw="line"):
    d = {"unit": unit, "color": {"mode": "palette-classic"},
         "custom": {"drawStyle": draw, "lineWidth": 2, "fillOpacity": fill, "gradientMode": "opacity",
                    "showPoints": "never", "spanNulls": True, "lineInterpolation": "smooth",
                    "stacking": {"mode": "normal" if stack else "none", "group": "A"},
                    "axisSoftMin": 0 if min0 else None}}
    return {"type": "timeseries", "title": title, "description": desc, "targets": targets,
            "fieldConfig": {"defaults": d, "overrides": overrides or []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": list(legend_calcs),
                                   "sortBy": "Max", "sortDesc": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def bargauge(title, expr, legend, unit="short", desc="", color_mode="continuous-BlPu"):
    return {"type": "bargauge", "title": title, "description": desc,
            "targets": [tgt(expr, legend, instant=True)],
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": color_mode}, "min": 0}, "overrides": []},
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                        "valueMode": "color", "namePlacement": "left", "sizing": "auto",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def ov(name, props):
    return {"matcher": {"id": "byName", "options": name}, "properties": props}


def unit(u):
    return {"id": "unit", "value": u}


def cell(mode, extra=None):
    c = {"type": mode}
    if extra:
        c.update(extra)
    return {"id": "custom.cellOptions", "value": c}


UPDOWN = {"id": "mappings", "value": [{"type": "value", "options": {
    "1": {"text": "UP", "color": "green", "index": 0}, "0": {"text": "DOWN", "color": "red", "index": 1}}}]}
CONN = {"id": "mappings", "value": [{"type": "value", "options": {
    "1": {"text": "CONNECTED", "color": "green", "index": 0}, "0": {"text": "DISCONNECTED", "color": "red", "index": 1}}}]}
ONOFF = {"id": "mappings", "value": [{"type": "value", "options": {
    "1": {"text": "ONLINE", "color": "green", "index": 0}, "0": {"text": "OFFLINE", "color": "red", "index": 1}}}]}


def table(title, targets, rename, order, overrides, desc="", sort=None, hide_extra=()):
    exclude = {"Time": True}
    for h in hide_extra:
        exclude[h] = True
    return {"type": "table", "title": title, "description": desc, "targets": targets,
            "transformations": [{"id": "merge", "options": {}},
                                {"id": "organize", "options": {"excludeByName": exclude, "renameByName": rename,
                                                               "indexByName": {k: i for i, k in enumerate(order)}}}],
            "fieldConfig": {"defaults": {"custom": {"align": "auto", "filterable": True,
                                                    "cellOptions": {"type": "auto"}}},
                            "overrides": overrides},
            "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False},
                        "sortBy": sort or []}}


TYPEMAP = {"id": "mappings", "value": [{"type": "value", "options": {
    "trcv": {"text": "Transceiver (trcv)", "color": "blue", "index": 0},
    "trans": {"text": "Transmitter (trans)", "color": "purple", "index": 1},
    "recv": {"text": "Receiver (recv)", "color": "orange", "index": 2}}}]}
# =========================================================== GATEWAY INFO + PEAKS (top of dashboard)
row("Gateways & Peak Throughput  -  $server")
place(table("Gateway / Build Information", [tgt(f'smppbox_gateway_info{{{S}}}', ref="A", instant=True, fmt="table")],
            {"server": "Server", "product": "Product", "version": "Version", "hostname": "Hostname",
             "host_ip": "IP", "os_release": "OS / Kernel", "build": "Build", "resp_mode": "Resp mode",
             "mysql_client": "MySQL client", "state": "State"},
            ["Server", "State", "Hostname", "IP", "Product", "Version", "Build", "OS / Kernel", "Resp mode",
             "MySQL client"],
            [ov("State", [cell("color-text"), {"id": "mappings", "value": [{"type": "value", "options": {
                "running": {"color": "green"}}}]}])],
            hide_extra=("__name__", "Value", "job", "instance")), 0, 24, 6)
newline(6)

PK = "[$__range:15s]"
IN_ALL = f'sum(rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[1m]))'
OUT_ALL = f'sum(rate(smppbox_messages_total{{{S}, side="esme", direction="sent"}}[1m]))'
place(stat("Peak Inbound (msg/s)", f'max_over_time({IN_ALL}{PK})', "mps", color="blue", spark=False,
           decimals=0), 0, 6, 4)
place(stat("Peak Outbound (msg/s)", f'max_over_time({OUT_ALL}{PK})', "mps", color="purple", spark=False,
           decimals=0), 6, 6, 4)
place(stat("Current Inbound (msg/s)", IN_ALL, "mps", color="blue", decimals=1), 12, 6, 4)
place(stat("Current Outbound (msg/s)", OUT_ALL, "mps", color="purple", decimals=1), 18, 6, 4)
newline(4)

MPS0 = [unit("mps"), {"id": "decimals", "value": 1}]
GAUGE = cell("gauge", {"mode": "gradient"})

# per server
bys = "sum by (server)"
place(table("Peak throughput per server", [
    tgt(f'max_over_time({bys} (rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[1m])){PK})',
        ref="A", instant=True, fmt="table"),
    tgt(f'max_over_time({bys} (rate(smppbox_messages_total{{{S}, side="esme", direction="sent"}}[1m])){PK})',
        ref="B", instant=True, fmt="table"),
    tgt(f'{bys} (rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[1m]))',
        ref="C", instant=True, fmt="table"),
    tgt(f'{bys} (rate(smppbox_messages_total{{{S}, side="esme", direction="sent"}}[1m]))',
        ref="D", instant=True, fmt="table")],
    {"server": "Server", "Value #A": "Peak inbound", "Value #B": "Peak outbound",
     "Value #C": "Current inbound", "Value #D": "Current outbound"},
    ["Server", "Peak inbound", "Peak outbound", "Current inbound", "Current outbound"],
    [ov("Peak inbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Peak outbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Current inbound", MPS0), ov("Current outbound", MPS0)],
    sort=[{"displayName": "Peak inbound", "desc": True}]), 0, 10, 8)

# per server + customer
byc = "sum by (server, esme, smsc_id)"
place(table("Peak throughput per server & customer", [
    tgt(f'max_over_time({byc} (rate(smppbox_esme_messages_received_total{{{C}}}[1m])){PK})',
        ref="A", instant=True, fmt="table"),
    tgt(f'max_over_time({byc} (rate(smppbox_esme_messages_sent_total{{{C}}}[1m])){PK})',
        ref="B", instant=True, fmt="table"),
    tgt(f'{byc} (rate(smppbox_esme_messages_received_total{{{C}}}[1m]))', ref="C", instant=True, fmt="table"),
    tgt(f'{byc} (rate(smppbox_esme_messages_sent_total{{{C}}}[1m]))', ref="D", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "smsc_id": "SMSC-ID", "Value #A": "Peak inbound",
     "Value #B": "Peak outbound", "Value #C": "Current inbound", "Value #D": "Current outbound"},
    ["Customer (ESME)", "Server", "SMSC-ID", "Peak inbound", "Peak outbound", "Current inbound", "Current outbound"],
    [ov("Peak inbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Peak outbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Current inbound", MPS0), ov("Current outbound", MPS0)],
    sort=[{"displayName": "Peak inbound", "desc": True}]), 10, 14, 8)
newline(8)

# per server + customer + session (needs per_session_metrics: true in the exporter config)
SL = C + ', type=~"$bind_type"'
place(table("Peak throughput per server, customer & session", [
    tgt(f'max_over_time(smppbox_session_in_rate{{{SL}}}[$__range])', ref="A", instant=True, fmt="table"),
    tgt(f'max_over_time(smppbox_session_out_rate{{{SL}}}[$__range])', ref="B", instant=True, fmt="table"),
    tgt(f'smppbox_session_in_rate{{{SL}}}', ref="C", instant=True, fmt="table"),
    tgt(f'smppbox_session_out_rate{{{SL}}}', ref="D", instant=True, fmt="table"),
    tgt(f'smppbox_session_online_seconds{{{SL}}}', ref="E", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "smsc_id": "SMSC-ID", "ip": "Source IP", "port": "Port",
     "type": "Bind type", "Value #A": "Peak inbound", "Value #B": "Peak outbound",
     "Value #C": "Current inbound", "Value #D": "Current outbound", "Value #E": "Session age"},
    ["Customer (ESME)", "Server", "Source IP", "Port", "Bind type", "Peak inbound", "Peak outbound",
     "Current inbound", "Current outbound", "Session age", "SMSC-ID"],
    [ov("Peak inbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Peak outbound", MPS0 + [GAUGE, {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Current inbound", MPS0), ov("Current outbound", MPS0), ov("Session age", [unit("s")]),
     ov("Bind type", [TYPEMAP, cell("color-text")])],
    sort=[{"displayName": "Peak inbound", "desc": True}]), 0, 24, 9)
newline(9)

# =========================================================== OVERVIEW
row("Overview  -  $server  /  $esme")
G = [{"color": "green", "value": None}]
place(stat("Servers UP", f'sum(smppbox_up{{{S}}})', thresholds=G, spark=False,
           desc="smppbox status pages scraped successfully"), 0, 3, 4)
place(stat("Servers DOWN", f'count(smppbox_up{{{S}}} == 0) or vector(0)', spark=False,
           thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]), 3, 3, 4)
place(stat("Submit rate (MT)", f'sum(rate(smppbox_esme_messages_received_total{{{C}}}[{RI}]))', "mps",
           color="blue", desc="submit_sm received from customers, msg/s"), 6, 3, 4)
place(stat("Deliver rate (DLR/MO)", f'sum(rate(smppbox_esme_messages_sent_total{{{C}}}[{RI}]))', "mps",
           color="purple", desc="deliver_sm sent to customers, msg/s"), 9, 3, 4)
place(stat("Failed rate", f'sum(rate(smppbox_esme_messages_failed_total{{{C}}}[{RI}]))', "mps",
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1},
                       {"color": "red", "value": 10}]), 12, 3, 4)
place(stat("Failure %", f'100 * sum(rate(smppbox_esme_messages_failed_total{{{C}}}[{RI}])) / '
                         f'clamp_min(sum(rate(smppbox_esme_messages_received_total{{{C}}}[{RI}])), 0.0001)',
           "percent", decimals=2, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 2},
                                              {"color": "red", "value": 5}]), 15, 3, 4)
place(stat("Submitted (range)", f'sum(increase(smppbox_esme_messages_received_total{{{C}}}[$__range]))',
           "short", color="blue", spark=False, desc="Messages submitted in selected time range"), 18, 3, 4)
place(stat("Failed (range)", f'sum(increase(smppbox_esme_messages_failed_total{{{C}}}[$__range]))',
           "short", color="orange", spark=False), 21, 3, 4)
newline(4)
place(stat("Customers connected", f'count(smppbox_esme_connected{{{C}}} == 1) or vector(0)', thresholds=G,
           spark=False), 0, 3, 4)
place(stat("Customers disconnected", f'count(smppbox_esme_connected{{{C}}} == 0) or vector(0)', spark=False,
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}]), 3, 3, 4)
place(stat("Active sessions", f'sum(smppbox_esme_active_sessions{{{C}}})', color="teal"), 6, 3, 4)
place(stat("Open acks", f'sum(smppbox_esme_open_acks{{{C}}})',
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 50},
                       {"color": "red", "value": 500}], desc="Unacknowledged PDUs in flight"), 9, 3, 4)
place(stat("Queued msgs", f'sum(smppbox_queued_messages{{{S}}})',
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 100},
                       {"color": "red", "value": 1000}]), 12, 3, 4)
place(stat("Store size", f'sum(smppbox_store_size_messages{{{S}}})',
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1000},
                       {"color": "red", "value": 10000}]), 15, 3, 4)
place(stat("Bearerbox disconnected", f'count(smppbox_bearerbox_connected{{{S}}} == 0) or vector(0)', spark=False,
           thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]), 18, 3, 4)
place(stat("smppbox memory", f'sum(smppbox_memory_bytes{{{S}}})', "bytes", color="purple"), 21, 3, 4)
newline(4)

# =========================================================== TRAFFIC
row("Traffic (gateway totals, server filter)")
place(ts("Overall throughput", [
    tgt(f'sum(rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[{RI}]))', "From ESMEs (submit)", "A"),
    tgt(f'sum(rate(smppbox_messages_total{{{S}, side="esme", direction="sent"}}[{RI}]))', "To ESMEs (deliver)", "B"),
    tgt(f'sum(rate(smppbox_messages_total{{{S}, side="bearerbox", direction="sent"}}[{RI}]))', "To bearerbox", "C"),
    tgt(f'sum(rate(smppbox_messages_total{{{S}, side="bearerbox", direction="received"}}[{RI}]))', "From bearerbox", "D")],
    "mps", desc="PDUs/s counted by smppbox, all selected servers combined"), 0, 12, 8)
place(ts("Submit rate per server", [
    tgt(f'sum by (server) (rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[{RI}]))',
        "{{server}}")], "mps", stack=True), 12, 12, 8)
newline(8)
place(ts("Deliver (DLR/MO) rate per server", [
    tgt(f'sum by (server) (rate(smppbox_messages_total{{{S}, side="esme", direction="sent"}}[{RI}]))',
        "{{server}}")], "mps", stack=True), 0, 12, 8)
place(ts("Gateway-reported load (1m avg)", [
    tgt(f'smppbox_load_messages_per_second{{{S}, window="1m"}}', "{{server}} {{side}} {{direction}}")],
    "mps", fill=0, desc="Load values reported by smppbox itself (1-minute window)"), 12, 12, 8)
newline(8)
place(ts("Queues", [tgt(f'smppbox_queued_messages{{{S}}}',
                        "{{server}} {{side}} {{direction}}"),
                    tgt(f'smppbox_store_size_messages{{{S}}}', "{{server}} store", "B")], "short", fill=5),
      0, 12, 7)
place(ts("Messages per interval (bars)", [
    tgt(f'sum by (server) (increase(smppbox_messages_total{{{S}, side="esme", direction="received"}}[$__interval]))',
        "{{server}}")], "short", stack=True, draw="bars", fill=80,
    legend_calcs=("sum", "max")), 12, 12, 7)
newline(7)

# =========================================================== SERVERS
row("Servers")
srv_rename = {"server": "Server", "hostname": "Hostname", "host_ip": "Host IP", "version": "Version",
              "resp_mode": "Resp mode", "os_release": "Kernel", "Value #A": "Status", "Value #B": "Uptime",
              "Value #C": "CPU", "Value #D": "Memory", "Value #E": "Logins", "Value #F": "Online",
              "Value #G": "Sessions", "Value #H": "Submit/s", "Value #I": "Store", "Value #J": "Bearerbox",
              "Value #K": "Scrape"}
srv_order = ["Server", "Status", "Bearerbox", "Hostname", "Host IP", "Version", "Resp mode", "Uptime", "CPU",
             "Memory", "Logins", "Online", "Sessions", "Submit/s", "Store", "Scrape", "Kernel"]
place(table("Server health", [
    tgt(f'smppbox_up{{{S}}}', ref="A", instant=True, fmt="table"),
    tgt(f'smppbox_uptime_seconds{{{S}}}', ref="B", instant=True, fmt="table"),
    tgt(f'100 * rate(smppbox_cpu_seconds_total{{{S}}}[5m])', ref="C", instant=True, fmt="table"),
    tgt(f'smppbox_memory_bytes{{{S}}}', ref="D", instant=True, fmt="table"),
    tgt(f'smppbox_logins_configured{{{S}}}', ref="E", instant=True, fmt="table"),
    tgt(f'smppbox_logins_online{{{S}}}', ref="F", instant=True, fmt="table"),
    tgt(f'smppbox_sessions_active{{{S}}}', ref="G", instant=True, fmt="table"),
    tgt(f'sum by (server) (rate(smppbox_messages_total{{{S}, side="esme", direction="received"}}[5m]))',
        ref="H", instant=True, fmt="table"),
    tgt(f'smppbox_store_size_messages{{{S}}}', ref="I", instant=True, fmt="table"),
    tgt(f'smppbox_bearerbox_connected{{{S}}}', ref="J", instant=True, fmt="table"),
    tgt(f'smppbox_scrape_duration_seconds{{{S}}}', ref="K", instant=True, fmt="table"),
    tgt(f'smppbox_gateway_info{{{S}}}', ref="L", instant=True, fmt="table")],
    srv_rename, srv_order,
    [ov("Status", [UPDOWN, cell("color-background")]),
     ov("Bearerbox", [{"id": "mappings", "value": [{"type": "value", "options": {
         "1": {"text": "connected", "color": "green"}, "0": {"text": "DISCONNECTED", "color": "red"}}}]},
                      cell("color-text")]),
     ov("Uptime", [unit("s")]), ov("CPU", [unit("percent"), {"id": "decimals", "value": 1}]),
     ov("Memory", [unit("bytes")]), ov("Submit/s", [unit("mps"), {"id": "decimals", "value": 2},
                                                    cell("gauge", {"mode": "lcd"})]),
     ov("Scrape", [unit("s")])],
    hide_extra=("__name__", "Value #L", "build", "mysql_client", "product", "state", "job", "instance")), 0, 24, 7)
newline(7)
place(ts("CPU usage (% of one core)", [tgt(f'100 * rate(smppbox_cpu_seconds_total{{{S}}}[{RI}])', "{{server}}")],
         "percent", fill=5), 0, 8, 7)
place(ts("Memory", [tgt(f'smppbox_memory_bytes{{{S}}}', "{{server}}")], "bytes", fill=5), 8, 8, 7)
place(ts("Active sessions per server", [tgt(f'smppbox_sessions_active{{{S}}}', "{{server}}")], "short",
         stack=True), 16, 8, 7)
newline(7)

# =========================================================== CUSTOMERS
row("Customers (ESME)  -  $esme")
cu_rename = {"server": "Server", "esme": "Customer (ESME)", "smsc_id": "SMSC-ID", "Value #A": "Status",
             "Value #B": "Sessions", "Value #C": "Max sessions", "Value #D": "Submit/s", "Value #E": "Deliver/s",
             "Value #F": "Submitted (range)", "Value #G": "Delivered (range)", "Value #H": "Failed (range)",
             "Value #I": "Fail %", "Value #J": "Open acks", "Value #K": "IPs", "Value #L": "Last reconnect",
             "Value #M": "State for", "Value #N": "Login"}
cu_order = ["Customer (ESME)", "Server", "SMSC-ID", "Status", "State for", "Login", "Sessions", "Max sessions", "IPs", "Submit/s",
            "Deliver/s", "Submitted (range)", "Delivered (range)", "Failed (range)", "Fail %", "Open acks",
            "Last reconnect"]
by = "sum by (server, esme, smsc_id)"
place(table("Customer overview", [
    tgt(f'smppbox_esme_connected{{{C}}}', ref="A", instant=True, fmt="table"),
    tgt(f'time() - smppbox_esme_state_since_timestamp_seconds{{{C}}}', ref="M", instant=True, fmt="table"),
    tgt(f'smppbox_login_online{{{C}}}', ref="N", instant=True, fmt="table"),
    tgt(f'{by} (smppbox_esme_active_sessions{{{C}}})', ref="B", instant=True, fmt="table"),
    tgt(f'{by} (smppbox_login_sessions_max{{{C}}})', ref="C", instant=True, fmt="table"),
    tgt(f'{by} (rate(smppbox_esme_messages_received_total{{{C}}}[5m]))', ref="D", instant=True, fmt="table"),
    tgt(f'{by} (rate(smppbox_esme_messages_sent_total{{{C}}}[5m]))', ref="E", instant=True, fmt="table"),
    tgt(f'{by} (increase(smppbox_esme_messages_received_total{{{C}}}[$__range]))', ref="F", instant=True, fmt="table"),
    tgt(f'{by} (increase(smppbox_esme_messages_sent_total{{{C}}}[$__range]))', ref="G", instant=True, fmt="table"),
    tgt(f'{by} (increase(smppbox_esme_messages_failed_total{{{C}}}[$__range]))', ref="H", instant=True, fmt="table"),
    tgt(f'100 * {by} (increase(smppbox_esme_messages_failed_total{{{C}}}[$__range])) / clamp_min({by} '
        f'(increase(smppbox_esme_messages_received_total{{{C}}}[$__range])), 1)', ref="I", instant=True, fmt="table"),
    tgt(f'{by} (smppbox_esme_open_acks{{{C}}})', ref="J", instant=True, fmt="table"),
    tgt(f'{by} (smppbox_esme_connected_ips{{{C}}})', ref="K", instant=True, fmt="table"),
    tgt(f'{by} (smppbox_esme_session_uptime_min_seconds{{{C}}})', ref="L", instant=True, fmt="table")],
    cu_rename, cu_order,
    [ov("Status", [CONN, cell("color-background")]), ov("Login", [ONOFF, cell("color-text")]),
     ov("State for", [unit("s")]),
     ov("Submit/s", [unit("mps"), {"id": "decimals", "value": 2}, cell("gauge", {"mode": "basic"}),
                     {"id": "color", "value": {"mode": "continuous-BlPu"}}]),
     ov("Deliver/s", [unit("mps"), {"id": "decimals", "value": 2}]),
     ov("Submitted (range)", [unit("short"), {"id": "decimals", "value": 0}]),
     ov("Delivered (range)", [unit("short"), {"id": "decimals", "value": 0}]),
     ov("Failed (range)", [unit("short"), {"id": "decimals", "value": 0}]),
     ov("Fail %", [unit("percent"), {"id": "decimals", "value": 2}, cell("color-text"),
                   {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                       {"color": "green", "value": None}, {"color": "orange", "value": 2},
                       {"color": "red", "value": 5}]}}]),
     ov("Last reconnect", [unit("s")]),
     ov("Open acks", [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [
         {"color": "green", "value": None}, {"color": "orange", "value": 20}, {"color": "red", "value": 200}]}}])],
    desc="All configured logins on the selected servers. Last reconnect = age of the newest session.",
    sort=[{"displayName": "Submitted (range)", "desc": True}]), 0, 24, 10)
newline(10)
place(bargauge("Top 10 customers by volume (range)",
               f'topk(10, sum by (esme) (increase(smppbox_esme_messages_received_total{{{C}}}[$__range])))',
               "{{esme}}"), 0, 8, 9)
place(bargauge("Top 10 customers by failed (range)",
               f'topk(10, sum by (esme) (increase(smppbox_esme_messages_failed_total{{{C}}}[$__range])) > 0)',
               "{{esme}}", color_mode="continuous-YlRd"), 8, 8, 9)
place(bargauge("Top 10 failure % (range, >100 msgs)",
               f'topk(10, 100 * sum by (esme) (increase(smppbox_esme_messages_failed_total{{{C}}}[$__range])) / '
               f'(sum by (esme) (increase(smppbox_esme_messages_received_total{{{C}}}[$__range])) > 100))',
               "{{esme}}", "percent", color_mode="continuous-YlRd"), 16, 8, 9)
newline(9)
place(ts("Submit rate per customer", [
    tgt(f'sum by (server, esme) (rate(smppbox_esme_messages_received_total{{{C}}}[{RI}])) > 0',
        "{{esme}} @ {{server}}")], "mps", stack=True), 0, 12, 9)
place(ts("Deliver (DLR/MO) rate per customer", [
    tgt(f'sum by (server, esme) (rate(smppbox_esme_messages_sent_total{{{C}}}[{RI}])) > 0',
        "{{esme}} @ {{server}}")], "mps", stack=True), 12, 12, 9)
newline(9)
place(ts("Failed rate per customer", [
    tgt(f'sum by (server, esme) (rate(smppbox_esme_messages_failed_total{{{C}}}[{RI}])) > 0',
        "{{esme}} @ {{server}}")], "mps"), 0, 12, 8)
place(ts("Failure % per customer", [
    tgt(f'100 * sum by (server, esme) (rate(smppbox_esme_messages_failed_total{{{C}}}[{RI}])) / '
        f'(sum by (server, esme) (rate(smppbox_esme_messages_received_total{{{C}}}[{RI}])) > 0)',
        "{{esme}} @ {{server}}")], "percent", fill=0), 12, 12, 8)
newline(8)
place({"type": "state-timeline", "title": "Customer connection state (history)",
       "targets": [tgt(f'smppbox_esme_connected{{{C}}}', "{{esme}} @ {{server}}")],
       "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": CONN["value"],
                                    "thresholds": {"mode": "absolute", "steps": [
                                        {"color": "red", "value": None}, {"color": "green", "value": 1}]},
                                    "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
       "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8,
                   "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}}, 0, 12, 9)
place(ts("Active sessions per customer", [
    tgt(f'sum by (server, esme) (smppbox_esme_active_sessions{{{C}}})', "{{esme}} @ {{server}}")],
    "short", stack=True, legend_calcs=("min", "max", "lastNotNull")), 12, 12, 9)
newline(9)
place(ts("Open acks (in-flight) per customer", [
    tgt(f'sum by (server, esme) (smppbox_esme_open_acks{{{C}}})', "{{esme}} @ {{server}}")], "short", fill=0),
      0, 12, 8)
place(ts("Session utilisation % (bound / allowed)", [
    tgt(f'100 * sum by (server, esme) (smppbox_login_sessions{{{C}}}) / '
        f'clamp_min(sum by (server, esme) (smppbox_login_sessions_max{{{C}}}) / 3, 1)', "{{esme}} @ {{server}}")],
    "percent", fill=0, desc="Bound sessions vs per-bind-type max (max summed over trans/recv/trcv /3)"), 12, 12, 8)
newline(8)

# =========================================================== BIND TYPES
row("Customer connections by bind type (Transceiver / Transmitter / Receiver)  -  $bind_type")
CT = C + ', type=~"$bind_type"'
byt = "sum by (server, esme, smsc_id, type)"
TYPEMAP = {"id": "mappings", "value": [{"type": "value", "options": {
    "trcv": {"text": "Transceiver (trcv)", "color": "blue", "index": 0},
    "trans": {"text": "Transmitter (trans)", "color": "purple", "index": 1},
    "recv": {"text": "Receiver (recv)", "color": "orange", "index": 2}}}]}
place(stat("Transceiver sessions", f'sum(smppbox_esme_active_sessions{{{C}, type="trcv"}})', color="blue"), 0, 4, 4)
place(stat("Transmitter sessions", f'sum(smppbox_esme_active_sessions{{{C}, type="trans"}})', color="purple"), 4, 4, 4)
place(stat("Receiver sessions", f'sum(smppbox_esme_active_sessions{{{C}, type="recv"}})', color="orange"), 8, 4, 4)
place(stat("Binds (range)", f'sum(increase(smppbox_esme_type_connects_total{{{CT}}}[$__range]))', color="teal",
           spark=False), 12, 4, 4)
place(stat("Unbinds / drops (range)", f'sum(increase(smppbox_esme_type_disconnects_total{{{CT}}}[$__range]))',
           spark=False, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 5},
                                    {"color": "red", "value": 50}]), 16, 4, 4)
place(stat("Open acks (selected types)", f'sum(smppbox_esme_type_open_acks{{{CT}}})',
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 50},
                       {"color": "red", "value": 500}]), 20, 4, 4)
newline(4)
bt_rename = {"server": "Server", "esme": "Customer (ESME)", "smsc_id": "SMSC-ID", "type": "Bind type",
             "Value #A": "Sessions", "Value #B": "Max allowed", "Value #C": "Submit/s", "Value #D": "Deliver/s",
             "Value #E": "Submitted (range)", "Value #F": "Delivered (range)", "Value #G": "Failed (range)",
             "Value #H": "Fail %", "Value #I": "Open acks", "Value #J": "Binds (range)",
             "Value #K": "Drops (range)", "Value #L": "Oldest session", "Value #M": "Newest session"}
bt_order = ["Customer (ESME)", "Bind type", "Server", "SMSC-ID", "Sessions", "Max allowed", "Submit/s",
            "Deliver/s", "Submitted (range)", "Delivered (range)", "Failed (range)", "Fail %", "Open acks",
            "Binds (range)", "Drops (range)", "Oldest session", "Newest session"]
place(table("Customer stats per bind type", [
    tgt(f'{byt} (smppbox_esme_active_sessions{{{CT}}})', ref="A", instant=True, fmt="table"),
    tgt(f'{byt} (smppbox_login_sessions_max{{{CT}}})', ref="B", instant=True, fmt="table"),
    tgt(f'{byt} (rate(smppbox_esme_type_messages_received_total{{{CT}}}[5m]))', ref="C", instant=True, fmt="table"),
    tgt(f'{byt} (rate(smppbox_esme_type_messages_sent_total{{{CT}}}[5m]))', ref="D", instant=True, fmt="table"),
    tgt(f'{byt} (increase(smppbox_esme_type_messages_received_total{{{CT}}}[$__range]))', ref="E", instant=True, fmt="table"),
    tgt(f'{byt} (increase(smppbox_esme_type_messages_sent_total{{{CT}}}[$__range]))', ref="F", instant=True, fmt="table"),
    tgt(f'{byt} (increase(smppbox_esme_type_messages_failed_total{{{CT}}}[$__range]))', ref="G", instant=True, fmt="table"),
    tgt(f'100 * {byt} (increase(smppbox_esme_type_messages_failed_total{{{CT}}}[$__range])) / clamp_min({byt} '
        f'(increase(smppbox_esme_type_messages_received_total{{{CT}}}[$__range])), 1)', ref="H", instant=True, fmt="table"),
    tgt(f'{byt} (smppbox_esme_type_open_acks{{{CT}}})', ref="I", instant=True, fmt="table"),
    tgt(f'{byt} (increase(smppbox_esme_type_connects_total{{{CT}}}[$__range]))', ref="J", instant=True, fmt="table"),
    tgt(f'{byt} (increase(smppbox_esme_type_disconnects_total{{{CT}}}[$__range]))', ref="K", instant=True, fmt="table"),
    tgt(f'{byt} (smppbox_esme_type_session_uptime_max_seconds{{{CT}}})', ref="L", instant=True, fmt="table"),
    tgt(f'{byt} (smppbox_esme_type_session_uptime_min_seconds{{{CT}}})', ref="M", instant=True, fmt="table")],
    bt_rename, bt_order,
    [ov("Bind type", [TYPEMAP, cell("color-text")]),
     ov("Sessions", [cell("color-background"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [
         {"color": "transparent", "value": None}, {"color": "green", "value": 1}]}}]),
     ov("Submit/s", [unit("mps"), {"id": "decimals", "value": 2}]),
     ov("Deliver/s", [unit("mps"), {"id": "decimals", "value": 2}]),
     ov("Submitted (range)", [{"id": "decimals", "value": 0}]), ov("Delivered (range)", [{"id": "decimals", "value": 0}]),
     ov("Failed (range)", [{"id": "decimals", "value": 0}]),
     ov("Binds (range)", [{"id": "decimals", "value": 0}]),
     ov("Drops (range)", [{"id": "decimals", "value": 0}, cell("color-text"), {"id": "thresholds", "value": {
         "mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 3},
                                       {"color": "red", "value": 20}]}}]),
     ov("Fail %", [unit("percent"), {"id": "decimals", "value": 2}, cell("color-text"),
                   {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                       {"color": "green", "value": None}, {"color": "orange", "value": 2},
                       {"color": "red", "value": 5}]}}]),
     ov("Oldest session", [unit("s")]), ov("Newest session", [unit("s")])],
    sort=[{"displayName": "Submitted (range)", "desc": True}]), 0, 24, 10)
newline(10)
place(ts("Submit rate by bind type", [
    tgt(f'sum by (type) (rate(smppbox_esme_type_messages_received_total{{{CT}}}[{RI}]))', "{{type}}")],
    "mps", stack=True), 0, 8, 8)
place(ts("Deliver (DLR/MO) rate by bind type", [
    tgt(f'sum by (type) (rate(smppbox_esme_type_messages_sent_total{{{CT}}}[{RI}]))', "{{type}}")],
    "mps", stack=True), 8, 8, 8)
place(ts("Active sessions by bind type", [
    tgt(f'sum by (type) (smppbox_esme_active_sessions{{{CT}}})', "{{type}}")], "short", stack=True,
    legend_calcs=("min", "max", "lastNotNull")), 16, 8, 8)
newline(8)
place(ts("Binds & drops per customer", [
    tgt(f'sum by (esme, type) (increase(smppbox_esme_type_connects_total{{{CT}}}[$__interval])) > 0',
        "bind  {{esme}} {{type}}", "A"),
    tgt(f'-1 * (sum by (esme, type) (increase(smppbox_esme_type_disconnects_total{{{CT}}}[$__interval])) > 0)',
        "drop  {{esme}} {{type}}", "B")], "short", draw="bars", fill=80, legend_calcs=("sum",)), 0, 12, 8)
place(ts("Submit rate per customer & bind type", [
    tgt(f'sum by (esme, type) (rate(smppbox_esme_type_messages_received_total{{{CT}}}[{RI}])) > 0',
        "{{esme}} [{{type}}]")], "mps"), 12, 12, 8)
newline(8)

# =========================================================== CONNECTIONS
row("Customer connections (source IPs)", collapsed=False)
CI = C
place(table("Connections by source IP", [
    tgt(f'smppbox_esme_ip_sessions{{{CI}}}', ref="A", instant=True, fmt="table"),
    tgt(f'rate(smppbox_esme_ip_messages_received_total{{{CI}}}[5m])', ref="B", instant=True, fmt="table"),
    tgt(f'rate(smppbox_esme_ip_messages_sent_total{{{CI}}}[5m])', ref="C", instant=True, fmt="table"),
    tgt(f'increase(smppbox_esme_ip_messages_received_total{{{CI}}}[$__range])', ref="D", instant=True, fmt="table"),
    tgt(f'increase(smppbox_esme_ip_messages_failed_total{{{CI}}}[$__range])', ref="E", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer", "smsc_id": "SMSC-ID", "ip": "Source IP", "Value #A": "Sessions",
     "Value #B": "Submit/s", "Value #C": "Deliver/s", "Value #D": "Submitted (range)", "Value #E": "Failed (range)"},
    ["Customer", "Source IP", "Server", "SMSC-ID", "Sessions", "Submit/s", "Deliver/s", "Submitted (range)",
     "Failed (range)"],
    [ov("Submit/s", [unit("mps"), {"id": "decimals", "value": 2}]),
     ov("Deliver/s", [unit("mps"), {"id": "decimals", "value": 2}]),
     ov("Submitted (range)", [{"id": "decimals", "value": 0}]), ov("Failed (range)", [{"id": "decimals", "value": 0}]),
     ov("Sessions", [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [
         {"color": "red", "value": None}, {"color": "green", "value": 1}]}}])],
    sort=[{"displayName": "Submit/s", "desc": True}]), 0, 14, 9)
place(ts("Submit rate per source IP", [
    tgt(f'sum by (esme, ip) (rate(smppbox_esme_ip_messages_received_total{{{CI}}}[{RI}])) > 0', "{{esme}} {{ip}}")],
    "mps", stack=True), 14, 10, 9)
newline(9)

# =========================================================== PLUGINS
row("Plugins & database", collapsed=True)
plug = []
pY = Y[0]


def pplace(p, x, w, h, y):
    p["gridPos"] = {"h": h, "w": w, "x": x, "y": y}
    p["id"] = nid()
    p["datasource"] = DS
    plug.append(p)


pplace(table("Plugin chains", [tgt(f'smppbox_plugin_info{{{S}}}', ref="A", instant=True, fmt="table")],
             {"server": "Server", "chain": "Trigger chain", "position": "#", "plugin": "Plugin", "state": "State",
              "async": "Async", "args": "Arguments"},
             ["Server", "Trigger chain", "#", "Plugin", "State", "Async", "Arguments"],
             [ov("State", [cell("color-text"), {"id": "mappings", "value": [{"type": "value", "options": {
                 "active": {"color": "green"}}}, {"type": "regex", "options": {"pattern": "^(?!active).*",
                                                                               "result": {"color": "red"}}}]}]),
              ov("Arguments", [{"id": "custom.width", "value": 700}])],
             hide_extra=("__name__", "Value", "job", "instance")), 0, 24, 10, pY)
pplace(ts("DB pool utilisation % (CDR / prepaid)", [
    tgt(f'100 * (1 - smppbox_plugin_db_connections_idle{{{S}}} / clamp_min(smppbox_plugin_db_connections_max{{{S}}}, 1))',
        "{{server}} {{chain}} {{plugin}}")], "percent", fill=0), 0, 12, 8, pY + 10)
pplace(ts("SQL statements in queue", [tgt(f'smppbox_plugin_sql_queue{{{S}}}', "{{server}} {{chain}} {{plugin}}")],
          "short", fill=0), 12, 12, 8, pY + 10)
pplace(stat("Inactive plugins", f'count(smppbox_plugin_active{{{S}}} == 0) or vector(0)', spark=False,
            thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]), 0, 6, 4, pY + 18)
pplace(stat("Plugins loaded", f'count(smppbox_plugin_active{{{S}}})', spark=False), 6, 6, 4, pY + 18)
panels[-1]["panels"] = plug
Y[0] += 1

# =========================================================== EXPORTER
row("Exporter health", collapsed=True)
exp = []
eY = Y[0]
for p, x, w, h in (
        (ts("Scrape duration", [tgt(f'smppbox_scrape_duration_seconds{{{S}}}', "{{server}}")], "s", fill=0), 0, 8, 7),
        (ts("Scrape errors / min", [tgt(f'60 * rate(smppbox_scrape_errors_total{{{S}}}[{RI}])', "{{server}}")],
            "short", fill=0), 8, 8, 7),
        (ts("Seconds since last good scrape", [
            tgt(f'time() - smppbox_last_scrape_success_timestamp_seconds{{{S}}} and '
                f'smppbox_last_scrape_success_timestamp_seconds{{{S}}} > 0', "{{server}}")], "s", fill=0), 16, 8, 7)):
    p["gridPos"] = {"h": h, "w": w, "x": x, "y": eY}
    p["id"] = nid()
    p["datasource"] = DS
    exp.append(p)
panels[-1]["panels"] = exp


def qvar(name, label, query, multi=True, hide=0):
    return {"name": name, "label": label, "type": "query", "datasource": DS,
            "definition": query, "query": {"query": query, "refId": name, "qryType": 1},
            "refresh": 2, "multi": multi, "includeAll": True, "allValue": ".*",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "sort": 7, "hide": hide, "regex": "", "options": []}


dash = {
    "__inputs": [], "annotations": {"list": [
        {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
         "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"},
        {"datasource": DS, "enable": True, "iconColor": "red", "name": "smppbox restarts",
         "expr": f'changes(smppbox_uptime_seconds{{{S}}}[2m]) > 0 and smppbox_uptime_seconds{{{S}}} < 300',
         "titleFormat": "smppbox restarted", "textFormat": "{{server}}", "step": "60s"},
        {"datasource": DS, "enable": True, "iconColor": "orange", "name": "Server down",
         "expr": f'smppbox_up{{{S}}} == 0', "titleFormat": "Status page unreachable", "textFormat": "{{server}}",
         "step": "60s"}]},
    "description": "Kannel smppbox - all servers, per server and per customer (ESME)",
    "editable": True, "graphTooltip": 1, "links": [], "liveNow": False,
    "panels": panels, "refresh": "30s", "schemaVersion": 39, "tags": ["smpp", "kannel", "smppbox", "sms"],
    "templating": {"list": [
        {"name": "datasource", "label": "Data source", "type": "datasource", "query": "prometheus",
         "current": {}, "hide": 0, "refresh": 1, "regex": "", "options": []},
        qvar("server", "SMPP server", "label_values(smppbox_up, server)"),
        qvar("smsc_id", "SMSC-ID / route", 'label_values(smppbox_login_info{server=~"$server"}, smsc_id)'),
        {"name": "bind_type", "label": "Bind type", "type": "custom", "multi": True, "includeAll": True,
         "allValue": ".*", "query": "Transceiver : trcv,Transmitter : trans,Receiver : recv",
         "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "hide": 0, "options": [],
         "description": "trcv = transceiver (send+receive on one bind), trans = transmitter (send only), recv = receiver (DLR/MO only)"},
        qvar("esme", "Customer (ESME)",
             'label_values(smppbox_login_info{server=~"$server", smsc_id=~"$smsc_id"}, esme)')]},
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m", "15m", "1h"]},
    "timezone": "browser", "title": "Kannel smppbox - SMPP Monitoring", "uid": "kannel-smppbox", "version": 1,
    "weekStart": ""}


# =========================================================== table row-merge fix
# Grafana merges table rows only when label sets are identical. Raw series carry job/instance (and other
# labels), aggregated ones do not -> one row per query. Force the same key labels on every table query.
INFO = "hostname, host_ip, version, resp_mode, os_release"
TABLE_KEYS = {"Peak throughput per server": "server",
              "Peak throughput per server & customer": "server, esme, smsc_id",
              "Peak throughput per server, customer & session": "server, esme, smsc_id, ip, port, type",
              "Customer overview": "server, esme, smsc_id",
              "Customer stats per bind type": "server, esme, smsc_id, type",
              "Connections by source IP": "server, esme, smsc_id, ip",
              "Gateway / Build Information": "server, product, version, build, hostname, host_ip, os_release, mysql_client, state, resp_mode",
              "Plugin chains": "server, chain, position, plugin, state, async, args"}
CUR = "smppbox_esme_active_sessions{%s}" % C
LIVE = {"Customer overview": ("server, esme, smsc_id", CUR),
        "Customer stats per bind type": ("server, esme, smsc_id, type", CUR),
        "Peak throughput per server & customer": ("server, esme, smsc_id", CUR),
        "Peak throughput per server": ("server", "smppbox_up{%s} == 1" % S),
        "Connections by source IP": ("server, esme, smsc_id, ip", "smppbox_esme_ip_sessions{%s}" % C),
        "Peak throughput per server, customer & session": ("server, esme, smsc_id, ip, port, type",
                                                            "smppbox_session_online_seconds{%s}" % C)}
for p in panels:
    if p.get("type") != "table":
        continue
    if p["title"] == "Server health":
        for t in p["targets"]:
            if t["refId"] == "L":
                t["expr"] = "max by (server, %s) (%s)" % (INFO, t["expr"])
            else:
                t["expr"] = ("max by (server) (%s) * on (server) group_left (%s) max by (server, %s) (smppbox_gateway_info{%s})"
                             % (t["expr"], INFO, INFO, S))
    elif p["title"] in TABLE_KEYS:
        live = LIVE.get(p["title"])
        for t in p["targets"]:
            e = t["expr"]
            if live:   # only customers the exporter reports right now (drops old rows of removed / unreachable servers)
                e = "(%s) and on (%s) group by (%s) (%s)" % (e, live[0], live[0], live[1])
            t["expr"] = "max by (%s) (%s)" % (TABLE_KEYS[p["title"]], e)
    else:
        continue
    ex = p["transformations"][1]["options"]["excludeByName"]
    ex.update({"__name__": True, "job": True, "instance": True})

exec(open(os.path.join(HERE, "smppbox_desc.py")).read())
json.dump(dash, open(os.path.join(HERE, "..", "dashboards", "smppbox_dashboard.json"), "w", newline="\n"), indent=2)
print("panels:", _id[0])
