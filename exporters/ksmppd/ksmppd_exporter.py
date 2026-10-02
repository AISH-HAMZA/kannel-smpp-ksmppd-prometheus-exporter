#!/usr/bin/env python3
"""
ksmppd_exporter.py - Centralised Prometheus exporter for KSMPPD (https://github.com/kneodev/ksmppd)

Scrapes the ksmppd HTTP admin command  /esme-status(.xml)?password=...  of many servers from one place
and exposes everything on a single /metrics endpoint (every metric has a `server` label).

What ksmppd reports (verified against the ksmppd source, smpp_esme.c / smpp_queues.c):
  * mt      = submit_sm / data_sm ACCEPTED from the customer      (counter)
  * errors  = submit_sm / data_sm REJECTED  (non-ROK response)     (counter)
  * mo      = MO deliver_sm successfully delivered to the customer (counter)
  * dlr     = DLR deliver_sm successfully delivered to the customer(counter)
  * inbound/outbound processed = ALL PDUs received from / sent to ESMEs (incl. enquire_link, resp ...)
  * load a/b/c on summary + customer level = average since start / last 1 second / last 60 seconds
  * load on bind level                     = last 1 second
  * max-inbound-load = configured throughput limit of the customer (msg/s, 0 = unlimited)
  * bind-type 1 = TX (transmitter), 2 = RX (receiver), 3 = TRX (transceiver)
  * customer counters live as long as ksmppd runs (they survive bind drops), bind counters live per bind.
Both the XML (esme-status.xml) and the plain text (esme-status) page are supported.

Requirements:  pip3 install prometheus_client pyyaml
Examples:
  ./ksmppd_exporter.py --config /opt/smpp-exporter/ksmppd/config.yml
  ./ksmppd_exporter.py -p 9878 -i 15 -t ksmppd-a=http://192.0.2.20:14000/esme-status.xml?password=xxx
  ./ksmppd_exporter.py -c config.yml --once        # scrape once, print metrics, exit
Reload targets without restart:  kill -HUP <pid>   (systemctl reload ksmppd_exporter)
"""

import argparse
import base64
import json
import logging
import re
import signal
import ssl
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import prometheus_client
    from prometheus_client import REGISTRY, generate_latest, start_http_server
    from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
except ImportError:  # pragma: no cover
    sys.exit("prometheus_client missing:  pip3 install prometheus_client")

__version__ = "1.2.0"
log = logging.getLogger("ksmppd_exporter")

WINDOWS = ("since_start", "1s", "1m")          # order of the a/b/c load triplet in ksmppd
BIND_TYPES = {"1": "tx", "2": "rx", "3": "trx"}
ALL_TYPES = ("trx", "tx", "rx")


# --------------------------------------------------------------------------- helpers
def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _t(el, tag, d=""):
    if el is None:
        return d
    n = el.find(tag)
    return n.text.strip() if n is not None and n.text is not None else d


def triplet(s):
    n = [_f(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s or "")]
    return (n + [0.0, 0.0, 0.0])[:3]


def duration(s):
    m = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return float(sum(int(a) * m[b] for a, b in re.findall(r"(\d+)\s*([dhms])\b", s or "")))


def btype(v):
    return BIND_TYPES.get(str(v).strip(), "type_%s" % str(v).strip())


def mask_url(url):
    p = urlsplit(url)
    q = [(k, "***" if k.lower() in ("password", "pass", "pwd") else v) for k, v in parse_qsl(p.query, True)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q, safe="*"), p.fragment))


def uptime_url(url):
    """esme-status(.xml)?password=x  ->  uptime.xml?password=x"""
    p = urlsplit(url)
    path = p.path[: p.path.rfind("/") + 1] + "uptime.xml"
    return urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


# --------------------------------------------------------------------------- parsers
def _empty():
    return {"summary": {"unique": 0.0, "in_processed": 0.0, "out_processed": 0.0,
                        "in_load": [0.0] * 3, "out_load": [0.0] * 3}, "esmes": []}


def parse_xml(text):
    s = text[text.find("<esmes"):]
    s = s[: s.rfind("</esmes>") + len("</esmes>")]
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    root = ET.fromstring(s.encode("utf-8", "replace"))
    d = _empty()
    sm = root.find("summary")
    d["summary"] = {"unique": _f(_t(sm, "unique")),
                    "in_processed": _f(_t(sm, "inbound-processed")),
                    "out_processed": _f(_t(sm, "outbound-processed")),
                    "in_load": triplet(_t(sm, "inbound-load")),
                    "out_load": triplet(_t(sm, "outbound-load"))}
    for e in root.findall("esme"):
        esme = {"id": _t(e, "system-id") or "unknown",
                "bind_count": _f(_t(e, "bind-count")), "max_binds": _f(_t(e, "max-binds")),
                "in_load": triplet(_t(e, "inbound-load")), "out_load": triplet(_t(e, "outbound-load")),
                "limit": _f(_t(e, "max-inbound-load")),
                "mt": _f(_t(e, "mt")), "mo": _f(_t(e, "mo")), "dlr": _f(_t(e, "dlr")),
                "errors": _f(_t(e, "errors")), "binds": []}
        for b in e.findall("bind"):
            esme["binds"].append({
                "id": _t(b, "bind-id") or "0", "ip": _t(b, "ip") or "unknown",
                "uptime": _f(_t(b, "uptime")), "type": btype(_t(b, "bind-type")),
                "open_acks": _f(_t(b, "open-acks")), "simulate": 1.0 if _t(b, "simulate") == "yes" else 0.0,
                "in_load": _f(_t(b, "inbound-load")), "in_queued": _f(_t(b, "inbound-queued")),
                "in_processed": _f(_t(b, "inbound-processed")), "routing": _f(_t(b, "inbound-routing")),
                "out_load": _f(_t(b, "outbound-load")), "out_queued": _f(_t(b, "outbound-queued")),
                "out_processed": _f(_t(b, "outbound-processed")),
                "mt": _f(_t(b, "mt")), "mo": _f(_t(b, "mo")), "dlr": _f(_t(b, "dlr")),
                "errors": _f(_t(b, "errors"))})
        d["esmes"].append(esme)
    return d


RE_SUM_UNIQUE = re.compile(r"Unique known ESME's:\s*(\d+)")
RE_SUM_IN = re.compile(r"Total inbound processed:\s*(\d+)\s*load:\s*([\d./]+)")
RE_SUM_OUT = re.compile(r"Total outbound processed:\s*(\d+)\s*load:\s*([\d./]+)")
RE_ESME = re.compile(r"^(\S.*?) - binds:(\d+)/(\d+), total inbound load:\(([\d./]+)\)/([\d.]+)/sec, "
                     r"outbound load:\(([\d./]+)\)/sec, mt/mo/dlr/errors:\((\d+)/(\d+)/(\d+)/(\d+)\)")
RE_BIND = re.compile(r"^-- id:(\d+) ip:(\S*) uptime:([^,]*), type:(\d+), open-acks:(\d+), simulate: (\w+), "
                     r"inbound \(load/queued/processed/routing\):([\d.]+)/(\d+)/(\d+)/(\d+), "
                     r"outbound \(load/queued/processed\):([\d.]+)/(\d+)/(\d+), mt/mo/dlr/errors:(\d+)/(\d+)/(\d+)/(\d+)")


def parse_text(text):
    d = _empty()
    m = RE_SUM_UNIQUE.search(text)
    if not m:
        raise ValueError("not a ksmppd esme-status page (no 'Unique known ESME's')")
    d["summary"]["unique"] = _f(m.group(1))
    for rx, p in ((RE_SUM_IN, "in"), (RE_SUM_OUT, "out")):
        m = rx.search(text)
        if m:
            d["summary"][p + "_processed"] = _f(m.group(1))
            d["summary"][p + "_load"] = triplet(m.group(2))
    cur = None
    for line in text.splitlines():
        line = line.rstrip()
        m = RE_ESME.match(line)
        if m:
            g = m.groups()
            cur = {"id": g[0], "bind_count": _f(g[1]), "max_binds": _f(g[2]), "in_load": triplet(g[3]),
                   "limit": _f(g[4]), "out_load": triplet(g[5]), "mt": _f(g[6]), "mo": _f(g[7]),
                   "dlr": _f(g[8]), "errors": _f(g[9]), "binds": []}
            d["esmes"].append(cur)
            continue
        m = RE_BIND.match(line)
        if m and cur is not None:
            g = m.groups()
            cur["binds"].append({"id": g[0], "ip": g[1] or "unknown", "uptime": duration(g[2]), "type": btype(g[3]),
                                 "open_acks": _f(g[4]), "simulate": 1.0 if g[5] == "yes" else 0.0,
                                 "in_load": _f(g[6]), "in_queued": _f(g[7]), "in_processed": _f(g[8]),
                                 "routing": _f(g[9]), "out_load": _f(g[10]), "out_queued": _f(g[11]),
                                 "out_processed": _f(g[12]), "mt": _f(g[13]), "mo": _f(g[14]),
                                 "dlr": _f(g[15]), "errors": _f(g[16])})
    return d


def parse_status(raw):
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    if "<esmes" in text:
        return parse_xml(text)
    if text.strip() == "Denied":
        raise ValueError("ksmppd answered 'Denied' - wrong password")
    return parse_text(text)


# --------------------------------------------------------------------------- state tracking
class Tracker:
    """Connected/disconnected state per customer and bind connect / disconnect events."""

    def __init__(self, retention):
        self.retention = retention
        self.primed = False
        self.binds = {}        # bind key -> (esme, type)
        self.events = {}       # (esme, type) -> [connects, disconnects]
        self.state = {}        # esme -> [connected, since]
        self.last_conn = {}    # esme -> ts
        self.seen = {}         # esme -> ts

    def update(self, data, now):
        current = {}
        for e in data["esmes"]:
            self.seen[e["id"]] = now
            for b in e["binds"]:
                current[(e["id"], b["id"])] = (e["id"], b["type"])
        if self.primed:
            for k, v in current.items():
                if k not in self.binds:
                    self.events.setdefault(v, [0.0, 0.0])[0] += 1
            for k, v in self.binds.items():
                if k not in current:
                    self.events.setdefault(v, [0.0, 0.0])[1] += 1
        self.binds = current
        for e in data["esmes"]:
            conn = 1.0 if e["binds"] or e["bind_count"] > 0 else 0.0
            if conn:
                self.last_conn[e["id"]] = now
            if e["id"] not in self.state or self.state[e["id"]][0] != conn:
                self.state[e["id"]] = [conn, now]
        for e, ts in list(self.seen.items()):
            if now - ts > self.retention:
                for dct in (self.seen, self.state, self.last_conn):
                    dct.pop(e, None)
                for k in [k for k in self.events if k[0] == e]:
                    self.events.pop(k, None)
        self.primed = True


# --------------------------------------------------------------------------- scraping
class Target:
    def __init__(self, name, url, timeout=10, insecure=False, username=None, password=None, uptime=True):
        self.name, self.url, self.timeout = name, url, timeout
        self.insecure, self.username, self.password, self.uptime = insecure, username, password, uptime

    def get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "ksmppd_exporter/" + __version__})
        if self.username:
            tok = base64.b64encode(("%s:%s" % (self.username, self.password or "")).encode()).decode()
            req.add_header("Authorization", "Basic " + tok)
        ctx = ssl._create_unverified_context() if self.insecure else None
        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
            return r.read()


class State:
    def __init__(self, retention):
        self.up, self.data, self.duration, self.errors, self.scrapes = 0.0, None, 0.0, 0.0, 0.0
        self.last_ok, self.uptime = 0.0, None
        self.tracker = Tracker(retention)


class KsmppdExporter:
    def __init__(self, o):
        self.o = o
        self.lock = threading.Lock()
        self.targets, self.states = [], {}
        self.pool = ThreadPoolExecutor(max_workers=o.workers)

    def set_targets(self, targets):
        with self.lock:
            self.targets = targets
            names = {t.name for t in targets}
            for n in [n for n in self.states if n not in names]:
                del self.states[n]
            for t in targets:
                self.states.setdefault(t.name, State(self.o.series_retention))
        log.info("targets: %s", ", ".join("%s=%s" % (t.name, mask_url(t.url)) for t in targets))

    def _scrape(self, t):
        t0 = time.time()
        try:
            data = parse_status(t.get(t.url))
            up = None
            if t.uptime and self.o.fetch_uptime:
                try:
                    m = re.search(r"<uptime>(\d+)</uptime>", t.get(uptime_url(t.url)).decode("utf-8", "replace"))
                    up = float(m.group(1)) if m else None
                except Exception:  # noqa - optional
                    up = None
            return t, data, up, time.time() - t0, None
        except Exception as e:  # noqa
            return t, None, None, time.time() - t0, "%s: %s" % (type(e).__name__, e)

    def scrape_all(self):
        with self.lock:
            targets = list(self.targets)
        for t, data, up, dur, err in self.pool.map(self._scrape, targets):
            now = time.time()
            with self.lock:
                st = self.states.get(t.name)
                if st is None:
                    continue
                st.scrapes += 1
                st.duration = dur
                if err:
                    st.up, st.data, st.uptime = 0.0, None, None
                    st.errors += 1
                    log.warning("scrape %s failed (%.2fs): %s", t.name, dur, err)
                else:
                    st.tracker.update(data, now)
                    st.up, st.data, st.uptime, st.last_ok = 1.0, data, up, now

    def loop(self, stop):
        while not stop.is_set():
            t0 = time.time()
            try:
                self.scrape_all()
            except Exception:  # noqa
                log.exception("scrape cycle crashed")
            stop.wait(max(1.0, self.o.interval - (time.time() - t0)))

    def describe(self):
        return []

    # ------------------------------------------------------------------ metrics
    def collect(self):
        with self.lock:
            snap = [(n, s.up, s.data, s.duration, s.errors, s.scrapes, s.last_ok, s.uptime,
                     {k: list(v) for k, v in s.tracker.events.items()},
                     {k: list(v) for k, v in s.tracker.state.items()}, dict(s.tracker.last_conn))
                    for n, s in self.states.items()]
        S, E = ["server"], ["server", "esme"]
        ET_ = E + ["type"]
        EI = E + ["ip"]
        B = E + ["bind_id", "ip", "type"]
        m = {}

        def g(n, doc, lbl): m[n] = GaugeMetricFamily(n, doc, labels=lbl)

        def c(n, doc, lbl): m[n] = CounterMetricFamily(n, doc, labels=lbl)

        g("ksmppd_up", "1 if the last scrape of the ksmppd status page succeeded", S)
        g("ksmppd_scrape_duration_seconds", "Duration of the last status page scrape", S)
        c("ksmppd_scrape_errors", "Failed status page scrapes since exporter start", S)
        c("ksmppd_scrapes", "Status page scrapes since exporter start", S)
        g("ksmppd_last_scrape_success_timestamp_seconds", "Unix time of the last successful scrape", S)
        g("ksmppd_uptime_seconds", "ksmppd uptime (from /uptime.xml)", S)
        g("ksmppd_known_esmes", "Unique ESMEs (customers) ksmppd knows since start", S)
        g("ksmppd_esmes_connected", "Customers with at least one bind", S)
        g("ksmppd_binds_active", "Active binds (sessions) on the server", S)
        g("ksmppd_binds_active_by_type", "Active binds by bind type (trx/tx/rx)", S + ["type"])
        c("ksmppd_pdus", "All PDUs processed. direction=inbound (from ESMEs) | outbound (to ESMEs)", S + ["direction"])
        g("ksmppd_load_pdus_per_second", "Server PDU load reported by ksmppd. window=since_start|1s|1m",
          S + ["direction", "window"])
        c("ksmppd_messages", "Messages summed over all customers. kind=mt|mo|dlr|errors", S + ["kind"])
        # customer
        g("ksmppd_esme_binds", "Active binds of the customer", E)
        g("ksmppd_esme_max_binds", "Maximum binds allowed for the customer", E)
        g("ksmppd_esme_binds_by_type", "Active binds of the customer by bind type", ET_)
        g("ksmppd_esme_throughput_limit", "max-inbound-load: TPS limit of the customer (all sessions together), 0 = unlimited", E)
        g("ksmppd_esme_load_pdus_per_second", "Customer PDU load reported by ksmppd. window=since_start|1s|1m",
          E + ["direction", "window"])
        c("ksmppd_esme_mt", "submit_sm accepted from the customer (MT)", E)
        c("ksmppd_esme_mo", "MO messages delivered to the customer", E)
        c("ksmppd_esme_dlr", "Delivery reports delivered to the customer", E)
        c("ksmppd_esme_errors", "submit_sm rejected (error response sent to the customer)", E)
        g("ksmppd_esme_connected", "1 = customer has at least one bind, 0 = disconnected", E)
        g("ksmppd_esme_state_since_timestamp_seconds", "Unix time the customer entered its current state", E)
        g("ksmppd_esme_last_connected_timestamp_seconds", "Unix time the customer last had a bind", E)
        g("ksmppd_esme_open_acks", "Unacknowledged PDUs over all binds of the customer", E)
        g("ksmppd_esme_queued", "Queued PDUs over all binds. direction=inbound|outbound", E + ["direction"])
        g("ksmppd_esme_pending_routing", "PDUs waiting for routing over all binds", E)
        g("ksmppd_esme_connected_ips", "Distinct source IPs the customer is bound from", E)
        g("ksmppd_esme_simulate_binds", "Binds running in simulate mode", E)
        g("ksmppd_esme_bind_uptime_max_seconds", "Age of the oldest bind", E)
        g("ksmppd_esme_bind_uptime_min_seconds", "Age of the newest bind (small = recent reconnect)", E)
        c("ksmppd_esme_bind_connects", "New binds seen by the exporter", ET_)
        c("ksmppd_esme_bind_disconnects", "Binds that disappeared (unbind / drop) seen by the exporter", ET_)
        # per ip
        g("ksmppd_esme_ip_binds", "Active binds per customer source IP", EI)
        g("ksmppd_esme_ip_load_pdus_per_second", "Last-second PDU load per customer source IP", EI + ["direction"])
        if self.o.per_bind:
            g("ksmppd_bind_uptime_seconds", "Bind age", B)
            g("ksmppd_bind_open_acks", "Unacknowledged PDUs on the bind", B)
            g("ksmppd_bind_simulate", "1 if the bind runs in simulate mode", B)
            g("ksmppd_bind_load_pdus_per_second", "Last-second PDU load of the bind", B + ["direction"])
            g("ksmppd_bind_queued", "Queued PDUs on the bind", B + ["direction"])
            g("ksmppd_bind_pending_routing", "PDUs of the bind waiting for routing", B)
            c("ksmppd_bind_pdus", "PDUs processed on the bind", B + ["direction"])
            c("ksmppd_bind_mt", "submit_sm accepted on the bind", B)
            c("ksmppd_bind_mo", "MO delivered on the bind", B)
            c("ksmppd_bind_dlr", "DLR delivered on the bind", B)
            c("ksmppd_bind_errors", "submit_sm rejected on the bind", B)
        g("ksmppd_exporter_build_info", "Exporter version", ["version"])
        g("ksmppd_exporter_targets", "Configured targets", [])
        g("ksmppd_exporter_scrape_interval_seconds", "Configured scrape interval", [])
        m["ksmppd_exporter_build_info"].add_metric([__version__], 1)
        m["ksmppd_exporter_targets"].add_metric([], len(snap))
        m["ksmppd_exporter_scrape_interval_seconds"].add_metric([], self.o.interval)

        for name, up, d, dur, errs, scrapes, last_ok, uptime, events, state, last_conn in snap:
            s = [name]
            m["ksmppd_up"].add_metric(s, up)
            m["ksmppd_scrape_duration_seconds"].add_metric(s, dur)
            m["ksmppd_scrape_errors"].add_metric(s, errs)
            m["ksmppd_scrapes"].add_metric(s, scrapes)
            m["ksmppd_last_scrape_success_timestamp_seconds"].add_metric(s, last_ok)
            if not d:
                continue
            if uptime is not None:
                m["ksmppd_uptime_seconds"].add_metric(s, uptime)
            sm = d["summary"]
            m["ksmppd_known_esmes"].add_metric(s, sm["unique"])
            m["ksmppd_pdus"].add_metric(s + ["inbound"], sm["in_processed"])
            m["ksmppd_pdus"].add_metric(s + ["outbound"], sm["out_processed"])
            for w, a, b in zip(WINDOWS, sm["in_load"], sm["out_load"]):
                m["ksmppd_load_pdus_per_second"].add_metric(s + ["inbound", w], a)
                m["ksmppd_load_pdus_per_second"].add_metric(s + ["outbound", w], b)
            allb = [b for e in d["esmes"] for b in e["binds"]]
            m["ksmppd_binds_active"].add_metric(s, len(allb))
            for t in ALL_TYPES:
                m["ksmppd_binds_active_by_type"].add_metric(s + [t], sum(1 for b in allb if b["type"] == t))
            m["ksmppd_esmes_connected"].add_metric(s, sum(1 for e in d["esmes"] if e["binds"] or e["bind_count"]))
            for k in ("mt", "mo", "dlr", "errors"):
                m["ksmppd_messages"].add_metric(s + [k], sum(e[k] for e in d["esmes"]))

            for e in d["esmes"]:
                el = [name, e["id"]]
                bs = e["binds"]
                m["ksmppd_esme_binds"].add_metric(el, e["bind_count"])
                m["ksmppd_esme_max_binds"].add_metric(el, e["max_binds"])
                m["ksmppd_esme_throughput_limit"].add_metric(el, e["limit"])
                for w, a, b in zip(WINDOWS, e["in_load"], e["out_load"]):
                    m["ksmppd_esme_load_pdus_per_second"].add_metric(el + ["inbound", w], a)
                    m["ksmppd_esme_load_pdus_per_second"].add_metric(el + ["outbound", w], b)
                for k in ("mt", "mo", "dlr", "errors"):
                    m["ksmppd_esme_" + k].add_metric(el, e[k])
                types = set(ALL_TYPES) | {b["type"] for b in bs}
                for t in types:
                    m["ksmppd_esme_binds_by_type"].add_metric(el + [t], sum(1 for b in bs if b["type"] == t))
                    ev = events.get((e["id"], t), [0.0, 0.0])
                    m["ksmppd_esme_bind_connects"].add_metric(el + [t], ev[0])
                    m["ksmppd_esme_bind_disconnects"].add_metric(el + [t], ev[1])
                st = state.get(e["id"])
                if st:
                    m["ksmppd_esme_connected"].add_metric(el, st[0])
                    m["ksmppd_esme_state_since_timestamp_seconds"].add_metric(el, st[1])
                if e["id"] in last_conn:
                    m["ksmppd_esme_last_connected_timestamp_seconds"].add_metric(el, last_conn[e["id"]])
                m["ksmppd_esme_open_acks"].add_metric(el, sum(b["open_acks"] for b in bs))
                m["ksmppd_esme_queued"].add_metric(el + ["inbound"], sum(b["in_queued"] for b in bs))
                m["ksmppd_esme_queued"].add_metric(el + ["outbound"], sum(b["out_queued"] for b in bs))
                m["ksmppd_esme_pending_routing"].add_metric(el, sum(b["routing"] for b in bs))
                m["ksmppd_esme_connected_ips"].add_metric(el, len({b["ip"] for b in bs}))
                m["ksmppd_esme_simulate_binds"].add_metric(el, sum(b["simulate"] for b in bs))
                if bs:
                    m["ksmppd_esme_bind_uptime_max_seconds"].add_metric(el, max(b["uptime"] for b in bs))
                    m["ksmppd_esme_bind_uptime_min_seconds"].add_metric(el, min(b["uptime"] for b in bs))
                ips = {}
                for b in bs:
                    ips.setdefault(b["ip"], []).append(b)
                for ip, ib in ips.items():
                    m["ksmppd_esme_ip_binds"].add_metric(el + [ip], len(ib))
                    m["ksmppd_esme_ip_load_pdus_per_second"].add_metric(el + [ip, "inbound"], sum(b["in_load"] for b in ib))
                    m["ksmppd_esme_ip_load_pdus_per_second"].add_metric(el + [ip, "outbound"], sum(b["out_load"] for b in ib))
                if self.o.per_bind:
                    for b in bs:
                        bl = el + [b["id"], b["ip"], b["type"]]
                        m["ksmppd_bind_uptime_seconds"].add_metric(bl, b["uptime"])
                        m["ksmppd_bind_open_acks"].add_metric(bl, b["open_acks"])
                        m["ksmppd_bind_simulate"].add_metric(bl, b["simulate"])
                        m["ksmppd_bind_load_pdus_per_second"].add_metric(bl + ["inbound"], b["in_load"])
                        m["ksmppd_bind_load_pdus_per_second"].add_metric(bl + ["outbound"], b["out_load"])
                        m["ksmppd_bind_queued"].add_metric(bl + ["inbound"], b["in_queued"])
                        m["ksmppd_bind_queued"].add_metric(bl + ["outbound"], b["out_queued"])
                        m["ksmppd_bind_pending_routing"].add_metric(bl, b["routing"])
                        m["ksmppd_bind_pdus"].add_metric(bl + ["inbound"], b["in_processed"])
                        m["ksmppd_bind_pdus"].add_metric(bl + ["outbound"], b["out_processed"])
                        for k in ("mt", "mo", "dlr", "errors"):
                            m["ksmppd_bind_" + k].add_metric(bl, b[k])
        for fam in m.values():
            yield fam


# --------------------------------------------------------------------------- config
def load_config(path):
    with open(path) as fh:
        raw = fh.read()
    if path.endswith((".yml", ".yaml")):
        try:
            import yaml
        except ImportError:
            sys.exit("pyyaml missing:  pip3 install pyyaml   (or use a .json config)")
        return yaml.safe_load(raw) or {}
    return json.loads(raw)


def build_targets(cfg, cli, timeout):
    out = []
    for t in cfg.get("targets", []) or []:
        out.append(Target(str(t["name"]), t["url"], float(t.get("timeout", timeout)), bool(t.get("insecure", False)),
                          t.get("username"), t.get("password"), bool(t.get("uptime", True))))
    for spec in cli or []:
        if "=" not in spec:
            sys.exit("--target must be NAME=URL, got: %s" % spec)
        n, u = spec.split("=", 1)
        out.append(Target(n.strip(), u.strip(), timeout))
    names = [t.name for t in out]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        sys.exit("duplicate target names: %s" % ", ".join(sorted(dup)))
    return out


def options():
    ap = argparse.ArgumentParser(description="KSMPPD multi-target Prometheus exporter",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("-c", "--config", help="YAML/JSON config (CLI flags override it)")
    ap.add_argument("-t", "--target", action="append", help="NAME=URL (repeatable)")
    ap.add_argument("--listen-address", default=None, help="bind address [0.0.0.0]")
    ap.add_argument("-p", "--port", type=int, default=None, help="metrics port [9878]")
    ap.add_argument("-i", "--interval", type=float, default=None, help="scrape cycle seconds [15]")
    ap.add_argument("--timeout", type=float, default=None, help="per-target HTTP timeout [10]")
    ap.add_argument("--workers", type=int, default=None, help="parallel scrapes [16]")
    ap.add_argument("--no-per-bind", action="store_true", default=None, help="disable per-bind metrics")
    ap.add_argument("--no-uptime", action="store_true", default=None, help="do not call /uptime.xml")
    ap.add_argument("--series-retention", type=float, default=None, help="forget vanished customers after s [86400]")
    ap.add_argument("--disable-process-metrics", action="store_true", default=None, help="drop python process metrics")
    ap.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING/ERROR [INFO]")
    ap.add_argument("--once", action="store_true", help="scrape once, print metrics, exit")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args()
    cfg = load_config(a.config) if a.config else {}

    def pick(v, k, d):
        return v if v is not None else cfg.get(k, d)

    class O: pass
    o = O()
    o.a, o.cfg = a, cfg
    o.listen = pick(a.listen_address, "listen_address", "0.0.0.0")
    o.port = int(pick(a.port, "port", 9878))
    o.interval = float(pick(a.interval, "scrape_interval", 15))
    o.timeout = float(pick(a.timeout, "timeout", 10))
    o.workers = int(pick(a.workers, "max_workers", 16))
    o.per_bind = not bool(a.no_per_bind) and bool(cfg.get("per_bind_metrics", True))
    o.fetch_uptime = not bool(a.no_uptime) and bool(cfg.get("fetch_uptime", True))
    o.series_retention = float(pick(a.series_retention, "series_retention", 86400))
    o.disable_process = bool(pick(a.disable_process_metrics, "disable_process_metrics", False))
    o.log_level = str(pick(a.log_level, "log_level", "INFO")).upper()
    return o


def main():
    o = options()
    logging.basicConfig(level=getattr(logging, o.log_level, logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    targets = build_targets(o.cfg, o.a.target, o.timeout)
    if not targets:
        sys.exit("no targets: use --config or --target NAME=URL")
    if o.disable_process:
        for col in (prometheus_client.PROCESS_COLLECTOR, prometheus_client.PLATFORM_COLLECTOR,
                    prometheus_client.GC_COLLECTOR):
            try:
                REGISTRY.unregister(col)
            except Exception:  # noqa
                pass
    exp = KsmppdExporter(o)
    exp.set_targets(targets)
    REGISTRY.register(exp)
    if o.a.once:
        exp.scrape_all()
        sys.stdout.write(generate_latest(REGISTRY).decode())
        return
    stop = threading.Event()

    def reload(*_):
        if not o.a.config:
            return log.info("SIGHUP ignored (no --config)")
        try:
            o.cfg = load_config(o.a.config)
            exp.set_targets(build_targets(o.cfg, o.a.target, o.timeout))
        except (Exception, SystemExit) as e:  # noqa
            log.error("reload failed, keeping old targets: %s", e)

    signal.signal(signal.SIGHUP, reload)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    start_http_server(o.port, addr=o.listen)
    log.info("ksmppd_exporter %s on %s:%d, interval %.0fs, %d targets", __version__, o.listen, o.port,
             o.interval, len(targets))
    threading.Thread(target=exp.loop, args=(stop,), daemon=True).start()
    while not stop.is_set():
        stop.wait(1)


if __name__ == "__main__":
    main()
