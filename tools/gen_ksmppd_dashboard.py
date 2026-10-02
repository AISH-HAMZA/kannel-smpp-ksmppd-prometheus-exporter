#!/usr/bin/env python3
"""Generates ksmppd_dashboard.json (Grafana).  Import via Dashboards > New > Import."""
import json
import os

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_helpers.py")).read())

S = 'server=~"$server"'
C = 'server=~"$server", esme=~"$esme"'
B = C + ', ip=~"$ip", type=~"$bind_type"'
RI = "$__rate_interval"
PK = "[$__range:15s]"

# message selectors (verified in ksmppd source):  submits = mt (accepted) + errors (rejected)
SUBM = ("ksmppd_esme_mt_total", "ksmppd_esme_errors_total")
DELV = ("ksmppd_esme_mo_total", "ksmppd_esme_dlr_total")
BSUBM = ("ksmppd_bind_mt_total", "ksmppd_bind_errors_total")
BDELV = ("ksmppd_bind_mo_total", "ksmppd_bind_dlr_total")


def agg(fn, names, flt, by="", win=RI):
    # two separate aggregations added together (rate over 2 metric names at once is not allowed)
    b = "sum by (%s) " % by if by else "sum "
    return "(" + " + ".join("%s(%s(%s{%s}[%s]))" % (b, fn, n, flt, win) for n in names) + ")"


def rate_sum(names, flt, by="", win=RI):
    return agg("rate", names, flt, by, win)


TYPEMAP = {"id": "mappings", "value": [{"type": "value", "options": {
    "trx": {"text": "Transceiver (TRX)", "color": "blue", "index": 0},
    "tx": {"text": "Transmitter (TX)", "color": "purple", "index": 1},
    "rx": {"text": "Receiver (RX)", "color": "orange", "index": 2}}}]}
MPS1 = [unit("mps"), {"id": "decimals", "value": 1}]
MPS2 = [unit("mps"), {"id": "decimals", "value": 2}]
INT = [{"id": "decimals", "value": 0}]
GAUGE = cell("gauge", {"mode": "gradient"})
PURPLE = {"id": "color", "value": {"mode": "continuous-BlPu"}}
ERRTH = [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [
    {"color": "green", "value": None}, {"color": "orange", "value": 2}, {"color": "red", "value": 5}]}}]
G = [{"color": "green", "value": None}]
RED1 = [{"color": "green", "value": None}, {"color": "red", "value": 1}]

# =========================================================== 1. SERVERS & PEAKS
row("KSMPPD Servers & Peak Throughput  -  $server")
sv = "sum by (server)"
place(table("KSMPPD servers", [
    tgt(f'ksmppd_up{{{S}}}', ref="A", instant=True, fmt="table"),
    tgt(f'ksmppd_uptime_seconds{{{S}}}', ref="B", instant=True, fmt="table"),
    tgt(f'ksmppd_known_esmes{{{S}}}', ref="C", instant=True, fmt="table"),
    tgt(f'ksmppd_esmes_connected{{{S}}}', ref="D", instant=True, fmt="table"),
    tgt(f'ksmppd_binds_active{{{S}}}', ref="E", instant=True, fmt="table"),
    tgt(rate_sum(SUBM, S, "server", "1m"), ref="F", instant=True, fmt="table"),
    tgt(rate_sum(DELV, S, "server", "1m"), ref="G", instant=True, fmt="table"),
    tgt(f'{sv} (rate(ksmppd_esme_errors_total{{{S}}}[5m]))', ref="H", instant=True, fmt="table"),
    tgt(f'{sv} (ksmppd_esme_open_acks{{{S}}})', ref="I", instant=True, fmt="table"),
    tgt(f'{sv} (ksmppd_esme_queued{{{S}}})', ref="J", instant=True, fmt="table"),
    tgt(f'ksmppd_load_pdus_per_second{{{S}, direction="inbound", window="1m"}}', ref="K", instant=True, fmt="table"),
    tgt(f'ksmppd_load_pdus_per_second{{{S}, direction="outbound", window="1m"}}', ref="L", instant=True, fmt="table"),
    tgt(f'ksmppd_scrape_duration_seconds{{{S}}}', ref="M", instant=True, fmt="table")],
    {"server": "Server", "Value #A": "Status", "Value #B": "Uptime", "Value #C": "Known customers",
     "Value #D": "Connected", "Value #E": "Binds", "Value #F": "Submit/s", "Value #G": "Deliver/s",
     "Value #H": "Errors/s", "Value #I": "Open acks", "Value #J": "Queued", "Value #K": "PDU in/s (1m)",
     "Value #L": "PDU out/s (1m)", "Value #M": "Scrape"},
    ["Server", "Status", "Uptime", "Known customers", "Connected", "Binds", "Submit/s", "Deliver/s", "Errors/s",
     "Open acks", "Queued", "PDU in/s (1m)", "PDU out/s (1m)", "Scrape"],
    [ov("Status", [UPDOWN, cell("color-background")]), ov("Uptime", [unit("s")]),
     ov("Submit/s", MPS1 + [GAUGE, PURPLE]), ov("Deliver/s", MPS1), ov("Errors/s", MPS2),
     ov("PDU in/s (1m)", MPS1), ov("PDU out/s (1m)", MPS1), ov("Scrape", [unit("s")])],
    hide_extra=("__name__", "job", "instance", "direction", "window")), 0, 24, 6)
newline(6)
IN_ALL, OUT_ALL = rate_sum(SUBM, S, win="1m"), rate_sum(DELV, S, win="1m")
place(stat("Peak Inbound (msg/s)", f'max_over_time({IN_ALL}{PK})', "mps", color="blue", spark=False, decimals=0), 0, 6, 4)
place(stat("Peak Outbound (msg/s)", f'max_over_time({OUT_ALL}{PK})', "mps", color="purple", spark=False, decimals=0), 6, 6, 4)
place(stat("Current Inbound (msg/s)", IN_ALL, "mps", color="blue", decimals=1), 12, 6, 4)
place(stat("Current Outbound (msg/s)", OUT_ALL, "mps", color="purple", decimals=1), 18, 6, 4)
newline(4)
PEAKCOLS = {"Value #A": "Peak inbound", "Value #B": "Peak outbound", "Value #C": "Current inbound",
            "Value #D": "Current outbound"}
PEAKOV = [ov("Peak inbound", MPS1 + [GAUGE, PURPLE]), ov("Peak outbound", MPS1 + [GAUGE, PURPLE]),
          ov("Current inbound", MPS1), ov("Current outbound", MPS1)]


def peak_targets(names_in, names_out, flt, by):
    return [tgt(f'max_over_time({rate_sum(names_in, flt, by, "1m")}{PK})', ref="A", instant=True, fmt="table"),
            tgt(f'max_over_time({rate_sum(names_out, flt, by, "1m")}{PK})', ref="B", instant=True, fmt="table"),
            tgt(rate_sum(names_in, flt, by, "1m"), ref="C", instant=True, fmt="table"),
            tgt(rate_sum(names_out, flt, by, "1m"), ref="D", instant=True, fmt="table")]


place(table("Peak throughput per server", peak_targets(SUBM, DELV, S, "server"), dict(server="Server", **PEAKCOLS),
            ["Server", "Peak inbound", "Peak outbound", "Current inbound", "Current outbound"], PEAKOV,
            sort=[{"displayName": "Peak inbound", "desc": True}]), 0, 10, 8)
place(table("Peak throughput per server & customer", peak_targets(SUBM, DELV, C, "server, esme"),
            dict(server="Server", esme="Customer (ESME)", **PEAKCOLS),
            ["Customer (ESME)", "Server", "Peak inbound", "Peak outbound", "Current inbound", "Current outbound"],
            PEAKOV, sort=[{"displayName": "Peak inbound", "desc": True}]), 10, 14, 8)
newline(8)
place(table("Peak throughput per server, customer & bind (session)",
            peak_targets(BSUBM, BDELV, B, "server, esme, bind_id, ip, type") +
            [tgt(f'max by (server, esme, bind_id, ip, type) (ksmppd_bind_uptime_seconds{{{B}}})', ref="E",
                 instant=True, fmt="table")],
            dict(server="Server", esme="Customer (ESME)", bind_id="Bind ID", ip="Source IP", type="Bind type",
                 **PEAKCOLS, **{"Value #E": "Bind age"}),
            ["Customer (ESME)", "Server", "Bind ID", "Source IP", "Bind type", "Peak inbound", "Peak outbound",
             "Current inbound", "Current outbound", "Bind age"],
            PEAKOV + [ov("Bind age", [unit("s")]), ov("Bind type", [TYPEMAP, cell("color-text")])],
            sort=[{"displayName": "Peak inbound", "desc": True}]), 0, 24, 9)
newline(9)

# =========================================================== 2. OVERVIEW
row("Overview  -  $server  /  $esme")
place(stat("Servers UP", f'sum(ksmppd_up{{{S}}})', thresholds=G, spark=False), 0, 3, 4)
place(stat("Servers DOWN", f'count(ksmppd_up{{{S}}} == 0) or vector(0)', spark=False, thresholds=RED1), 3, 3, 4)
place(stat("Submit rate (MT)", rate_sum(SUBM, C), "mps", color="blue"), 6, 3, 4)
place(stat("Deliver rate (DLR+MO)", rate_sum(DELV, C), "mps", color="purple"), 9, 3, 4)
place(stat("Error rate", f'sum(rate(ksmppd_esme_errors_total{{{C}}}[{RI}]))', "mps",
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 10}]), 12, 3, 4)
place(stat("Error %", f'100 * sum(rate(ksmppd_esme_errors_total{{{C}}}[{RI}])) / clamp_min({rate_sum(SUBM, C)}, 0.0001)',
           "percent", decimals=2, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 2},
                                              {"color": "red", "value": 5}]), 15, 3, 4)
place(stat("Submitted (range)", agg('increase', SUBM, C, win='$__range'), color="blue", spark=False), 18, 3, 4)
place(stat("Errors (range)", f'sum(increase(ksmppd_esme_errors_total{{{C}}}[$__range]))', color="orange", spark=False), 21, 3, 4)
newline(4)
place(stat("Customers connected", f'count(ksmppd_esme_connected{{{C}}} == 1) or vector(0)', thresholds=G, spark=False), 0, 3, 4)
place(stat("Customers disconnected", f'count(ksmppd_esme_connected{{{C}}} == 0) or vector(0)', spark=False,
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}]), 3, 3, 4)
place(stat("Active binds", f'sum(ksmppd_esme_binds{{{C}}})', color="teal"), 6, 3, 4)
place(stat("Bind utilisation", f'100 * sum(ksmppd_esme_binds{{{C}}}) / clamp_min(sum(ksmppd_esme_max_binds{{{C}}}), 1)',
           "percent", decimals=0, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 80},
                                              {"color": "red", "value": 95}]), 9, 3, 4)
place(stat("Open acks", f'sum(ksmppd_esme_open_acks{{{C}}})', thresholds=[{"color": "green", "value": None},
      {"color": "orange", "value": 50}, {"color": "red", "value": 500}]), 12, 3, 4)
place(stat("Queued PDUs", f'sum(ksmppd_esme_queued{{{C}}})', thresholds=[{"color": "green", "value": None},
      {"color": "orange", "value": 100}, {"color": "red", "value": 1000}]), 15, 3, 4)
place(stat("Pending routing", f'sum(ksmppd_esme_pending_routing{{{C}}})', thresholds=[{"color": "green", "value": None},
      {"color": "orange", "value": 10}, {"color": "red", "value": 100}]), 18, 3, 4)
place(stat("DLR ratio", f'100 * sum(rate(ksmppd_esme_dlr_total{{{C}}}[{RI}])) / clamp_min(sum(rate(ksmppd_esme_mt_total{{{C}}}[{RI}])), 0.0001)',
           "percent", decimals=1, color="purple"), 21, 3, 4)
newline(4)

# =========================================================== 2b. TPS
row("TPS limit & utilisation  -  $server  /  $esme")
ALLM = SUBM + DELV                                   # achieved TPS = inbound (MT+errors) + outbound (DLR+MO)
BALL = BSUBM + BDELV
ACH = rate_sum(ALLM, C, "server, esme", "1m")
LIMC = f'(ksmppd_esme_throughput_limit{{{C}}} > 0)'
UTH = [{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 90}]
place(stat("TPS limit (sum of customers)", f'sum(ksmppd_esme_throughput_limit{{{C}}})', "mps", color="purple", decimals=0, spark=False), 0, 4, 4)
place(stat("Achieved TPS (in + out)", rate_sum(ALLM, C, win="1m"), "mps", color="teal", decimals=1), 4, 4, 4)
place(stat("Inbound TPS", rate_sum(SUBM, C, win="1m"), "mps", color="blue", decimals=1), 8, 4, 4)
place(stat("Outbound TPS", rate_sum(DELV, C, win="1m"), "mps", color="purple", decimals=1), 12, 4, 4)
place(stat("Peak TPS (range)", f'max_over_time({rate_sum(ALLM, C, win="1m")}{PK})', "mps", color="teal", decimals=1, spark=False), 16, 4, 4)
place(stat("Highest customer TPS utilisation", f'max(100 * {ACH} / on (server, esme) {LIMC})', "percent", decimals=1,
           thresholds=UTH), 20, 4, 4)
newline(4)
UTILCOL = [unit("percent"), {"id": "decimals", "value": 1}, {"id": "min", "value": 0}, {"id": "max", "value": 100},
           cell("gauge", {"mode": "gradient"}), {"id": "color", "value": {"mode": "continuous-GrYlRd"}}]
place(table("TPS per customer", [
    tgt(f'ksmppd_esme_throughput_limit{{{C}}}', ref="A", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_binds{{{C}}}', ref="B", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_max_binds{{{C}}}', ref="C", instant=True, fmt="table"),
    tgt(rate_sum(SUBM, C, "server, esme", "1m"), ref="D", instant=True, fmt="table"),
    tgt(rate_sum(DELV, C, "server, esme", "1m"), ref="E", instant=True, fmt="table"),
    tgt(ACH, ref="F", instant=True, fmt="table"),
    tgt(f'max_over_time({ACH}{PK})', ref="G", instant=True, fmt="table"),
    tgt(f'{ACH} / on (server, esme) clamp_min(ksmppd_esme_binds{{{C}}}, 1)', ref="H", instant=True, fmt="table"),
    tgt(f'100 * {ACH} / on (server, esme) {LIMC}', ref="I", instant=True, fmt="table"),
    tgt(f'100 * max_over_time({ACH}{PK}) / on (server, esme) {LIMC}', ref="J", instant=True, fmt="table"),
    tgt(f'clamp_min({LIMC} - on (server, esme) {ACH}, 0)', ref="K", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "Value #A": "TPS limit", "Value #B": "Sessions",
     "Value #C": "Max sessions", "Value #D": "Inbound TPS", "Value #E": "Outbound TPS", "Value #F": "Achieved TPS",
     "Value #G": "Peak TPS", "Value #H": "Avg TPS / session", "Value #I": "Util %", "Value #J": "Peak util %",
     "Value #K": "Headroom TPS"},
    ["Customer (ESME)", "Server", "TPS limit", "Sessions", "Max sessions", "Inbound TPS", "Outbound TPS",
     "Achieved TPS", "Peak TPS", "Avg TPS / session", "Util %", "Peak util %", "Headroom TPS"],
    [ov("TPS limit", [{"id": "decimals", "value": 0}]), ov("Inbound TPS", MPS2), ov("Outbound TPS", MPS2),
     ov("Achieved TPS", MPS2), ov("Peak TPS", MPS2), ov("Avg TPS / session", MPS2), ov("Headroom TPS", MPS1),
     ov("Util %", UTILCOL), ov("Peak util %", UTILCOL)],
    sort=[{"displayName": "Util %", "desc": True}]), 0, 24, 10)
newline(10)
place(ts("TPS utilisation % per customer (achieved / limit)", [tgt(
    f'100 * {rate_sum(ALLM, C, "server, esme")} / on (server, esme) {LIMC}', "{{esme}} @ {{server}}")],
    "percent", fill=0), 0, 12, 8)
place(ts("Achieved TPS vs limit", [
    tgt(rate_sum(ALLM, C), "Achieved TPS (in + out)", "A"),
    tgt(rate_sum(SUBM, C), "Inbound TPS", "B"),
    tgt(rate_sum(DELV, C), "Outbound TPS", "C"),
    tgt(f'sum(ksmppd_esme_throughput_limit{{{C}}})', "TPS limit", "D")], "mps", fill=0,
    overrides=[ov("TPS limit", [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 10]}},
                                {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}])]), 12, 12, 8)
newline(8)
place(ts("Session share of customer TPS limit % (busiest sessions)", [tgt(
    f'topk(15, 100 * {rate_sum(BALL, B, "server, esme, bind_id")} / on (server, esme) group_left () {LIMC})',
    "{{esme}} #{{bind_id}}")], "percent", fill=0), 0, 24, 8)
newline(8)

# =========================================================== 3. TRAFFIC
row("Traffic")
place(ts("Messages by kind", [
    tgt(f'sum(rate(ksmppd_esme_mt_total{{{C}}}[{RI}]))', "MT accepted", "A"),
    tgt(f'sum(rate(ksmppd_esme_errors_total{{{C}}}[{RI}]))', "MT rejected (errors)", "B"),
    tgt(f'sum(rate(ksmppd_esme_dlr_total{{{C}}}[{RI}]))', "DLR delivered", "C"),
    tgt(f'sum(rate(ksmppd_esme_mo_total{{{C}}}[{RI}]))', "MO delivered", "D")], "mps",
    overrides=[ov("MT rejected (errors)", [{"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}])]), 0, 12, 8)
place(ts("Submit rate per server", [tgt(rate_sum(SUBM, S, "server"), "{{server}}")], "mps", stack=True), 12, 12, 8)
newline(8)
place(ts("Deliver (DLR+MO) rate per server", [tgt(rate_sum(DELV, S, "server"), "{{server}}")], "mps", stack=True), 0, 12, 8)
place(ts("PDUs processed per server", [
    tgt(f'sum by (server) (rate(ksmppd_pdus_total{{{S}, direction="inbound"}}[{RI}]))', "{{server}} in", "A"),
    tgt(f'sum by (server) (rate(ksmppd_pdus_total{{{S}, direction="outbound"}}[{RI}]))', "{{server}} out", "B")],
    "mps", fill=0), 12, 12, 8)
newline(8)
place(ts("ksmppd reported load (last 60 s)", [
    tgt(f'ksmppd_load_pdus_per_second{{{S}, window="1m"}}', "{{server}} {{direction}}")], "mps", fill=0), 0, 12, 7)
place(ts("Submitted messages per interval", [
    tgt(agg('increase', SUBM, S, 'server', '$__interval'), "{{server}}")], "short", stack=True,
    draw="bars", fill=80, legend_calcs=("sum", "max")), 12, 12, 7)
newline(7)

# =========================================================== 4. CUSTOMERS
row("Customers (ESME)  -  $esme")
by = "sum by (server, esme)"
place(table("Customer overview", [
    tgt(f'ksmppd_esme_connected{{{C}}}', ref="A", instant=True, fmt="table"),
    tgt(f'time() - ksmppd_esme_state_since_timestamp_seconds{{{C}}}', ref="B", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_binds{{{C}}}', ref="C", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_max_binds{{{C}}}', ref="D", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_connected_ips{{{C}}}', ref="E", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_throughput_limit{{{C}}}', ref="F", instant=True, fmt="table"),
    tgt(rate_sum(SUBM, C, "server, esme", "5m"), ref="G", instant=True, fmt="table"),
    tgt(rate_sum(DELV, C, "server, esme", "5m"), ref="H", instant=True, fmt="table"),
    tgt(f'{by} (increase(ksmppd_esme_mt_total{{{C}}}[$__range]))', ref="I", instant=True, fmt="table"),
    tgt(f'{by} (increase(ksmppd_esme_errors_total{{{C}}}[$__range]))', ref="J", instant=True, fmt="table"),
    tgt(f'{by} (increase(ksmppd_esme_dlr_total{{{C}}}[$__range]))', ref="K", instant=True, fmt="table"),
    tgt(f'{by} (increase(ksmppd_esme_mo_total{{{C}}}[$__range]))', ref="L", instant=True, fmt="table"),
    tgt(f'100 * {by} (increase(ksmppd_esme_errors_total{{{C}}}[$__range])) / clamp_min({agg("increase", SUBM, C, "server, esme", "$__range")}, 1)',
        ref="M", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_open_acks{{{C}}}', ref="N", instant=True, fmt="table"),
    tgt(f'ksmppd_esme_bind_uptime_min_seconds{{{C}}}', ref="O", instant=True, fmt="table"),
    tgt(f'{by} (ksmppd_esme_queued{{{C}}})', ref="P", instant=True, fmt="table"),
    tgt(f'100 * {rate_sum(SUBM + DELV, C, "server, esme", "5m")} / on (server, esme) (ksmppd_esme_throughput_limit{{{C}}} > 0)', ref="R", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "Value #A": "Status", "Value #B": "State for",
     "Value #C": "Binds", "Value #D": "Max binds", "Value #E": "IPs", "Value #F": "TPS limit",
     "Value #G": "Submit/s", "Value #H": "Deliver/s", "Value #I": "MT (range)", "Value #J": "Errors (range)",
     "Value #K": "DLR (range)", "Value #L": "MO (range)", "Value #M": "Error %", "Value #N": "Open acks",
     "Value #O": "Last reconnect", "Value #P": "Queued", "Value #R": "TPS util %"},
    ["Customer (ESME)", "Server", "Status", "State for", "Binds", "Max binds", "IPs", "TPS limit", "TPS util %", "Submit/s",
     "Deliver/s", "MT (range)", "Errors (range)", "Error %", "DLR (range)", "MO (range)", "Open acks", "Queued",
     "Last reconnect"],
    [ov("Status", [CONN, cell("color-background")]), ov("State for", [unit("s")]),
     ov("Submit/s", MPS2 + [GAUGE, PURPLE]), ov("Deliver/s", MPS2), ov("MT (range)", INT), ov("Errors (range)", INT),
     ov("DLR (range)", INT), ov("MO (range)", INT), ov("Error %", [unit("percent"), {"id": "decimals", "value": 2}] + ERRTH),
     ov("Last reconnect", [unit("s")]), ov("TPS limit", [{"id": "decimals", "value": 0}]), ov("TPS util %", [unit("percent"), {"id": "decimals", "value": 1}] + [cell("color-text"), {"id": "thresholds", "value": {"mode": "absolute", "steps": [{"color": "green", "value": None}, {"color": "orange", "value": 70}, {"color": "red", "value": 90}]}}])],
    hide_extra=("__name__", "job", "instance"), sort=[{"displayName": "MT (range)", "desc": True}]), 0, 24, 10)
newline(10)
place(bargauge("Top 10 customers by MT (range)",
               f'topk(10, {by} (increase(ksmppd_esme_mt_total{{{C}}}[$__range])))', "{{esme}} @ {{server}}"), 0, 8, 9)
place(bargauge("Top 10 customers by errors (range)",
               f'topk(10, {by} (increase(ksmppd_esme_errors_total{{{C}}}[$__range])) > 0)', "{{esme}} @ {{server}}",
               color_mode="continuous-YlRd"), 8, 8, 9)
place(bargauge("Top 10 error % (range, >100 msgs)",
               f'topk(10, 100 * {by} (increase(ksmppd_esme_errors_total{{{C}}}[$__range])) / ({agg("increase", SUBM, C, "server, esme", "$__range")} > 100))',
               "{{esme}} @ {{server}}", "percent", color_mode="continuous-YlRd"), 16, 8, 9)
newline(9)
place(ts("Submit rate per customer", [tgt(f'{rate_sum(SUBM, C, "server, esme")} > 0', "{{esme}} @ {{server}}")],
         "mps", stack=True), 0, 12, 9)
place(ts("Deliver (DLR+MO) rate per customer", [tgt(f'{rate_sum(DELV, C, "server, esme")} > 0', "{{esme}} @ {{server}}")],
         "mps", stack=True), 12, 12, 9)
newline(9)
place(ts("Error rate per customer", [tgt(f'{by} (rate(ksmppd_esme_errors_total{{{C}}}[{RI}])) > 0', "{{esme}} @ {{server}}")],
         "mps"), 0, 12, 8)
place(ts("Error % per customer", [tgt(f'100 * {by} (rate(ksmppd_esme_errors_total{{{C}}}[{RI}])) / ({rate_sum(SUBM, C, "server, esme")} > 0)',
                                      "{{esme}} @ {{server}}")], "percent", fill=0), 12, 12, 8)
newline(8)
place(ts("Achieved TPS per customer vs limit", [
    tgt(f'{rate_sum(SUBM + DELV, C, "server, esme")} > 0', "achieved {{esme}}", "A"),
    tgt(f'ksmppd_esme_throughput_limit{{{C}}} and on (server, esme) ({rate_sum(SUBM + DELV, C, "server, esme")} > 0)', "limit {{esme}}", "B")],
    "mps", fill=0), 0, 12, 8)
place(ts("DLR ratio per customer (DLR / MT)", [tgt(
    f'100 * {by} (rate(ksmppd_esme_dlr_total{{{C}}}[{RI}])) / ({by} (rate(ksmppd_esme_mt_total{{{C}}}[{RI}])) > 0)',
    "{{esme}} @ {{server}}")], "percent", fill=0), 12, 12, 8)
newline(8)
place({"type": "state-timeline", "title": "Customer connection state (history)",
       "targets": [tgt(f'ksmppd_esme_connected{{{C}}}', "{{esme}} @ {{server}}")],
       "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": CONN["value"],
                                    "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None},
                                                                                 {"color": "green", "value": 1}]},
                                    "custom": {"fillOpacity": 80, "lineWidth": 0}}, "overrides": []},
       "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8, "legend": {"showLegend": False},
                   "tooltip": {"mode": "single"}}}, 0, 12, 9)
place(ts("Binds per customer", [tgt(f'ksmppd_esme_binds{{{C}}}', "{{esme}} @ {{server}}")], "short", stack=True,
         legend_calcs=("min", "max", "lastNotNull")), 12, 12, 9)
newline(9)
place(ts("Binds & drops per customer", [
    tgt(f'sum by (esme, type) (increase(ksmppd_esme_bind_connects_total{{{C}, type=~"$bind_type"}}[$__interval])) > 0',
        "bind  {{esme}} {{type}}", "A"),
    tgt(f'-1 * (sum by (esme, type) (increase(ksmppd_esme_bind_disconnects_total{{{C}, type=~"$bind_type"}}[$__interval])) > 0)',
        "drop  {{esme}} {{type}}", "B")], "short", draw="bars", fill=80, legend_calcs=("sum",)), 0, 12, 8)
place(ts("Open acks & queued per customer", [
    tgt(f'ksmppd_esme_open_acks{{{C}}}', "open acks {{esme}}", "A"),
    tgt(f'{by} (ksmppd_esme_queued{{{C}}}) > 0', "queued {{esme}}", "B"),
    tgt(f'ksmppd_esme_pending_routing{{{C}}} > 0', "routing {{esme}}", "C")], "short", fill=0), 12, 12, 8)
newline(8)

# =========================================================== 5. BINDS / SESSIONS
row("Binds / sessions  -  $bind_type  /  $ip")
place(stat("Transceiver binds (TRX)", f'sum(ksmppd_esme_binds_by_type{{{C}, type="trx"}})', color="blue"), 0, 4, 4)
place(stat("Transmitter binds (TX)", f'sum(ksmppd_esme_binds_by_type{{{C}, type="tx"}})', color="purple"), 4, 4, 4)
place(stat("Receiver binds (RX)", f'sum(ksmppd_esme_binds_by_type{{{C}, type="rx"}})', color="orange"), 8, 4, 4)
place(stat("Binds (range)", f'sum(increase(ksmppd_esme_bind_connects_total{{{C}, type=~"$bind_type"}}[$__range]))',
           color="teal", spark=False), 12, 4, 4)
place(stat("Drops (range)", f'sum(increase(ksmppd_esme_bind_disconnects_total{{{C}, type=~"$bind_type"}}[$__range]))',
           spark=False, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 5},
                                    {"color": "red", "value": 50}]), 16, 4, 4)
place(stat("Simulate-mode binds", f'sum(ksmppd_esme_simulate_binds{{{C}}})', spark=False,
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}]), 20, 4, 4)
newline(4)
bl = "server, esme, bind_id, ip, type"
place(table("Bind details", [
    tgt(f'ksmppd_bind_uptime_seconds{{{B}}}', ref="A", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_open_acks{{{B}}}', ref="B", instant=True, fmt="table"),
    tgt(rate_sum(BSUBM, B, bl, "5m"), ref="C", instant=True, fmt="table"),
    tgt(rate_sum(BDELV, B, bl, "5m"), ref="D", instant=True, fmt="table"),
    tgt(f'sum by ({bl}) (ksmppd_bind_load_pdus_per_second{{{B}, direction="inbound"}})', ref="E", instant=True, fmt="table"),
    tgt(f'sum by ({bl}) (ksmppd_bind_load_pdus_per_second{{{B}, direction="outbound"}})', ref="F", instant=True, fmt="table"),
    tgt(f'sum by ({bl}) (ksmppd_bind_queued{{{B}}})', ref="G", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_pending_routing{{{B}}}', ref="H", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_mt_total{{{B}}}', ref="I", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_errors_total{{{B}}}', ref="J", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_dlr_total{{{B}}}', ref="K", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_mo_total{{{B}}}', ref="L", instant=True, fmt="table"),
    tgt(f'ksmppd_bind_simulate{{{B}}}', ref="M", instant=True, fmt="table"),
    tgt(f'100 * {rate_sum(BSUBM + BDELV, B, bl, "5m")} / on (server, esme) group_left () (ksmppd_esme_throughput_limit{{{C}}} > 0)', ref="N", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "bind_id": "Bind ID", "ip": "Source IP", "type": "Bind type",
     "Value #A": "Age", "Value #B": "Open acks", "Value #C": "Submit/s", "Value #D": "Deliver/s",
     "Value #E": "PDU in/s (1s)", "Value #F": "PDU out/s (1s)", "Value #G": "Queued", "Value #H": "Routing",
     "Value #I": "MT (bind life)", "Value #J": "Errors (bind life)", "Value #K": "DLR (bind life)",
     "Value #L": "MO (bind life)", "Value #M": "Simulate", "Value #N": "Share of TPS limit %"},
    ["Customer (ESME)", "Server", "Bind ID", "Source IP", "Bind type", "Age", "Submit/s", "Deliver/s", "Share of TPS limit %",
     "PDU in/s (1s)", "PDU out/s (1s)", "Open acks", "Queued", "Routing", "MT (bind life)", "Errors (bind life)",
     "DLR (bind life)", "MO (bind life)", "Simulate"],
    [ov("Bind type", [TYPEMAP, cell("color-text")]), ov("Age", [unit("s")]), ov("Submit/s", MPS2 + [GAUGE, PURPLE]),
     ov("Share of TPS limit %", [unit("percent"), {"id": "decimals", "value": 1}]),
     ov("Deliver/s", MPS2), ov("PDU in/s (1s)", MPS1), ov("PDU out/s (1s)", MPS1),
     ov("MT (bind life)", INT), ov("Errors (bind life)", INT), ov("DLR (bind life)", INT), ov("MO (bind life)", INT),
     ov("Simulate", [{"id": "mappings", "value": [{"type": "value", "options": {
         "0": {"text": "no", "color": "green"}, "1": {"text": "YES", "color": "orange"}}}]}, cell("color-text")])],
    hide_extra=("__name__", "job", "instance"), sort=[{"displayName": "Submit/s", "desc": True}]), 0, 24, 10)
newline(10)
place(table("Connections by source IP", [
    tgt(f'ksmppd_esme_ip_binds{{{C}, ip=~"$ip"}}', ref="A", instant=True, fmt="table"),
    tgt(rate_sum(BSUBM, B, "server, esme, ip", "5m"), ref="B", instant=True, fmt="table"),
    tgt(rate_sum(BDELV, B, "server, esme, ip", "5m"), ref="C", instant=True, fmt="table"),
    tgt(f'sum by (server, esme, ip) (ksmppd_esme_ip_load_pdus_per_second{{{C}, ip=~"$ip", direction="inbound"}})', ref="D", instant=True, fmt="table")],
    {"server": "Server", "esme": "Customer (ESME)", "ip": "Source IP", "Value #A": "Binds", "Value #B": "Submit/s",
     "Value #C": "Deliver/s", "Value #D": "PDU in/s (1s)"},
    ["Customer (ESME)", "Source IP", "Server", "Binds", "Submit/s", "Deliver/s", "PDU in/s (1s)"],
    [ov("Submit/s", MPS2), ov("Deliver/s", MPS2), ov("PDU in/s (1s)", MPS1)],
    hide_extra=("__name__", "job", "instance"), sort=[{"displayName": "Submit/s", "desc": True}]), 0, 12, 9)
place(ts("Submit rate per bind", [tgt(f'{rate_sum(BSUBM, B, "esme, bind_id")} > 0', "{{esme}} #{{bind_id}}")],
         "mps", stack=True), 12, 12, 9)
newline(9)
place(ts("Binds by type", [tgt(f'sum by (type) (ksmppd_esme_binds_by_type{{{C}, type=~"$bind_type"}})', "{{type}}")],
         "short", stack=True, legend_calcs=("min", "max", "lastNotNull")), 0, 12, 8)
place(ts("Bind age (newest bind per customer)", [tgt(f'ksmppd_esme_bind_uptime_min_seconds{{{C}}}', "{{esme}} @ {{server}}")],
         "s", fill=0), 12, 12, 8)
newline(8)

# =========================================================== 6. EXPORTER
row("Exporter health", collapsed=True)
eY = Y[0]
kids = []
for p, x in ((ts("Scrape duration", [tgt(f'ksmppd_scrape_duration_seconds{{{S}}}', "{{server}}")], "s", fill=0), 0),
             (ts("Scrape errors / min", [tgt(f'60 * rate(ksmppd_scrape_errors_total{{{S}}}[{RI}])', "{{server}}")], fill=0), 8),
             (ts("Seconds since last good scrape", [tgt(
                 f'time() - ksmppd_last_scrape_success_timestamp_seconds{{{S}}} and ksmppd_last_scrape_success_timestamp_seconds{{{S}}} > 0',
                 "{{server}}")], "s", fill=0), 16)):
    p.update({"gridPos": {"h": 7, "w": 8, "x": x, "y": eY}, "id": nid(), "datasource": DS})
    kids.append(p)
panels[-1]["panels"] = kids


# =========================================================== table row-merge fix
# Grafana's merge only joins rows whose label sets are identical; raw series carry job/instance (and
# direction/window), aggregated ones do not -> separate rows.  Force the same key labels on every query.
TABLE_KEYS = {"KSMPPD servers": "server", "Peak throughput per server": "server",
              "Peak throughput per server & customer": "server, esme", "Customer overview": "server, esme",
              "TPS per customer": "server, esme",
              "Peak throughput per server, customer & bind (session)": "server, esme, bind_id, ip, type",
              "Bind details": "server, esme, bind_id, ip, type", "Connections by source IP": "server, esme, ip"}
for p in panels:
    if p.get("type") == "table" and p["title"] in TABLE_KEYS:
        for t in p["targets"]:
            t["expr"] = "max by (%s) (%s)" % (TABLE_KEYS[p["title"]], t["expr"])
        ex = p["transformations"][1]["options"]["excludeByName"]
        ex.update({"__name__": True, "job": True, "instance": True, "direction": True, "window": True})

# =========================================================== descriptions (hover help)
DIR = ("\n\nInbound / Submit = submit_sm the customer sends to ksmppd (MT accepted + MT rejected). "
       "Outbound / Deliver = deliver_sm ksmppd delivers to the customer (DLR + MO).")
F = "\n\nFollows the Server and Customer filters."
FS = "\n\nFollows the Server filter."
FB = "\n\nFollows the Server, Customer, Source IP and Bind type filters."
TPSD = ("\n\nTPS model: max-inbound-load = TPS limit of the customer - the same whether 1 or all max-binds "
        "sessions are connected. Achieved TPS = inbound (submit_sm accepted + rejected) + outbound (DLR + MO) per second, "
        "1-minute average. Utilisation = achieved / limit. Customers with limit 0 (unlimited) show no utilisation.")
PEAK = " Peak = highest 1-minute average inside the selected time range; Current = last minute."
DESC = {
 "KSMPPD servers": "One row per ksmppd server: reachability, uptime, customers known since start, customers "
     "connected now, active binds, current submit / deliver / error rate, open acks, queued PDUs, the PDU load "
     "ksmppd itself reports for the last 60 s, and how long the status scrape took." + FS,
 "Peak Inbound (msg/s)": "Highest submit rate of all selected servers combined." + PEAK + DIR + FS,
 "Peak Outbound (msg/s)": "Highest deliver (DLR+MO) rate of all selected servers combined." + PEAK + DIR + FS,
 "Current Inbound (msg/s)": "Submit rate of all selected servers combined right now." + DIR + FS,
 "Current Outbound (msg/s)": "Deliver rate of all selected servers combined right now." + DIR + FS,
 "Peak throughput per server": "Peak and current rates per ksmppd server." + PEAK + DIR + FS,
 "Peak throughput per server & customer": "Peak and current rates per customer per server." + PEAK + DIR + F,
 "Peak throughput per server, customer & bind (session)": "Peak and current rates of every single bind "
     "(SMPP session) - bind id, source IP, bind type and age." + PEAK + DIR + FB,
 "Servers UP": "ksmppd servers whose status page was read successfully." + FS,
 "Servers DOWN": "ksmppd servers whose status page could not be read (down, timeout, wrong password)." + FS,
 "Submit rate (MT)": "submit_sm per second from the selected customers (accepted + rejected)." + DIR + F,
 "Deliver rate (DLR+MO)": "Delivery reports and MO messages per second delivered to the customers." + DIR + F,
 "Error rate": "submit_sm per second that ksmppd rejected (error response to the customer: throttled, "
     "invalid, no route, no credit ...)." + F,
 "Error %": "Rejected submits as % of all submits. Green < 2 %, orange 2-5 %, red > 5 %." + F,
 "Submitted (range)": "All submit_sm (accepted + rejected) in the selected time range." + F,
 "Errors (range)": "Rejected submit_sm in the selected time range." + F,
 "Customers connected": "Customers with at least one bind right now." + F,
 "Customers disconnected": "Known customers with NO bind right now - they cannot send traffic." + F,
 "Active binds": "Total SMPP binds (sessions) open by the selected customers." + F,
 "Bind utilisation": "Active binds as % of the maximum binds allowed. At 100 % new binds are refused." + F,
 "Open acks": "PDUs sent to customers that are not yet acknowledged (in flight). Growing = slow customer." + F,
 "Queued PDUs": "PDUs waiting in the inbound + outbound queues of the binds. Should be close to 0." + F,
 "Pending routing": "Submitted messages waiting for a route decision. Should be 0." + F,
 "DLR ratio": "Delivery reports delivered as % of MT accepted (over the graph interval). Low = operator DLRs "
     "missing or late." + F,
 "TPS limit (sum of customers)": "Sum of max-inbound-load of the selected customers." + TPSD + F,
 "Achieved TPS (in + out)": "Inbound + outbound messages per second of the selected customers (1-minute average)." + TPSD + F,
 "Inbound TPS": "submit_sm per second (accepted + rejected)." + TPSD + F,
 "Outbound TPS": "DLR + MO delivered per second." + TPSD + F,
 "Peak TPS (range)": "Highest 1-minute achieved TPS (in + out) inside the selected time range." + TPSD + F,
 "Highest customer TPS utilisation": "Utilisation of the busiest selected customer. Green < 70 %, orange 70-90 %, "
     "red > 90 % (close to throttling)." + TPSD + F,
 "TPS per customer": "Per customer: TPS limit, sessions connected / allowed, inbound / outbound / achieved TPS now, "
     "peak TPS in range, average TPS per session, utilisation now and at peak, and headroom (limit - achieved)." + TPSD + F,
 "TPS utilisation % per customer (achieved / limit)": "Utilisation per customer over time." + TPSD + F,
 "Achieved TPS vs limit": "Achieved, inbound and outbound TPS against the TPS limit (dashed red) of the selected customers." + TPSD + F,
 "Session share of customer TPS limit % (busiest sessions)": "The 15 busiest sessions: how much of their customer's "
     "TPS limit each single session is using." + TPSD + FB,
 "Messages by kind": "MT accepted, MT rejected, DLR delivered and MO delivered per second." + F,
 "Submit rate per server": "Submit rate per ksmppd server (stacked)." + DIR + FS,
 "Deliver (DLR+MO) rate per server": "Deliveries per ksmppd server (stacked)." + DIR + FS,
 "PDUs processed per server": "ALL PDUs (incl. enquire_link, responses) received from and sent to customers." + FS,
 "ksmppd reported load (last 60 s)": "The PDU/s load ksmppd itself computes over the last 60 seconds." + FS,
 "Submitted messages per interval": "Submitted messages per graph interval per server." + FS,
 "Customer overview": "One row per customer per server.\nStatus = CONNECTED if at least one bind.\n"
     "State for = time in the current state.\nBinds / Max binds / IPs = sessions now, allowed, source IPs.\n"
     "TPS limit = max-inbound-load (whole customer). TPS util % = (inbound + outbound msg/s, 5 min) / TPS limit.\nSubmit/s, Deliver/s = last 5 min.\n"
     "(range) = within the selected time range. Error % = errors / submits.\nOpen acks / Queued = in flight / "
     "waiting.\nLast reconnect = age of the newest bind." + DIR + F,
 "Top 10 customers by MT (range)": "Customers with the most accepted MT in the range." + F,
 "Top 10 customers by errors (range)": "Customers with the most rejected submits in the range." + F,
 "Top 10 error % (range, >100 msgs)": "Worst error %; customers with 100 or fewer submits are hidden." + F,
 "Submit rate per customer": "Submits per second per customer (stacked)." + DIR + F,
 "Deliver (DLR+MO) rate per customer": "Deliveries per second per customer (stacked)." + DIR + F,
 "Error rate per customer": "Rejected submits per second per customer." + F,
 "Error % per customer": "Rejected as % of submitted per customer over time." + F,
 "Achieved TPS per customer vs limit": "Achieved TPS (inbound + outbound) of each customer next to its TPS limit "
     "(max-inbound-load)." + F,
 "DLR ratio per customer (DLR / MT)": "Delivery reports as % of accepted MT per customer." + F,
 "Customer connection state (history)": "Green = CONNECTED, red = DISCONNECTED per customer over time." + F,
 "Binds per customer": "Open binds per customer over time; dips = binds dropped." + F,
 "Binds & drops per customer": "Bars up = new binds, bars down = binds that disappeared. Flapping customers "
     "show many of both." + F + " Also follows the Bind type filter.",
 "Open acks & queued per customer": "In-flight acks, queued PDUs and PDUs pending routing per customer." + F,
 "Transceiver binds (TRX)": "Open TRX binds - submit and receive DLR/MO on the same session." + F,
 "Transmitter binds (TX)": "Open TX binds - submit only." + F,
 "Receiver binds (RX)": "Open RX binds - receive DLR/MO only." + F,
 "Binds (range)": "New binds seen in the selected range (reconnects)." + F,
 "Drops (range)": "Binds that disappeared in the selected range. Orange > 5, red > 50." + F,
 "Simulate-mode binds": "Binds running in ksmppd simulate mode (test traffic, not sent to operators). "
     "Should be 0 in production." + F,
 "Bind details": "Share of TPS limit % = (inbound + outbound msg/s of this session) / customer TPS limit. Every open bind: id, source IP, type, age, current rates (5 min), last-second PDU load, "
     "open acks, queues, routing and counters since the bind connected." + DIR + FB,
 "Connections by source IP": "Binds and rates per customer source IP." + FB,
 "Submit rate per bind": "Submit rate of each bind - shows load balancing across a customer's sessions." + FB,
 "Binds by type": "Open binds by bind type over time." + F,
 "Bind age (newest bind per customer)": "Age of each customer's most recent bind; drops to 0 on reconnect." + F,
 "Scrape duration": "Time the exporter needs to read each status page." + FS,
 "Scrape errors / min": "Failed status page reads per minute." + FS,
 "Seconds since last good scrape": "Grows while a server's status page is unreachable." + FS,
}


def apply(ps):
    for p in ps:
        if p.get("title") in DESC:
            p["description"] = DESC[p["title"]]
        apply(p.get("panels", []))


apply(panels)
missing = [p["title"] for p in panels if p["type"] != "row" and not p.get("description")]
assert not missing, missing


def qvar(name, label, query, hide=0):
    return {"name": name, "label": label, "type": "query", "datasource": DS, "definition": query,
            "query": {"query": query, "refId": name, "qryType": 1}, "refresh": 2, "multi": True, "includeAll": True,
            "allValue": ".*", "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "sort": 7,
            "hide": hide, "regex": "", "options": []}


dash = {
    "annotations": {"list": [
        {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True, "hide": True,
         "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"},
        {"datasource": DS, "enable": True, "iconColor": "red", "name": "ksmppd restarts",
         "expr": f'ksmppd_uptime_seconds{{{S}}} < 300', "titleFormat": "ksmppd restarted", "textFormat": "{{server}}", "step": "60s"},
        {"datasource": DS, "enable": True, "iconColor": "orange", "name": "Server down",
         "expr": f'ksmppd_up{{{S}}} == 0', "titleFormat": "Status page unreachable", "textFormat": "{{server}}", "step": "60s"}]},
    "description": "KSMPPD - all servers, per server, per customer (ESME) and per bind",
    "editable": True, "graphTooltip": 1, "links": [], "panels": panels, "refresh": "30s", "schemaVersion": 39,
    "tags": ["smpp", "ksmppd", "sms"],
    "templating": {"list": [
        {"name": "datasource", "label": "Data source", "type": "datasource", "query": "prometheus", "current": {},
         "hide": 0, "refresh": 1, "regex": "", "options": []},
        qvar("server", "KSMPPD server", "label_values(ksmppd_up, server)"),
        qvar("esme", "Customer (ESME)", 'label_values(ksmppd_esme_binds{server=~"$server"}, esme)'),
        qvar("ip", "Source IP", 'label_values(ksmppd_esme_ip_binds{server=~"$server", esme=~"$esme"}, ip)'),
        {"name": "bind_type", "label": "Bind type", "type": "custom", "multi": True, "includeAll": True,
         "allValue": ".*", "query": "Transceiver (TRX) : trx,Transmitter (TX) : tx,Receiver (RX) : rx",
         "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "hide": 0, "options": [],
         "description": "TRX = send + receive on one bind, TX = send only, RX = receive DLR/MO only"}]},
    "time": {"from": "now-6h", "to": "now"},
    "timepicker": {"refresh_intervals": ["15s", "30s", "1m", "5m", "15m", "1h"]},
    "timezone": "browser", "title": "KSMPPD - SMPP Monitoring", "uid": "ksmppd-monitoring", "version": 1}
json.dump(dash, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboards", "ksmppd_dashboard.json"), "w", newline="\n"), indent=2)
print("panels:", _id[0])
