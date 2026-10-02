#!/usr/bin/env python3
"""Generates kannel_dashboard.json (Grafana).  Import via Dashboards > New > Import."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "_helpers.py")).read())

S = 'server=~"$server"'
L = 'server=~"$server", smsc_id=~"$smsc_id", admin_id=~"$admin_id"'
BXF = 'server=~"$server", box_id=~"$box"'
RI = "$__rate_interval"
PK = "[$__range:15s]"

MT = f'kannel_smsc_sms_total{{{L}, direction="sent"}}'
MO = f'kannel_smsc_sms_total{{{L}, direction="received"}}'
DLR = f'kannel_smsc_dlr_total{{{L}, direction="received"}}'
FAIL = f'kannel_smsc_failed_total{{{L}}}'


def r(sel, by="", win=RI, fn="rate"):
    b = "sum by (%s) " % by if by else "sum "
    return "%s(%s(%s[%s]))" % (b, fn, sel, win)


STATEMAP = {"id": "mappings", "value": [{"type": "value", "options": {
    "4": {"text": "ONLINE", "color": "green", "index": 0}, "3": {"text": "RE-CONNECTING", "color": "orange", "index": 1},
    "2": {"text": "CONNECTING", "color": "yellow", "index": 2}, "1": {"text": "DISCONNECTED", "color": "red", "index": 3},
    "0": {"text": "DEAD", "color": "dark-red", "index": 4}}}]}
MPS1 = [unit("mps"), {"id": "decimals", "value": 1}]
MPS2 = [unit("mps"), {"id": "decimals", "value": 2}]
INT = [{"id": "decimals", "value": 0}]
GAUGE = cell("gauge", {"mode": "gradient"})
PURPLE = {"id": "color", "value": {"mode": "continuous-BlPu"}}
PCT = lambda warn, crit: [unit("percent"), {"id": "decimals", "value": 2}, cell("color-text"), {"id": "thresholds", "value": {
    "mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": warn}, {"color": "red", "value": crit}]}}]
G = [{"color": "green", "value": None}]
RED1 = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
TH = lambda w, c: [{"color": "green", "value": None}, {"color": "orange", "value": w}, {"color": "red", "value": c}]

# =========================================================== 1. GATEWAYS & PEAKS
row("Kannel gateways & peak throughput  -  $server")
place(table("Gateway / build information", [tgt(f'kannel_gateway_info{{{S}}}', ref="A", instant=True, fmt="table"),
                                             tgt(f'kannel_uptime_seconds{{{S}}}', ref="B", instant=True, fmt="table")],
            {"server": "Server", "product": "Product", "flavour": "Flavour", "build_type": "Build", "version": "Version",
             "build": "Build date", "hostname": "Hostname", "host_ip": "IP", "os_release": "OS / Kernel",
             "dlr_storage": "DLR storage", "Value #B": "Uptime"},
            ["Server", "Product", "Version", "Build", "Build date", "Hostname", "IP", "Uptime", "DLR storage", "OS / Kernel"],
            [ov("Uptime", [unit("s")]), ov("Build", [{"id": "mappings", "value": [{"type": "value", "options": {
                "svn": {"text": "SVN build", "color": "blue"}, "release": {"text": "Release (apt)", "color": "purple"}}}]},
                                                        cell("color-text")])],
            hide_extra=("Value #A", "flavour")), 0, 24, 6)
newline(6)
by_s = "sum by (server)"
place(table("Gateway health", [
    tgt(f'kannel_up{{{S}}}', ref="A", instant=True, fmt="table"),
    tgt(f'{by_s} (kannel_gateway_state{{{S}, state="running"}})', ref="B", instant=True, fmt="table"),
    tgt(f'kannel_smscs_online{{{S}}}', ref="C", instant=True, fmt="table"),
    tgt(f'kannel_smscs_configured{{{S}}}', ref="D", instant=True, fmt="table"),
    tgt(f'{by_s} (kannel_boxes_connected{{{S}}})', ref="E", instant=True, fmt="table"),
    tgt(f'{by_s} (rate(kannel_sms_total{{{S}, direction="sent"}}[5m]))', ref="F", instant=True, fmt="table"),
    tgt(f'{by_s} (rate(kannel_dlr_total{{{S}, direction="received"}}[5m]))', ref="G", instant=True, fmt="table"),
    tgt(f'{by_s} (rate(kannel_sms_total{{{S}, direction="received"}}[5m]))', ref="H", instant=True, fmt="table"),
    tgt(f'{by_s} (kannel_sms_queued{{{S}}})', ref="I", instant=True, fmt="table"),
    tgt(f'kannel_dlr_queued{{{S}}}', ref="J", instant=True, fmt="table"),
    tgt(f'kannel_sms_store_size{{{S}}}', ref="K", instant=True, fmt="table"),
    tgt(f'{by_s} (kannel_smsc_queued{{{S}}})', ref="L", instant=True, fmt="table"),
    tgt(f'kannel_scrape_duration_seconds{{{S}}}', ref="M", instant=True, fmt="table")],
    {"server": "Server", "Value #A": "Status", "Value #B": "Running", "Value #C": "SMSCs online",
     "Value #D": "SMSCs total", "Value #E": "Boxes", "Value #F": "MT/s", "Value #G": "DLR/s", "Value #H": "MO/s",
     "Value #I": "BB queued", "Value #J": "DLR waiting", "Value #K": "Store", "Value #L": "SMSC queued",
     "Value #M": "Scrape"},
    ["Server", "Status", "Running", "SMSCs online", "SMSCs total", "Boxes", "MT/s", "DLR/s", "MO/s", "BB queued",
     "SMSC queued", "DLR waiting", "Store", "Scrape"],
    [ov("Status", [UPDOWN, cell("color-background")]),
     ov("Running", [{"id": "mappings", "value": [{"type": "value", "options": {
         "1": {"text": "running", "color": "green"}, "0": {"text": "NOT RUNNING", "color": "red"}}}]}, cell("color-text")]),
     ov("MT/s", MPS1 + [GAUGE, PURPLE]), ov("DLR/s", MPS1), ov("MO/s", MPS2), ov("Scrape", [unit("s")])]), 0, 24, 6)
newline(6)
place(stat("Peak MT (msg/s)", f'max_over_time({r(MT, win="1m")}{PK})', "mps", color="blue", spark=False, decimals=1), 0, 4, 4)
place(stat("Peak DLR in (msg/s)", f'max_over_time({r(DLR, win="1m")}{PK})', "mps", color="purple", spark=False, decimals=1), 4, 4, 4)
place(stat("Peak MO (msg/s)", f'max_over_time({r(MO, win="1m")}{PK})', "mps", color="teal", spark=False, decimals=1), 8, 4, 4)
place(stat("Current MT (msg/s)", r(MT, win="1m"), "mps", color="blue", decimals=1), 12, 4, 4)
place(stat("Current DLR in (msg/s)", r(DLR, win="1m"), "mps", color="purple", decimals=1), 16, 4, 4)
place(stat("Current MO (msg/s)", r(MO, win="1m"), "mps", color="teal", decimals=1), 20, 4, 4)
newline(4)
PKC = {"Value #A": "Peak MT", "Value #B": "Peak DLR in", "Value #C": "Peak MO", "Value #D": "Current MT",
       "Value #E": "Current DLR in", "Value #F": "Current MO"}
PKO = [ov("Peak MT", MPS1 + [GAUGE, PURPLE]), ov("Peak DLR in", MPS1 + [GAUGE, PURPLE]), ov("Peak MO", MPS1),
       ov("Current MT", MPS1), ov("Current DLR in", MPS1), ov("Current MO", MPS1)]


def peaks(by):
    return [tgt(f'max_over_time({r(MT, by, "1m")}{PK})', ref="A", instant=True, fmt="table"),
            tgt(f'max_over_time({r(DLR, by, "1m")}{PK})', ref="B", instant=True, fmt="table"),
            tgt(f'max_over_time({r(MO, by, "1m")}{PK})', ref="C", instant=True, fmt="table"),
            tgt(r(MT, by, "1m"), ref="D", instant=True, fmt="table"),
            tgt(r(DLR, by, "1m"), ref="E", instant=True, fmt="table"),
            tgt(r(MO, by, "1m"), ref="F", instant=True, fmt="table")]


PKN = ["Peak MT", "Peak DLR in", "Peak MO", "Current MT", "Current DLR in", "Current MO"]
place(table("Peak throughput per server", peaks("server"), dict(server="Server", **PKC), ["Server"] + PKN, PKO,
            sort=[{"displayName": "Peak MT", "desc": True}]), 0, 12, 8)
place(table("Peak throughput per SMSC (route)", peaks("server, smsc_id"),
            dict(server="Server", smsc_id="SMSC-ID", **PKC), ["SMSC-ID", "Server"] + PKN, PKO,
            sort=[{"displayName": "Peak MT", "desc": True}]), 12, 12, 8)
newline(8)
place(table("Peak throughput per SMSC link (admin-id)", peaks("server, smsc_id, admin_id"),
            dict(server="Server", smsc_id="SMSC-ID", admin_id="Link (admin-id)", **PKC),
            ["Link (admin-id)", "SMSC-ID", "Server"] + PKN, PKO, sort=[{"displayName": "Peak MT", "desc": True}]), 0, 24, 9)
newline(9)

# =========================================================== 2. OVERVIEW
row("Overview  -  $server  /  $smsc_id  /  $admin_id")
place(stat("Servers UP", f'sum(kannel_up{{{S}}})', thresholds=G, spark=False), 0, 3, 4)
place(stat("Servers DOWN", f'count(kannel_up{{{S}}} == 0) or vector(0)', spark=False, thresholds=RED1), 3, 3, 4)
place(stat("MT rate", r(MT), "mps", color="blue"), 6, 3, 4)
place(stat("DLR rate", r(DLR), "mps", color="purple"), 9, 3, 4)
place(stat("MO rate", r(MO), "mps", color="teal"), 12, 3, 4)
place(stat("Failed rate", r(FAIL), "mps", thresholds=TH(1, 10)), 15, 3, 4)
place(stat("Failure %", f'100 * {r(FAIL)} / clamp_min({r(MT)} + {r(FAIL)}, 0.0001)', "percent", decimals=2, thresholds=TH(2, 5)), 18, 3, 4)
place(stat("DLR ratio", f'100 * {r(DLR)} / clamp_min({r(MT)}, 0.0001)', "percent", decimals=1, color="purple"), 21, 3, 4)
newline(4)
place(stat("SMSC links online", f'sum(kannel_smsc_online{{{L}}})', thresholds=G, spark=False), 0, 3, 4)
place(stat("SMSC links NOT online", f'count(kannel_smsc_online{{{L}}} == 0) or vector(0)', spark=False, thresholds=TH(1, 3)), 3, 3, 4)
place(stat("MT sent (range)", f'sum(increase({MT}[$__range]))', color="blue", spark=False), 6, 3, 4)
place(stat("Failed (range)", f'sum(increase({FAIL}[$__range]))', color="orange", spark=False), 9, 3, 4)
place(stat("SMSC queued", f'sum(kannel_smsc_queued{{{L}}})', thresholds=TH(100, 1000)), 12, 3, 4)
place(stat("Bearerbox queued", f'sum(kannel_sms_queued{{{S}}})', thresholds=TH(100, 1000)), 15, 3, 4)
place(stat("DLRs waiting", f'sum(kannel_dlr_queued{{{S}}})', color="purple"), 18, 3, 4)
place(stat("Boxes connected", f'sum(kannel_boxes_connected{{{S}}})', thresholds=[{"color": "red", "value": None}, {"color": "green", "value": 1}], spark=False), 21, 3, 4)
newline(4)

# =========================================================== 3. TRAFFIC
row("Traffic")
place(ts("Messages by kind (SMSC links)", [
    tgt(r(MT), "MT sent", "A"), tgt(r(FAIL), "MT failed", "B"), tgt(r(DLR), "DLR received", "C"), tgt(r(MO), "MO received", "D")],
    "mps", overrides=[ov("MT failed", [{"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}])]), 0, 12, 8)
place(ts("MT per server (bearerbox)", [tgt(f'{by_s} (rate(kannel_sms_total{{{S}, direction="sent"}}[{RI}]))', "{{server}}")],
         "mps", stack=True), 12, 12, 8)
newline(8)
place(ts("DLR received per server (bearerbox)", [tgt(f'{by_s} (rate(kannel_dlr_total{{{S}, direction="received"}}[{RI}]))', "{{server}}")],
         "mps", stack=True), 0, 12, 8)
place(ts("MO received per server (bearerbox)", [tgt(f'{by_s} (rate(kannel_sms_total{{{S}, direction="received"}}[{RI}]))', "{{server}}")],
         "mps", stack=True), 12, 12, 8)
newline(8)
place(ts("Bearerbox reported load (1 min)", [tgt(f'kannel_load_messages_per_second{{{S}, window="1m"}}', "{{server}} {{type}} {{direction}}")],
         "mps", fill=0), 0, 12, 7)
place(ts("Queues & waiting DLRs", [tgt(f'{by_s} (kannel_sms_queued{{{S}}})', "{{server}} bearerbox queued", "A"),
                                   tgt(f'{by_s} (kannel_smsc_queued{{{S}}})', "{{server}} SMSC queued", "B"),
                                   tgt(f'kannel_dlr_queued{{{S}}}', "{{server}} DLR waiting", "C"),
                                   tgt(f'kannel_sms_store_size{{{S}}} >= 0', "{{server}} store", "D")], "short", fill=0), 12, 12, 7)
newline(7)

# =========================================================== 4. SMSC LINKS
row("SMSC / operator links  -  $smsc_id  /  $admin_id")
lk = "server, smsc_id, admin_id"
place(table("SMSC links", [
    tgt(f'kannel_smsc_state{{{L}}}', ref="A", instant=True, fmt="table"),
    tgt(f'time() - kannel_smsc_state_since_timestamp_seconds{{{L}}}', ref="B", instant=True, fmt="table"),
    tgt(r(MT, lk, "5m"), ref="C", instant=True, fmt="table"),
    tgt(r(DLR, lk, "5m"), ref="D", instant=True, fmt="table"),
    tgt(r(MO, lk, "5m"), ref="E", instant=True, fmt="table"),
    tgt(r(MT, lk, "$__range", "increase"), ref="F", instant=True, fmt="table"),
    tgt(r(FAIL, lk, "$__range", "increase"), ref="G", instant=True, fmt="table"),
    tgt(f'100 * {r(FAIL, lk, "$__range", "increase")} / clamp_min({r(MT, lk, "$__range", "increase")} + {r(FAIL, lk, "$__range", "increase")}, 1)', ref="H", instant=True, fmt="table"),
    tgt(f'100 * {r(DLR, lk, "$__range", "increase")} / clamp_min({r(MT, lk, "$__range", "increase")}, 1)', ref="I", instant=True, fmt="table"),
    tgt(f'kannel_smsc_queued{{{L}}}', ref="J", instant=True, fmt="table"),
    tgt(r(f'kannel_smsc_state_drops_total{{{L}}}', lk, "$__range", "increase"), ref="K", instant=True, fmt="table"),
    tgt(f'kannel_smsc_sms_total{{{L}, direction="sent"}}', ref="L", instant=True, fmt="table")],
    {"server": "Server", "smsc_id": "SMSC-ID", "admin_id": "Link (admin-id)", "username": "SMSC username",
     "host": "Operator host", "port": "Port", "Value #A": "Status", "Value #B": "State for",
     "Value #C": "MT/s", "Value #D": "DLR/s", "Value #E": "MO/s", "Value #F": "MT (range)", "Value #G": "Failed (range)",
     "Value #H": "Fail %", "Value #I": "DLR ratio %", "Value #J": "Queued", "Value #K": "Drops (range)",
     "Value #L": "MT since link start"},
    ["Link (admin-id)", "SMSC-ID", "SMSC username", "Operator host", "Port", "Server", "Status", "State for", "MT/s", "DLR/s", "MO/s", "MT (range)",
     "Failed (range)", "Fail %", "DLR ratio %", "Queued", "Drops (range)", "MT since link start"],
    [ov("Status", [STATEMAP, cell("color-background")]), ov("State for", [unit("s")]),
     ov("MT/s", MPS2 + [GAUGE, PURPLE]), ov("DLR/s", MPS2), ov("MO/s", MPS2), ov("MT (range)", INT),
     ov("Failed (range)", INT), ov("Fail %", PCT(2, 5)), ov("DLR ratio %", [unit("percent"), {"id": "decimals", "value": 1}]),
     ov("Drops (range)", INT + [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": TH(1, 5)}}]),
     ov("MT since link start", INT)],
    sort=[{"displayName": "MT/s", "desc": True}]), 0, 24, 11)
newline(11)
place(bargauge("Top 10 SMSC-IDs by MT (range)", f'topk(10, {r(MT, "server, smsc_id", "$__range", "increase")})',
               "{{smsc_id}} @ {{server}}"), 0, 8, 9)
place(bargauge("Top 10 SMSC-IDs by failed (range)", f'topk(10, {r(FAIL, "server, smsc_id", "$__range", "increase")} > 0)',
               "{{smsc_id}} @ {{server}}", color_mode="continuous-YlRd"), 8, 8, 9)
place(bargauge("Top 10 failure % (range, >100 MT)",
               f'topk(10, 100 * {r(FAIL, "server, smsc_id", "$__range", "increase")} / ({r(MT, "server, smsc_id", "$__range", "increase")} > 100))',
               "{{smsc_id}} @ {{server}}", "percent", color_mode="continuous-YlRd"), 16, 8, 9)
newline(9)
place(ts("MT per SMSC-ID", [tgt(f'{r(MT, "server, smsc_id")} > 0', "{{smsc_id}} @ {{server}}")], "mps", stack=True), 0, 12, 9)
place(ts("DLR received per SMSC-ID", [tgt(f'{r(DLR, "server, smsc_id")} > 0', "{{smsc_id}} @ {{server}}")], "mps", stack=True), 12, 12, 9)
newline(9)
place(ts("MT failed per SMSC-ID", [tgt(f'{r(FAIL, "server, smsc_id")} > 0', "{{smsc_id}} @ {{server}}")], "mps"), 0, 12, 8)
place(ts("MO received per SMSC-ID", [tgt(f'{r(MO, "server, smsc_id")} > 0', "{{smsc_id}} @ {{server}}")], "mps", stack=True), 12, 12, 8)
newline(8)
LS = f'kannel_smsc_state{{{L}}}'
place(stat("Links ONLINE", f'count({LS} == 4) or vector(0)', thresholds=G, spark=False), 0, 4, 4)
place(stat("Links CONNECTING / RE-CONNECTING", f'count({LS} == 2 or {LS} == 3) or vector(0)', spark=False,
           thresholds=TH(1, 5)), 4, 4, 4)
place(stat("Links DISCONNECTED / DEAD", f'count({LS} <= 1) or vector(0)', spark=False, thresholds=TH(1, 3)), 8, 4, 4)
RAV = f'100 * sum by (server, smsc_id) (kannel_smsc_online{{{L}}}) / count by (server, smsc_id) (kannel_smsc_online{{{L}}})'
place(stat("Routes fully UP", f'count(({RAV}) == 100) or vector(0)', thresholds=G, spark=False), 12, 4, 4)
place(stat("Routes DEGRADED (some links down)", f'count(({RAV}) < 100 and ({RAV}) > 0) or vector(0)', spark=False,
           thresholds=TH(1, 3)), 16, 4, 4)
place(stat("Routes DOWN (all links down)", f'count(({RAV}) == 0) or vector(0)', spark=False, thresholds=RED1), 20, 4, 4)
newline(4)


def timeline(title, expr, legend, steps, mappings=None, unit_=None):
    d = {"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": steps},
         "custom": {"fillOpacity": 85, "lineWidth": 0}}
    if mappings:
        d["mappings"] = mappings
    if unit_:
        d["unit"] = unit_
    return {"type": "state-timeline", "title": title, "targets": [tgt(expr, legend)],
            "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.85, "alignValue": "center",
                        "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "single"}}}


# colours from thresholds (always applied) + text from mappings
STATE_STEPS = [{"color": "dark-red", "value": None}, {"color": "red", "value": 1}, {"color": "yellow", "value": 2},
               {"color": "orange", "value": 3}, {"color": "green", "value": 4}]
place(timeline("Route availability (history)", RAV, "{{smsc_id}} @ {{server}}",
               [{"color": "red", "value": None}, {"color": "orange", "value": 1}, {"color": "green", "value": 100}],
               [{"type": "range", "options": {"from": 100, "to": 100, "result": {"text": "ALL LINKS UP", "color": "green"}}},
                {"type": "range", "options": {"from": 0.001, "to": 99.999, "result": {"text": "DEGRADED", "color": "orange"}}},
                {"type": "range", "options": {"from": 0, "to": 0, "result": {"text": "DOWN", "color": "red"}}}],
               "percent"), 0, 12, 11)
place(timeline("Links with problems in range (history)",
               f'{LS} and on (server, smsc_id, admin_id) (min_over_time({LS}[$__range]) < 4)',
               "{{admin_id}} @ {{server}}", STATE_STEPS, STATEMAP["value"]), 12, 12, 11)
newline(11)
q = place  # noqa
p = ts("Queued per SMSC-ID (top 10)", [tgt(f'topk(10, sum by (server, smsc_id) (kannel_smsc_queued{{{L}}}) > 0)',
                                         "{{smsc_id}} @ {{server}}")], "short", fill=0)
place(p, 0, 12, 8)
p = ts("DLR ratio % per SMSC-ID", [tgt(
    f'clamp_max(100 * {r(DLR, "server, smsc_id", "5m")} / ({r(MT, "server, smsc_id", "5m")} > 0.5), 200)',
    "{{smsc_id}} @ {{server}}")], "percent", fill=0)
p["fieldConfig"]["defaults"]["max"] = 200
p["fieldConfig"]["defaults"]["custom"]["thresholdsStyle"] = {"mode": "dashed"}
p["fieldConfig"]["defaults"]["thresholds"] = {"mode": "absolute", "steps": [{"color": "transparent", "value": None},
                                                                           {"color": "green", "value": 100}]}
place(p, 12, 12, 8)
newline(8)
place(ts("MT load per SMSC-ID (top 10, Kannel 1 min)", [tgt(
    f'topk(10, sum by (server, smsc_id) (kannel_smsc_load_messages_per_second{{{L}, type="sms", direction="outbound", window="1m"}}) > 0)',
    "{{smsc_id}} @ {{server}}")], "mps", fill=0), 0, 12, 8)
place(ts("DLR load per SMSC-ID (top 10, Kannel 1 min)", [tgt(
    f'topk(10, sum by (server, smsc_id) (kannel_smsc_load_messages_per_second{{{L}, type="dlr", direction="inbound", window="1m"}}) > 0)',
    "{{smsc_id}} @ {{server}}")], "mps", fill=0), 12, 12, 8)
newline(8)

# =========================================================== 4b. SMSC USERNAMES (accounts)
row("SMSC usernames (operator accounts)  -  $username")
CI = f'kannel_smsc_connection_info{{{L}, username=~"$username"}}'


def U(expr, by="server, username"):
    """attach the SMSC username to any per-link series and aggregate per username"""
    return (f'sum by ({by}) ({expr} * on (server, smsc_id, admin_id) group_left (username, host, port) '
            f'max by (server, smsc_id, admin_id, username, host, port) ({CI}))')


def UR(sel, by="server, username", win=RI, fn="rate"):
    return U(f'{fn}({sel}[{win}])', by)


GOPT = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "showThresholdLabels": False,
        "showThresholdMarkers": True, "orientation": "auto", "sizing": "auto", "minVizWidth": 75, "minVizHeight": 75}


def gauge(title, expr, legend, unit_, steps, mx=None):
    d = {"unit": unit_, "min": 0, "color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": steps},
         "decimals": 1}
    if mx is not None:
        d["max"] = mx
    return {"type": "gauge", "title": title, "targets": [tgt(expr, legend, instant=True)],
            "fieldConfig": {"defaults": d, "overrides": []}, "options": GOPT}


place(gauge("MT rate per SMSC username", UR(MT, win="1m"), "{{username}} @ {{server}}", "mps",
            [{"color": "blue", "value": None}]), 0, 12, 8)
place(gauge("Link availability per SMSC username",
            f'100 * {U(f"kannel_smsc_online{{{L}}}")} / {U(f"(kannel_smsc_online{{{L}}} * 0 + 1)")}',
            "{{username}} @ {{server}}", "percent",
            [{"color": "red", "value": None}, {"color": "orange", "value": 1}, {"color": "green", "value": 100}], 100), 12, 12, 8)
newline(8)
uk = "server, username, host, port"
place(table("SMSC username overview", [
    tgt(U(f"kannel_smsc_online{{{L}}}", uk), ref="A", instant=True, fmt="table"),
    tgt(U(f"(kannel_smsc_online{{{L}}} * 0 + 1)", uk), ref="B", instant=True, fmt="table"),
    tgt(f'100 * {U(f"kannel_smsc_online{{{L}}}", uk)} / {U(f"(kannel_smsc_online{{{L}}} * 0 + 1)", uk)}', ref="C", instant=True, fmt="table"),
    tgt(UR(MT, uk, "5m"), ref="D", instant=True, fmt="table"),
    tgt(UR(DLR, uk, "5m"), ref="E", instant=True, fmt="table"),
    tgt(UR(MO, uk, "5m"), ref="F", instant=True, fmt="table"),
    tgt(UR(MT, uk, "$__range", "increase"), ref="G", instant=True, fmt="table"),
    tgt(UR(FAIL, uk, "$__range", "increase"), ref="H", instant=True, fmt="table"),
    tgt(f'100 * {UR(FAIL, uk, "$__range", "increase")} / clamp_min({UR(MT, uk, "$__range", "increase")} + {UR(FAIL, uk, "$__range", "increase")}, 1)',
        ref="I", instant=True, fmt="table"),
    tgt(f'100 * {UR(DLR, uk, "$__range", "increase")} / clamp_min({UR(MT, uk, "$__range", "increase")}, 1)', ref="J", instant=True, fmt="table"),
    tgt(U(f"kannel_smsc_queued{{{L}}}", uk), ref="K", instant=True, fmt="table"),
    tgt(f'max_over_time({UR(MT, uk, "1m")}{PK})', ref="L", instant=True, fmt="table")],
    {"server": "Server", "username": "SMSC username", "host": "Operator host", "port": "Port",
     "Value #A": "Links online", "Value #B": "Links total", "Value #C": "Availability %", "Value #D": "MT/s",
     "Value #E": "DLR/s", "Value #F": "MO/s", "Value #G": "MT (range)", "Value #H": "Failed (range)", "Value #I": "Fail %",
     "Value #J": "DLR ratio %", "Value #K": "Queued", "Value #L": "Peak MT/s"},
    ["SMSC username", "Server", "Operator host", "Port", "Links online", "Links total", "Availability %", "MT/s",
     "Peak MT/s", "DLR/s", "MO/s", "MT (range)", "Failed (range)", "Fail %", "DLR ratio %", "Queued"],
    [ov("Availability %", [unit("percent"), {"id": "decimals", "value": 0}, {"id": "min", "value": 0}, {"id": "max", "value": 100},
                           cell("color-background"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [
                               {"color": "red", "value": None}, {"color": "orange", "value": 1}, {"color": "green", "value": 100}]}}]),
     ov("MT/s", MPS2 + [GAUGE, PURPLE]), ov("Peak MT/s", MPS2), ov("DLR/s", MPS2), ov("MO/s", MPS2),
     ov("MT (range)", INT), ov("Failed (range)", INT), ov("Fail %", PCT(2, 5)),
     ov("DLR ratio %", [unit("percent"), {"id": "decimals", "value": 1}])],
    sort=[{"displayName": "MT/s", "desc": True}]), 0, 24, 10)
newline(10)
place(ts("MT per SMSC username", [tgt(f'{UR(MT)} > 0', "{{username}} @ {{server}}")], "mps", stack=True), 0, 12, 9)
place(ts("DLR received per SMSC username", [tgt(f'{UR(DLR)} > 0', "{{username}} @ {{server}}")], "mps", stack=True), 12, 12, 9)
newline(9)
place(ts("Failure % per SMSC username", [tgt(
    f'100 * {UR(FAIL, win="5m")} / (({UR(MT, win="5m")} + {UR(FAIL, win="5m")}) > 0.1)', "{{username}} @ {{server}}")],
    "percent", fill=0), 0, 12, 8)
p = timeline("Availability per SMSC username (history)",
             f'100 * {U(f"kannel_smsc_online{{{L}}}")} / {U(f"(kannel_smsc_online{{{L}}} * 0 + 1)")}',
             "{{username}} @ {{server}}",
             [{"color": "red", "value": None}, {"color": "orange", "value": 1}, {"color": "green", "value": 100}],
             [{"type": "range", "options": {"from": 100, "to": 100, "result": {"text": "ALL LINKS UP", "color": "green"}}},
              {"type": "range", "options": {"from": 0.001, "to": 99.999, "result": {"text": "DEGRADED", "color": "orange"}}},
              {"type": "range", "options": {"from": 0, "to": 0, "result": {"text": "DOWN", "color": "red"}}}], "percent")
place(p, 12, 12, 8)
newline(8)

# =========================================================== 5. BOXES
row("Boxes (smsbox / wapbox / ksmppd / smppbox)  -  $box")
bk = "server, box_type, box_id"
place(table("Connected boxes", [
    tgt(f'kannel_box_online{{{BXF}}}', ref="A", instant=True, fmt="table"),
    tgt(f'kannel_box_uptime_seconds{{{BXF}}}', ref="B", instant=True, fmt="table"),
    tgt(f'kannel_box_queue{{{BXF}}}', ref="C", instant=True, fmt="table"),
    tgt(f'kannel_box_open_acks{{{BXF}}}', ref="D", instant=True, fmt="table"),
    tgt(f'kannel_box_ack_buffer{{{BXF}}}', ref="E", instant=True, fmt="table"),
    tgt(f'sum by ({bk}) (rate(kannel_box_messages_total{{{BXF}, type="sms", direction="received"}}[5m]))', ref="F", instant=True, fmt="table"),
    tgt(f'sum by ({bk}) (rate(kannel_box_messages_total{{{BXF}, type="dlr", direction="sent"}}[5m]))', ref="G", instant=True, fmt="table"),
    tgt(f'sum by ({bk}) (increase(kannel_box_failed_total{{{BXF}}}[$__range]))', ref="H", instant=True, fmt="table")],
    {"server": "Server", "box_type": "Type", "box_id": "Box ID", "Value #A": "Status", "Value #B": "Connected for",
     "Value #C": "Queue", "Value #D": "Open acks (HA)", "Value #E": "Ack buffer (HA)", "Value #F": "SMS from box/s (HA)",
     "Value #G": "DLR to box/s (HA)", "Value #H": "Failed (range, HA)"},
    ["Box ID", "Type", "Server", "Status", "Connected for", "Queue", "Open acks (HA)", "Ack buffer (HA)",
     "SMS from box/s (HA)", "DLR to box/s (HA)", "Failed (range, HA)"],
    [ov("Status", [ONOFF, cell("color-background")]), ov("Connected for", [unit("s")]),
     ov("SMS from box/s (HA)", MPS2), ov("DLR to box/s (HA)", MPS2), ov("Failed (range, HA)", INT),
     ov("Queue", [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": TH(100, 1000)}}])]), 0, 24, 7)
newline(7)
place(ts("Box queue", [tgt(f'kannel_box_queue{{{BXF}}}', "{{box_id}} ({{box_type}}) @ {{server}}")], "short", fill=0), 0, 12, 8)
place(ts("Box traffic (Kannel-HA)", [
    tgt(f'sum by (server, box_id, type, direction) (rate(kannel_box_messages_total{{{BXF}}}[{RI}])) > 0',
        "{{box_id}} {{type}} {{direction}} @ {{server}}")], "mps", fill=0), 12, 12, 8)
newline(8)

# =========================================================== 6. EXPORTER
row("Exporter health", collapsed=True)
eY = Y[0]
kids = []
for p, x in ((ts("Scrape duration", [tgt(f'kannel_scrape_duration_seconds{{{S}}}', "{{server}}")], "s", fill=0), 0),
             (ts("Scrape errors / min", [tgt(f'60 * rate(kannel_scrape_errors_total{{{S}}}[{RI}])', "{{server}}")], fill=0), 8),
             (ts("Seconds since last good scrape", [tgt(
                 f'time() - kannel_last_scrape_success_timestamp_seconds{{{S}}} and kannel_last_scrape_success_timestamp_seconds{{{S}}} > 0',
                 "{{server}}")], "s", fill=0), 16)):
    p.update({"gridPos": {"h": 7, "w": 8, "x": x, "y": eY}, "id": nid(), "datasource": DS})
    kids.append(p)
panels[-1]["panels"] = kids

# =========================================================== table row-merge fix (same labels on every query)
TABLE_KEYS = {"Gateway / build information": "server, product, flavour, build_type, version, build, hostname, host_ip, os_release, dlr_storage",
              "Gateway health": "server", "Peak throughput per server": "server",
              "Peak throughput per SMSC (route)": "server, smsc_id",
              "Peak throughput per SMSC link (admin-id)": "server, smsc_id, admin_id",
              "SMSC username overview": "server, username, host, port",
              "SMSC links": "server, smsc_id, admin_id", "Connected boxes": "server, box_type, box_id"}
for p in panels:
    if p.get("type") == "table" and p["title"] in TABLE_KEYS:
        for t in p["targets"]:
            keys = TABLE_KEYS[p["title"]]
            if p["title"] == "Gateway / build information" and t["refId"] == "B":
                t["expr"] = "max by (%s) (kannel_gateway_info{%s}) * 0 + on (server) group_left () max by (server) (kannel_uptime_seconds{%s})" % (keys, S, S)
            elif p["title"] == "SMSC links":   # add operator host / port / SMSC username to every link row
                t["expr"] = ("max by (server, smsc_id, admin_id, username, host, port) ((%s) * on (server, smsc_id, admin_id) "
                             "group_left (username, host, port) max by (server, smsc_id, admin_id, username, host, port) "
                             "(kannel_smsc_connection_info{%s}))" % (t["expr"], L))
            else:
                t["expr"] = "max by (%s) (%s)" % (keys, t["expr"])
        ex = p["transformations"][1]["options"]["excludeByName"]
        ex.update({"__name__": True, "job": True, "instance": True})

# =========================================================== descriptions
F = "\n\nFollows the Server, SMSC-ID and Link filters."
FS = "\n\nFollows the Server filter."
FB = "\n\nFollows the Server and Box filters."
DIRX = ("\n\nMT = messages Kannel sends to the operator (SMSC). DLR = delivery reports received from the operator. "
        "MO = messages received from the operator. Failed = MT the operator link could not send.")
PEAK = " Peak = highest 1-minute average inside the selected time range; Current = last minute."
DESC = {
 "Gateway / build information": "Identity of every bearerbox: product (Kannel or Kannel-HA), version, SVN or release (apt) "
     "build, build date, hostname, IP, uptime, DLR storage type and kernel." + FS,
 "Gateway health": "One row per bearerbox: reachability, running state, SMSC links online / total, connected boxes, "
     "MT / DLR / MO per second (bearerbox totals, 5 min), bearerbox and SMSC queues, DLRs waiting in dlr-storage for "
     "their report, store size (-1 = no store) and scrape time." + FS,
 "Peak MT (msg/s)": "Highest MT rate of the selected links." + PEAK + DIRX + F,
 "Peak DLR in (msg/s)": "Highest DLR receive rate." + PEAK + DIRX + F,
 "Peak MO (msg/s)": "Highest MO receive rate." + PEAK + DIRX + F,
 "Current MT (msg/s)": "MT rate of the selected links right now." + DIRX + F,
 "Current DLR in (msg/s)": "DLR receive rate right now." + DIRX + F,
 "Current MO (msg/s)": "MO receive rate right now." + DIRX + F,
 "Peak throughput per server": "Peak and current MT / DLR / MO per server." + PEAK + DIRX + F,
 "Peak throughput per SMSC (route)": "Peak and current rates per SMSC-ID (all links of the route together)." + PEAK + DIRX + F,
 "Peak throughput per SMSC link (admin-id)": "Peak and current rates of every single SMSC connection (admin-id). "
     "Repeated admin-ids (instances) are shown as name#2, name#3." + PEAK + DIRX + F,
 "Servers UP": "Bearerboxes whose status page was read successfully." + FS,
 "Servers DOWN": "Bearerboxes whose status page could not be read (down, timeout, wrong password)." + FS,
 "MT rate": "MT messages per second sent to operators." + DIRX + F,
 "DLR rate": "Delivery reports per second received from operators." + DIRX + F,
 "MO rate": "MO messages per second received from operators." + DIRX + F,
 "Failed rate": "MT messages per second that failed on the SMSC links." + F,
 "Failure %": "Failed / (sent + failed). Green < 2 %, orange 2-5 %, red > 5 %." + F,
 "DLR ratio": "DLRs received as % of MT sent. Low = operator reports missing or delayed." + F,
 "SMSC links online": "Links in 'online' state." + F,
 "SMSC links NOT online": "Links that are connecting, re-connecting, disconnected or dead." + F,
 "MT sent (range)": "MT sent in the selected time range." + F,
 "Failed (range)": "MT failed in the selected time range." + F,
 "SMSC queued": "MT waiting to be sent on the links. Growing = operator slow or link down." + F,
 "Bearerbox queued": "Messages in the bearerbox incoming/outgoing queues." + FS,
 "DLRs waiting": "Entries in dlr-storage waiting for their delivery report." + FS,
 "Boxes connected": "smsbox / wapbox / ksmppd / smppbox connections to the bearerboxes." + FS,
 "Messages by kind (SMSC links)": "MT sent, MT failed, DLR received and MO received per second." + DIRX + F,
 "MT per server (bearerbox)": "MT per second from bearerbox totals, stacked per server." + FS,
 "DLR received per server (bearerbox)": "DLRs per second from bearerbox totals." + FS,
 "MO received per server (bearerbox)": "MO per second from bearerbox totals." + FS,
 "Bearerbox reported load (1 min)": "The load Kannel computes itself over the last 60 s." + FS,
 "Queues & waiting DLRs": "Bearerbox queues, SMSC queues, DLRs waiting in storage and store size over time." + FS,
 "SMSC links": "Every SMSC connection: SMSC-ID (route), admin-id (link), SMSC username, operator host and port, state (ONLINE / RE-CONNECTING / CONNECTING / "
     "DISCONNECTED / DEAD), time in state, rates (5 min), MT / failed in range, fail %, DLR ratio, queue, how often it "
     "dropped from online in the range, and MT since the link object was created (resets on smsc restart)." + DIRX + F,
 "Top 10 SMSC-IDs by MT (range)": "Routes with the most MT in the range." + F,
 "Top 10 SMSC-IDs by failed (range)": "Routes with the most failed MT in the range." + F,
 "Top 10 failure % (range, >100 MT)": "Worst failure % per route (routes with 100 or fewer MT hidden)." + F,
 "MT per SMSC-ID": "MT per second per route (stacked)." + F,
 "DLR received per SMSC-ID": "DLRs per second per route (stacked)." + F,
 "MT failed per SMSC-ID": "Failed MT per second per route." + F,
 "MO received per SMSC-ID": "MO per second per route." + F,
 "Links ONLINE": "SMSC connections in ONLINE state." + F,
 "Links CONNECTING / RE-CONNECTING": "Connections trying to (re)connect to the operator." + F,
 "Links DISCONNECTED / DEAD": "Connections that are disconnected or dead (stopped / failed permanently)." + F,
 "Routes fully UP": "SMSC-IDs (routes) whose links are all online." + F,
 "Routes DEGRADED (some links down)": "Routes where some, but not all, links are online - traffic still flows "
     "with less capacity." + F,
 "Routes DOWN (all links down)": "Routes with no link online - MT for these routes cannot be sent." + F,
 "Route availability (history)": "One line per SMSC-ID: green = all links online, orange = degraded (some links "
     "down), red = no link online. Hover for the exact % of links online." + F,
 "Links with problems in range (history)": "Only links that were NOT online at some moment in the selected range: "
     "green ONLINE, orange RE-CONNECTING, yellow CONNECTING, red DISCONNECTED, dark red DEAD. Empty = every link "
     "stayed online. Healthy links are left out so the problem links stay readable." + F,
 "Queued per SMSC-ID (top 10)": "The 10 routes with the most MT waiting to be sent." + F,
 "DLR ratio % per SMSC-ID": "DLRs received / MT sent per route (5 min), only routes sending > 0.5 msg/s, capped at "
     "200 % (above 100 % = DLRs of older MT still arriving). Dashed green line = 100 %." + F,
 "MT load per SMSC-ID (top 10, Kannel 1 min)": "MT/s Kannel reports per route over the last minute - top 10 routes." + F,
 "DLR load per SMSC-ID (top 10, Kannel 1 min)": "DLR/s received per route over the last minute - top 10 routes." + F,
 "MT rate per SMSC username": "Current MT/s (1 min) per SMSC username (the system-id Kannel logs in with at the "
     "operator, taken from the link name SMPP:host:port/port:USERNAME:system-type). All links of the username together." + F,
 "Link availability per SMSC username": "% of the username's links that are online. Green 100 %, orange = some links "
     "down, red = all down." + F,
 "SMSC username overview": "One row per SMSC username per server and operator host:port - links online / total, "
     "availability, MT now / peak in range, DLR and MO rates, MT and failed in range, fail %, DLR ratio and queue." + DIRX + F,
 "MT per SMSC username": "MT per second per username (stacked)." + DIRX + F,
 "DLR received per SMSC username": "DLRs per second per username (stacked)." + DIRX + F,
 "Failure % per SMSC username": "Failed / (sent + failed) per username, 5-minute window." + F,
 "Availability per SMSC username (history)": "Green = all links of the username online, orange = some down, red = all "
     "down. Hover for the exact %." + F,
 "Connected boxes": "Boxes connected to the bearerboxes. Queue = messages waiting for the box. Kannel-HA builds also "
     "report open acks, ack buffer, per-box traffic and failed messages (empty on vanilla Kannel)." + FB,
 "Box queue": "Messages queued towards each box over time. Growing = box is slow or stuck." + FB,
 "Box traffic (Kannel-HA)": "SMS / DLR per second between bearerbox and each box (Kannel-HA only)." + FB,
 "Scrape duration": "Time the exporter needs to read each status page." + FS,
 "Scrape errors / min": "Failed status page reads per minute." + FS,
 "Seconds since last good scrape": "Grows while a bearerbox's status page is unreachable." + FS,
}


def apply(ps):
    for p in ps:
        if p.get("title") in DESC:
            p["description"] = DESC[p["title"]]
        apply(p.get("panels", []))


apply(panels)
missing = [p["title"] for p in panels if p["type"] != "row" and not p.get("description")]
assert not missing, missing


def qvar(name, label, query):
    return {"name": name, "label": label, "type": "query", "datasource": DS, "definition": query,
            "query": {"query": query, "refId": name, "qryType": 1}, "refresh": 2, "multi": True, "includeAll": True,
            "allValue": ".*", "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "sort": 7,
            "hide": 0, "regex": "", "options": []}


dash = {
    "annotations": {"list": [
        {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
         "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"},
        {"datasource": DS, "enable": True, "iconColor": "red", "name": "bearerbox restarts",
         "expr": f'kannel_uptime_seconds{{{S}}} < 300', "titleFormat": "bearerbox restarted", "textFormat": "{{server}}", "step": "60s"},
        {"datasource": DS, "enable": True, "iconColor": "orange", "name": "Server down",
         "expr": f'kannel_up{{{S}}} == 0', "titleFormat": "Status page unreachable", "textFormat": "{{server}}", "step": "60s"}]},
    "description": "Kannel bearerbox (vanilla / SVN / Kannel-HA) - servers, SMSC routes, SMSC links and boxes",
    "editable": True, "graphTooltip": 1, "links": [], "panels": panels, "refresh": "30s", "schemaVersion": 39,
    "tags": ["sms", "kannel", "bearerbox"],
    "templating": {"list": [
        {"name": "datasource", "label": "Data source", "type": "datasource", "query": "prometheus", "current": {},
         "hide": 0, "refresh": 1, "regex": "", "options": []},
        qvar("server", "Kannel server", "label_values(kannel_up, server)"),
        qvar("smsc_id", "SMSC-ID (route)", 'label_values(kannel_smsc_state{server=~"$server"}, smsc_id)'),
        qvar("admin_id", "Link (admin-id)", 'label_values(kannel_smsc_state{server=~"$server", smsc_id=~"$smsc_id"}, admin_id)'),
        qvar("username", "SMSC username", 'label_values(kannel_smsc_connection_info{server=~"$server", smsc_id=~"$smsc_id"}, username)'),
        qvar("box", "Box", 'label_values(kannel_box_online{server=~"$server"}, box_id)')]},
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m", "15m", "1h"]},
    "timezone": "browser", "title": "Kannel - Bearerbox Monitoring", "uid": "kannel-bearerbox", "version": 1}
json.dump(dash, open(os.path.join(HERE, "..", "dashboards", "kannel_dashboard.json"), "w", newline="\n"), indent=2)
print("panels:", _id[0])
