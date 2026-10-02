#!/usr/bin/env python3
"""
smpp_exporter.py - Centralised Prometheus exporter for Kannel / Kannel-HA smppbox.

Scrapes many smppbox  http://<host>:<admin-port>/status.xml?password=...  pages
from a single place and exposes everything on one /metrics endpoint.

Every metric carries a `server` label (the target name you give in the config),
customer metrics additionally carry `esme` (system-id) and `smsc_id`.

Direction conventions (smppbox point of view):
  received  = PDUs received FROM the ESME/customer  (submit_sm  -> MT traffic)
  sent      = PDUs sent TO the ESME/customer        (deliver_sm -> DLRs / MO)

Requirements:  pip3 install prometheus_client pyyaml     (pyyaml only for YAML config)

Examples:
  ./smpp_exporter.py --config /opt/smpp-exporter/smppbox/config.yml
  ./smpp_exporter.py --port 9877 --interval 15 \
        --target smppbox-a=http://192.0.2.10:14000/status.xml?password=CHANGE_ME \
        --target smppbox-b=http://192.0.2.11:14000/status.xml?password=CHANGE_ME
  ./smpp_exporter.py --config config.yml --once     # scrape once, print metrics, exit
Reload targets without restart:  kill -HUP <pid>
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
    from prometheus_client import REGISTRY, generate_latest, start_http_server
    from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
    import prometheus_client
except ImportError:  # pragma: no cover
    sys.exit("prometheus_client missing:  pip3 install prometheus_client")

__version__ = "1.2.0"
log = logging.getLogger("smpp_exporter")

LOAD_WINDOWS = ("1m", "5m", "overall")   # Kannel load triplet order: 60s, 300s, since start
SESSION_TYPES = ("trans", "recv", "trcv")
NONE = "none"                             # placeholder for empty labels (e.g. empty smsc-id)

# --------------------------------------------------------------------------- helpers

def _txt(el, path, default=""):
    if el is None:
        return default
    n = el.find(path)
    if n is None or n.text is None:
        return default
    return n.text.strip()


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _grab(pattern, text, cast=float, default=0.0):
    m = re.search(pattern, text or "")
    if not m:
        return default
    try:
        return cast(m.group(1))
    except ValueError:
        return default


def parse_duration(text):
    """'118d 10h 25m 40s' -> seconds"""
    mult = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return float(sum(int(n) * mult[u] for n, u in re.findall(r"(\d+)\s*([dhms])\b", text or "")))


def parse_cpu(text):
    """Kannel CPU time 'MMMM:SS.ss' or 'H:MM:SS.ss' -> seconds"""
    total = 0.0
    try:
        for i, part in enumerate(reversed(text.split(":"))):
            total += float(part) * (60 ** i)
    except (ValueError, AttributeError):
        return 0.0
    return total


def parse_size(text):
    """'321.64M' -> bytes"""
    m = re.match(r"\s*([\d.]+)\s*([KMGT]?)", text or "", re.I)
    if not m:
        return 0.0
    mult = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}
    return float(m.group(1)) * mult[m.group(2).upper()]


def parse_triplet(text):
    nums = [_f(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text or "")]
    return (nums + [0.0, 0.0, 0.0])[:3]


def mask_url(url):
    p = urlsplit(url)
    q = [(k, "***" if k.lower() in ("password", "pass", "pwd", "passwd") else v)
         for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q, safe="*"), p.fragment))


# --------------------------------------------------------------------------- parsing

def parse_status_xml(raw):
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    start = text.find("<?xml")
    if start < 0:
        start = text.find("<gateway")
    if start < 0:
        raise ValueError("no <gateway> document in response")
    text = text[start:]
    end = text.rfind("</gateway>")
    if end >= 0:
        text = text[: end + len("</gateway>")]
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    root = ET.fromstring(text.encode("utf-8"))
    if root.tag != "gateway":
        raise ValueError("root element is <%s>, expected <gateway>" % root.tag)

    d = {}
    ver = _txt(root, "version")
    d["info"] = {
        "product": (ver.split("smppbox")[0].strip() or "Kannel") if "smppbox" in ver else "Kannel",
        "version": _grab(r"smppbox/(\S+)", ver, str, "") or _grab(r"version `([^']+)'", ver, str, "unknown"),
        "build": _grab(r"Build `([^']+)'", ver, str, ""),
        "hostname": _grab(r"Hostname\s+([^,\s]+)", ver, str, ""),
        "host_ip": _grab(r"Hostname\s+[^,]+,\s*IP\s+([0-9A-Fa-f:.]+?)\.?\s*$", ver.replace("\r", ""), str, "")
                   or _grab(r"IP\s+([\d.]+\d)", ver, str, ""),
        "os_release": _grab(r"release\s+([^,]+),", ver, str, ""),
        "mysql_client": _grab(r"using MySQL\s+([\d.]+\d)", ver, str, ""),
    }
    # host_ip regex above is line based; make it robust
    m = re.search(r"Hostname\s+[^,]+,\s*IP\s+([0-9A-Fa-f:.]*[0-9A-Fa-f])", ver)
    d["info"]["host_ip"] = m.group(1) if m else ""

    st = _txt(root, "status")
    d["state"] = st.split(",")[0].strip() or "unknown"
    d["uptime"] = parse_duration(_grab(r"uptime\s+((?:\d+[dhms]\s*)+)", st, str, ""))
    d["cpu"] = parse_cpu(_grab(r"CPU time\s+([\d:.]+)", st, str, "0"))
    d["resp_mode"] = _grab(r"resp mode\s+([^,]+)", st, str, "").strip()

    # bearerbox / esme side totals
    d["sides"] = {}
    for side in ("bearerbox", "esme"):
        el = root.find(side)
        d["sides"][side] = {
            "status": _txt(el, "status"),
            "received": _f(_txt(el, "received/total")),
            "received_queued": _f(_txt(el, "received/queued")),
            "sent": _f(_txt(el, "sent/total")),
            "sent_queued": _f(_txt(el, "sent/queued")),
            "inbound": parse_triplet(_txt(el, "inbound")),
            "outbound": parse_triplet(_txt(el, "outbound")),
        }

    d["store_size"] = _f(_txt(root, "store/size"))
    d["store_status"] = _f(_txt(root, "store/status"))
    d["memory"] = parse_size(_txt(root, "memory/total"))

    # configured logins (customers)
    d["logins"] = []
    for sm in root.findall("logins/smsc"):
        s = _txt(sm, "status")
        parts = [p.strip() for p in s.split(",") if p.strip()]
        sessions = {t: (0.0 if cur == "-" else _f(cur), _f(mx))
                    for t, cur, mx in re.findall(r"\b(trans|recv|trcv)\s+(-|\d+)/(\d+)", s)}
        flags = [p for p in parts[1:] if not re.match(r"(trans|recv|trcv)\s|resp mode", p)]
        d["logins"].append({
            "esme": _txt(sm, "id") or NONE,
            "smsc_id": _txt(sm, "smsc-id") or NONE,
            "shortcode": _txt(sm, "shortcode"),
            "keyword": _txt(sm, "keyword"),
            "state": parts[0] if parts else "unknown",
            "online": 1.0 if parts and parts[0].lower().startswith("online") else 0.0,
            "sessions": sessions,
            "resp_mode": _grab(r"resp mode\s+([^,]+)", s, str, "").strip(),
            "flags": ",".join(flags),
        })
    d["logins_count"] = _f(_txt(root, "logins/count"), len(d["logins"]))

    # live sessions
    d["sessions"] = []
    for se in root.findall("sessions/session"):
        s = _txt(se, "status")
        d["sessions"].append({
            "esme": _txt(se, "esme") or NONE,
            "ip": _txt(se, "ip") or NONE,
            "port": _txt(se, "port") or "0",
            "type": _txt(se, "type") or "unknown",
            "state": (s.split()[0] if s else "unknown"),
            "online": _grab(r"online\s+(\d+)s", s),
            "rcvd": _grab(r"rcvd\s+(\d+)", s),
            "sent": _grab(r"sent\s+(\d+)", s),
            "failed": _grab(r"failed\s+(\d+)", s),
            "resp": _grab(r"resp\s+(\d+)\s+PDUs", s),
            "open_acks": _grab(r"open\s+(\d+)\s+acks", s),
            "in_rate": _grab(r"\bin\s+([\d.]+)\s*msg/s", s),
            "out_rate": _grab(r"\bout\s+([\d.]+)\s*msg/s", s),
        })
    d["sessions_count"] = _f(_txt(root, "sessions/count"), len(d["sessions"]))

    # plugins
    d["chains"] = []
    for ch in root.findall("plugins/trigger-chain"):
        chain = _txt(ch, "trigger-type") or "unknown"
        plugins = []
        for pos, pl in enumerate(ch.findall("plugin"), 1):
            s = _txt(pl, "status")
            idle = re.search(r"(\d+)/(\d+)\s+idle database connections", s)
            plugins.append({
                "position": str(pos),
                "plugin": _txt(pl, "id") or "unknown",
                "args": _txt(pl, "args"),
                "state": _txt(pl, "state") or "unknown",
                "async": _txt(pl, "async") or "no",
                "db_idle": float(idle.group(1)) if idle else None,
                "db_max": float(idle.group(2)) if idle else None,
                "sql_queue": _grab(r"(\d+)\s+SQL statements in queue", s, float, None),
            })
        d["chains"].append({"chain": chain, "count": _f(_txt(ch, "count"), len(plugins)), "plugins": plugins})
    return d


# --------------------------------------------------------------------------- counters that survive reconnects

class SessionAccumulator:
    """
    Session counters in status.xml reset every time a customer reconnects, so a plain
    sum would go *down* and Prometheus would see fake counter resets / spikes.
    We track each session (esme, ip, port, type, start-time) and add only the deltas
    into monotonic per-customer and per-customer-IP totals.
    """
    FIELDS = ("rcvd", "sent", "failed", "resp")

    def __init__(self, tolerance, retention, interval=15.0, max_rate=20000.0):
        self.tolerance = tolerance
        self.retention = retention
        self.fresh_window = interval * 2 + 30   # a session younger than this is "just connected"
        self.gone_ttl = 3600                    # remember vanished sessions for 1 h
        self.max_step = max_rate * (interval * 4 + 60)  # max believable msgs between two scrapes
        self.gone = {}
        self.primed = False     # first scrape only sets a baseline for connect/disconnect events
        self.sessions = {}
        self.esme = {}          # esme -> [rcvd, sent, failed, resp]
        self.esme_ip = {}       # (esme, ip) -> [...]
        self.esme_type = {}     # (esme, bind type) -> [...]
        self.events = {}        # (esme, bind type) -> [connects, disconnects]
        self.state = {}         # esme -> [connected 0/1, since_ts]
        self.last_connected = {}  # esme -> last time it had >=1 session
        self.seen_esme = {}
        self.seen_ip = {}

    def _ev(self, esme, btype, idx):
        self.events.setdefault((esme, btype), [0.0, 0.0])[idx] += 1

    def update(self, sessions, now, known_esmes=()):
        current = {}
        # sessions that vanished recently are remembered, so a session that is missing from one
        # status page (glitch / partial page) and then comes back continues from where it was
        # instead of being counted again from zero (which re-added its whole history).
        for k in [k for k, v in self.gone.items() if now - v["gone_at"] > self.gone_ttl]:
            self.gone.pop(k, None)
        for s in sessions:
            key = (s["esme"], s["ip"], s["port"], s["type"])
            start = now - s["online"]
            vals = [s[f] for f in self.FIELDS]
            prev = self.sessions.get(key)
            returning = False
            if prev is None and key in self.gone:
                prev = self.gone.pop(key)
                returning = True
            same = prev is not None and abs(prev["start"] - start) <= self.tolerance
            if same and all(v >= p for v, p in zip(vals, prev["vals"])):
                delta = [v - p for v, p in zip(vals, prev["vals"])]      # normal case: only new traffic
            elif same:
                delta = [0.0] * len(self.FIELDS)   # same session but counters went down: re-baseline, never jump
            else:
                # A new session.  Only a session that really started since our last look may bring its
                # counts in; an old session we simply never saw before (exporter start, or it was missing
                # for a while) only sets a baseline.  This guarantees no billion-size jumps.
                fresh = self.primed and s["online"] <= self.fresh_window
                delta = vals if fresh else [0.0] * len(self.FIELDS)
                if self.primed and not returning:
                    self._ev(s["esme"], s["type"], 0)          # connect (bind)
                    if prev:
                        self._ev(s["esme"], s["type"], 1)      # same ip:port re-bound = old one dropped
            # hard safety net: never accept an impossible jump for one interval
            delta = [dv if dv <= self.max_step else 0.0 for dv in delta]
            for bucket, k in ((self.esme, s["esme"]), (self.esme_ip, (s["esme"], s["ip"])),
                              (self.esme_type, (s["esme"], s["type"]))):
                acc = bucket.setdefault(k, [0.0] * len(self.FIELDS))
                for i, dv in enumerate(delta):
                    acc[i] += dv
            self.seen_esme[s["esme"]] = now
            self.seen_ip[(s["esme"], s["ip"])] = now
            current[key] = {"start": start, "vals": vals}
        if self.primed:
            for key, v in self.sessions.items():
                if key not in current:
                    self._ev(key[0], key[3], 1)                # disconnect (unbind / drop)
                    self.gone[key] = {"start": v["start"], "vals": v["vals"], "gone_at": now}
        self.sessions = current
        for e in known_esmes:  # configured customers keep their series alive
            self.esme.setdefault(e, [0.0] * len(self.FIELDS))
            self.seen_esme[e] = now
        # connection state per customer
        connected = {k[0] for k in current}
        for e in set(self.esme) | connected:
            st = 1.0 if e in connected else 0.0
            if e in connected:
                self.last_connected[e] = now
            cur = self.state.get(e)
            if cur is None or cur[0] != st:
                self.state[e] = [st, now]
        # retention / cleanup
        for k, ts in list(self.seen_ip.items()):
            if now - ts > self.retention:
                self.seen_ip.pop(k, None)
                self.esme_ip.pop(k, None)
        for e, ts in list(self.seen_esme.items()):
            if now - ts > self.retention:
                self.seen_esme.pop(e, None)
                self.esme.pop(e, None)
                self.state.pop(e, None)
                self.last_connected.pop(e, None)
                for bucket in (self.esme_type, self.events):
                    for k in [k for k in bucket if k[0] == e]:
                        bucket.pop(k, None)
        self.primed = True


# --------------------------------------------------------------------------- scraping

class Target:
    def __init__(self, name, url, timeout=10, insecure=False, username=None, password=None):
        self.name, self.url, self.timeout = name, url, timeout
        self.insecure, self.username, self.password = insecure, username, password

    def fetch(self):
        req = urllib.request.Request(self.url, headers={"User-Agent": "smpp_exporter/" + __version__})
        if self.username:
            tok = base64.b64encode(("%s:%s" % (self.username, self.password or "")).encode()).decode()
            req.add_header("Authorization", "Basic " + tok)
        ctx = ssl._create_unverified_context() if self.insecure else None
        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
            return r.read()


class TargetState:
    def __init__(self, tolerance, retention, interval=15.0, max_rate=20000.0):
        self.up = 0.0
        self.data = None
        self.duration = 0.0
        self.errors = 0.0
        self.scrapes = 0.0
        self.last_success = 0.0
        self.last_error = ""
        self.acc = SessionAccumulator(tolerance, retention, interval, max_rate)


class SmppExporter:
    def __init__(self, opts):
        self.opts = opts
        self.lock = threading.Lock()
        self.targets = []
        self.states = {}
        self.pool = ThreadPoolExecutor(max_workers=opts.workers)

    def set_targets(self, targets):
        with self.lock:
            self.targets = targets
            names = {t.name for t in targets}
            for n in list(self.states):
                if n not in names:
                    del self.states[n]
            tol = max(30.0, self.opts.interval * 2)
            for t in targets:
                self.states.setdefault(t.name, TargetState(tol, self.opts.series_retention,
                                                           self.opts.interval, self.opts.max_rate))
        log.info("targets: %s", ", ".join("%s=%s" % (t.name, mask_url(t.url)) for t in targets))

    def _scrape(self, t):
        t0 = time.time()
        try:
            data = parse_status_xml(t.fetch())
            return t, data, time.time() - t0, None
        except Exception as e:  # noqa
            return t, None, time.time() - t0, "%s: %s" % (type(e).__name__, e)

    def scrape_all(self):
        with self.lock:
            targets = list(self.targets)
        for t, data, dur, err in self.pool.map(self._scrape, targets):
            now = time.time()
            with self.lock:
                st = self.states.get(t.name)
                if st is None:
                    continue
                st.scrapes += 1
                st.duration = dur
                if err:
                    st.up, st.data, st.last_error = 0.0, None, err
                    st.errors += 1
                    log.warning("scrape %s failed (%.2fs): %s", t.name, dur, err)
                else:
                    st.acc.update(data["sessions"], now, [l["esme"] for l in data["logins"]])
                    st.up, st.data, st.last_success, st.last_error = 1.0, data, now, ""
                    log.debug("scrape %s ok (%.2fs, %d sessions)", t.name, dur, len(data["sessions"]))

    def loop(self, stop):
        while not stop.is_set():
            t0 = time.time()
            try:
                self.scrape_all()
            except Exception:  # noqa
                log.exception("scrape cycle crashed")
            stop.wait(max(1.0, self.opts.interval - (time.time() - t0)))

    # ------------------------------------------------------------------ collector
    def describe(self):
        return []

    def collect(self):
        with self.lock:
            snap = []
            for name, st in self.states.items():
                snap.append((name, st.up, st.data, st.duration, st.errors, st.scrapes, st.last_success,
                             {k: list(v) for k, v in st.acc.esme.items()},
                             {k: list(v) for k, v in st.acc.esme_ip.items()},
                             {k: list(v) for k, v in st.acc.esme_type.items()},
                             {k: list(v) for k, v in st.acc.events.items()},
                             {k: list(v) for k, v in st.acc.state.items()},
                             dict(st.acc.last_connected)))
        o = self.opts
        S = ["server"]
        C = ["server", "esme", "smsc_id"]
        CI = C + ["ip"]
        G, K = GaugeMetricFamily, CounterMetricFamily

        m = {}
        def g(name, doc, labels): m[name] = G(name, doc, labels=labels)
        def c(name, doc, labels): m[name] = K(name, doc, labels=labels)

        # exporter / scrape health
        g("smppbox_up", "1 if the last scrape of the smppbox status page succeeded", S)
        g("smppbox_scrape_duration_seconds", "Duration of the last status page scrape", S)
        c("smppbox_scrape_errors", "Failed status page scrapes since exporter start", S)
        c("smppbox_scrapes", "Status page scrapes since exporter start", S)
        g("smppbox_last_scrape_success_timestamp_seconds", "Unix time of the last successful scrape", S)
        # gateway
        g("smppbox_gateway_info", "smppbox build / host information (value always 1)",
          S + ["product", "version", "build", "hostname", "host_ip", "os_release", "mysql_client", "state", "resp_mode"])
        g("smppbox_gateway_running", "1 if smppbox reports state 'running'", S)
        g("smppbox_uptime_seconds", "smppbox uptime", S)
        c("smppbox_cpu_seconds", "CPU time consumed by smppbox", S)
        g("smppbox_memory_bytes", "Memory used by smppbox", S)
        g("smppbox_bearerbox_connected", "1 if smppbox is connected to bearerbox", S)
        c("smppbox_messages", "Messages counted by smppbox. side=bearerbox|esme, direction=received|sent",
          S + ["side", "direction"])
        g("smppbox_queued_messages", "Messages currently queued", S + ["side", "direction"])
        g("smppbox_load_messages_per_second", "Gateway reported load (msg/s) for window 1m/5m/overall",
          S + ["side", "direction", "window"])
        g("smppbox_store_size_messages", "Messages in the smppbox store", S)
        g("smppbox_store_status", "Store status code as reported", S)
        g("smppbox_logins_configured", "Configured ESME logins", S)
        g("smppbox_logins_online", "Configured ESME logins currently online", S)
        g("smppbox_sessions_active", "Active SMPP sessions", S)
        g("smppbox_sessions_active_by_type", "Active SMPP sessions by bind type", S + ["type"])
        # logins (customers)
        g("smppbox_login_info", "Configured login (value always 1)",
          C + ["shortcode", "keyword", "state", "resp_mode", "flags"])
        g("smppbox_login_online", "1 if the customer login is online", C)
        g("smppbox_login_sessions", "Bound sessions per bind type as reported on the login", C + ["type"])
        g("smppbox_login_sessions_max", "Maximum allowed sessions per bind type", C + ["type"])
        # customer aggregates from sessions
        g("smppbox_esme_active_sessions", "Active sessions per customer by bind type", C + ["type"])
        c("smppbox_esme_messages_received", "Messages received from the customer (submit_sm)", C)
        c("smppbox_esme_messages_sent", "Messages sent to the customer (deliver_sm: DLR/MO)", C)
        c("smppbox_esme_messages_failed", "Failed messages for the customer", C)
        c("smppbox_esme_resp_pdus", "Response PDUs for the customer", C)
        g("smppbox_esme_open_acks", "Open (unacknowledged) PDUs for the customer", C)
        g("smppbox_esme_reported_in_rate", "smppbox reported inbound msg/s from the customer", C)
        g("smppbox_esme_reported_out_rate", "smppbox reported outbound msg/s to the customer", C)
        g("smppbox_esme_connected_ips", "Distinct source IPs the customer is bound from", C)
        g("smppbox_esme_session_uptime_max_seconds", "Age of the oldest session of the customer", C)
        g("smppbox_esme_session_uptime_min_seconds", "Age of the newest session (low = recent reconnect)", C)
        # customer per source IP
        g("smppbox_esme_ip_sessions", "Active sessions per customer source IP", CI)
        c("smppbox_esme_ip_messages_received", "Messages received from the customer IP", CI)
        c("smppbox_esme_ip_messages_sent", "Messages sent to the customer IP", CI)
        c("smppbox_esme_ip_messages_failed", "Failed messages for the customer IP", CI)
        g("smppbox_esme_ip_reported_in_rate", "smppbox reported inbound msg/s from the customer IP", CI)
        g("smppbox_esme_ip_reported_out_rate", "smppbox reported outbound msg/s to the customer IP", CI)
        # customer connection state
        g("smppbox_esme_connected", "1 = customer has at least one bound session (connected), 0 = disconnected", C)
        g("smppbox_esme_state_since_timestamp_seconds",
          "Unix time the customer entered its current connected/disconnected state (as seen by the exporter)", C)
        g("smppbox_esme_last_connected_timestamp_seconds",
          "Unix time the customer was last seen with at least one session", C)
        # customer per bind type (trans = transmitter, recv = receiver, trcv = transceiver)
        CT = C + ["type"]
        c("smppbox_esme_type_messages_received", "Messages received from the customer per bind type", CT)
        c("smppbox_esme_type_messages_sent", "Messages sent to the customer per bind type", CT)
        c("smppbox_esme_type_messages_failed", "Failed messages per customer bind type", CT)
        c("smppbox_esme_type_resp_pdus", "Response PDUs per customer bind type", CT)
        g("smppbox_esme_type_open_acks", "Open (unacknowledged) PDUs per customer bind type", CT)
        g("smppbox_esme_type_reported_in_rate", "smppbox reported inbound msg/s per customer bind type", CT)
        g("smppbox_esme_type_reported_out_rate", "smppbox reported outbound msg/s per customer bind type", CT)
        g("smppbox_esme_type_session_uptime_max_seconds", "Age of oldest session per customer bind type", CT)
        g("smppbox_esme_type_session_uptime_min_seconds", "Age of newest session per customer bind type", CT)
        c("smppbox_esme_type_connects", "New binds (session connects) seen per customer bind type", CT)
        c("smppbox_esme_type_disconnects", "Sessions that disappeared (unbind/drop) per customer bind type", CT)
        if o.per_session:
            SL = CI + ["port", "type"]
            for n, doc in (("online_seconds", "Session age"), ("received", "Messages received on session"),
                           ("sent", "Messages sent on session"), ("failed", "Failed on session"),
                           ("open_acks", "Open acks on session"), ("in_rate", "Reported inbound msg/s"),
                           ("out_rate", "Reported outbound msg/s")):
                g("smppbox_session_" + n, doc + " (per-session, high cardinality)", SL)
        # plugins
        P = S + ["chain", "position", "plugin"]
        g("smppbox_plugin_info", "Loaded plugin (value always 1)",
          P + ["state", "async"] + (["args"] if o.plugin_args else []))
        g("smppbox_plugin_active", "1 if the plugin state is 'active'", P)
        g("smppbox_plugin_chain_plugins", "Number of plugins in a trigger chain", S + ["chain"])
        g("smppbox_plugin_db_connections_idle", "Idle database connections of a DB plugin", P)
        g("smppbox_plugin_db_connections_max", "Size of the DB connection pool of a DB plugin", P)
        g("smppbox_plugin_sql_queue", "SQL statements waiting in queue", P)
        # exporter
        g("smppbox_exporter_targets", "Configured scrape targets", [])
        g("smppbox_exporter_scrape_interval_seconds", "Configured scrape interval", [])
        g("smppbox_exporter_build_info", "Exporter version", ["version"])

        m["smppbox_exporter_targets"].add_metric([], len(snap))
        m["smppbox_exporter_scrape_interval_seconds"].add_metric([], o.interval)
        m["smppbox_exporter_build_info"].add_metric([__version__], 1)

        for name, up, d, dur, errs, scrapes, last_ok, acc_esme, acc_ip, acc_type, events, state, last_conn in snap:
            s = [name]
            m["smppbox_up"].add_metric(s, up)
            m["smppbox_scrape_duration_seconds"].add_metric(s, dur)
            m["smppbox_scrape_errors"].add_metric(s, errs)
            m["smppbox_scrapes"].add_metric(s, scrapes)
            m["smppbox_last_scrape_success_timestamp_seconds"].add_metric(s, last_ok)
            if not d:
                continue
            i = d["info"]
            m["smppbox_gateway_info"].add_metric(s + [i["product"], i["version"], i["build"], i["hostname"],
                                                      i["host_ip"], i["os_release"], i["mysql_client"],
                                                      d["state"], d["resp_mode"]], 1)
            m["smppbox_gateway_running"].add_metric(s, 1.0 if d["state"] == "running" else 0.0)
            m["smppbox_uptime_seconds"].add_metric(s, d["uptime"])
            m["smppbox_cpu_seconds"].add_metric(s, d["cpu"])
            m["smppbox_memory_bytes"].add_metric(s, d["memory"])
            bb = d["sides"]["bearerbox"]["status"].lower()
            m["smppbox_bearerbox_connected"].add_metric(s, 1.0 if bb.startswith("connected") else 0.0)
            for side, v in d["sides"].items():
                m["smppbox_messages"].add_metric(s + [side, "received"], v["received"])
                m["smppbox_messages"].add_metric(s + [side, "sent"], v["sent"])
                m["smppbox_queued_messages"].add_metric(s + [side, "received"], v["received_queued"])
                m["smppbox_queued_messages"].add_metric(s + [side, "sent"], v["sent_queued"])
                for direction in ("inbound", "outbound"):
                    for w, val in zip(LOAD_WINDOWS, v[direction]):
                        m["smppbox_load_messages_per_second"].add_metric(s + [side, direction, w], val)
            m["smppbox_store_size_messages"].add_metric(s, d["store_size"])
            m["smppbox_store_status"].add_metric(s, d["store_status"])
            m["smppbox_logins_configured"].add_metric(s, d["logins_count"])
            m["smppbox_logins_online"].add_metric(s, sum(l["online"] for l in d["logins"]))
            m["smppbox_sessions_active"].add_metric(s, d["sessions_count"])
            for t in SESSION_TYPES:
                m["smppbox_sessions_active_by_type"].add_metric(
                    s + [t], sum(1 for x in d["sessions"] if x["type"] == t))

            smsc_of = {}
            for l in d["logins"]:
                smsc_of.setdefault(l["esme"], l["smsc_id"])
                cl = [name, l["esme"], l["smsc_id"]]
                m["smppbox_login_info"].add_metric(cl + [l["shortcode"], l["keyword"], l["state"],
                                                         l["resp_mode"], l["flags"]], 1)
                m["smppbox_login_online"].add_metric(cl, l["online"])
                for t in SESSION_TYPES:
                    cur, mx = l["sessions"].get(t, (0.0, 0.0))
                    m["smppbox_login_sessions"].add_metric(cl + [t], cur)
                    m["smppbox_login_sessions_max"].add_metric(cl + [t], mx)

            by_esme, by_ip = {}, {}
            for x in d["sessions"]:
                by_esme.setdefault(x["esme"], []).append(x)
                by_ip.setdefault((x["esme"], x["ip"]), []).append(x)
            for e in set(smsc_of) | set(by_esme):
                cl = [name, e, smsc_of.get(e, NONE)]
                ss = by_esme.get(e, [])
                for t in SESSION_TYPES:
                    m["smppbox_esme_active_sessions"].add_metric(cl + [t], sum(1 for x in ss if x["type"] == t))
                m["smppbox_esme_open_acks"].add_metric(cl, sum(x["open_acks"] for x in ss))
                m["smppbox_esme_reported_in_rate"].add_metric(cl, sum(x["in_rate"] for x in ss))
                m["smppbox_esme_reported_out_rate"].add_metric(cl, sum(x["out_rate"] for x in ss))
                m["smppbox_esme_connected_ips"].add_metric(cl, len({x["ip"] for x in ss}))
                if ss:
                    m["smppbox_esme_session_uptime_max_seconds"].add_metric(cl, max(x["online"] for x in ss))
                    m["smppbox_esme_session_uptime_min_seconds"].add_metric(cl, min(x["online"] for x in ss))
            for e, v in acc_esme.items():
                cl = [name, e, smsc_of.get(e, NONE)]
                m["smppbox_esme_messages_received"].add_metric(cl, v[0])
                m["smppbox_esme_messages_sent"].add_metric(cl, v[1])
                m["smppbox_esme_messages_failed"].add_metric(cl, v[2])
                m["smppbox_esme_resp_pdus"].add_metric(cl, v[3])
            for (e, ip), v in acc_ip.items():
                cl = [name, e, smsc_of.get(e, NONE), ip]
                ss = by_ip.get((e, ip), [])
                m["smppbox_esme_ip_messages_received"].add_metric(cl, v[0])
                m["smppbox_esme_ip_messages_sent"].add_metric(cl, v[1])
                m["smppbox_esme_ip_messages_failed"].add_metric(cl, v[2])
                m["smppbox_esme_ip_sessions"].add_metric(cl, len(ss))
                m["smppbox_esme_ip_reported_in_rate"].add_metric(cl, sum(x["in_rate"] for x in ss))
                m["smppbox_esme_ip_reported_out_rate"].add_metric(cl, sum(x["out_rate"] for x in ss))
            # connection state
            for e, (st, since) in state.items():
                cl = [name, e, smsc_of.get(e, NONE)]
                m["smppbox_esme_connected"].add_metric(cl, st)
                m["smppbox_esme_state_since_timestamp_seconds"].add_metric(cl, since)
                if e in last_conn:
                    m["smppbox_esme_last_connected_timestamp_seconds"].add_metric(cl, last_conn[e])
            # per bind type
            by_type = {}
            for x in d["sessions"]:
                by_type.setdefault((x["esme"], x["type"]), []).append(x)
            keys = {(e, t) for e in (set(acc_esme) | set(by_esme)) for t in SESSION_TYPES}
            keys |= set(by_type) | set(acc_type) | set(events)
            for e, t in keys:
                cl = [name, e, smsc_of.get(e, NONE), t]
                ss = by_type.get((e, t), [])
                v = acc_type.get((e, t), [0.0, 0.0, 0.0, 0.0])
                ev = events.get((e, t), [0.0, 0.0])
                m["smppbox_esme_type_messages_received"].add_metric(cl, v[0])
                m["smppbox_esme_type_messages_sent"].add_metric(cl, v[1])
                m["smppbox_esme_type_messages_failed"].add_metric(cl, v[2])
                m["smppbox_esme_type_resp_pdus"].add_metric(cl, v[3])
                m["smppbox_esme_type_open_acks"].add_metric(cl, sum(x["open_acks"] for x in ss))
                m["smppbox_esme_type_reported_in_rate"].add_metric(cl, sum(x["in_rate"] for x in ss))
                m["smppbox_esme_type_reported_out_rate"].add_metric(cl, sum(x["out_rate"] for x in ss))
                m["smppbox_esme_type_connects"].add_metric(cl, ev[0])
                m["smppbox_esme_type_disconnects"].add_metric(cl, ev[1])
                if ss:
                    m["smppbox_esme_type_session_uptime_max_seconds"].add_metric(cl, max(x["online"] for x in ss))
                    m["smppbox_esme_type_session_uptime_min_seconds"].add_metric(cl, min(x["online"] for x in ss))
            if o.per_session:
                for x in d["sessions"]:
                    sl = [name, x["esme"], smsc_of.get(x["esme"], NONE), x["ip"], x["port"], x["type"]]
                    for n, key in (("online_seconds", "online"), ("received", "rcvd"), ("sent", "sent"),
                                   ("failed", "failed"), ("open_acks", "open_acks"),
                                   ("in_rate", "in_rate"), ("out_rate", "out_rate")):
                        m["smppbox_session_" + n].add_metric(sl, x[key])

            for ch in d["chains"]:
                m["smppbox_plugin_chain_plugins"].add_metric(s + [ch["chain"]], ch["count"])
                for p in ch["plugins"]:
                    pl = s + [ch["chain"], p["position"], p["plugin"]]
                    extra = [p["args"][:250]] if o.plugin_args else []
                    m["smppbox_plugin_info"].add_metric(pl + [p["state"], p["async"]] + extra, 1)
                    m["smppbox_plugin_active"].add_metric(pl, 1.0 if p["state"] == "active" else 0.0)
                    if p["db_idle"] is not None:
                        m["smppbox_plugin_db_connections_idle"].add_metric(pl, p["db_idle"])
                        m["smppbox_plugin_db_connections_max"].add_metric(pl, p["db_max"])
                    if p["sql_queue"] is not None:
                        m["smppbox_plugin_sql_queue"].add_metric(pl, p["sql_queue"])

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
            sys.exit("pyyaml missing for YAML config:  pip3 install pyyaml   (or use a .json config)")
        return yaml.safe_load(raw) or {}
    return json.loads(raw)


def build_targets(cfg, cli_targets, default_timeout):
    out, names = [], set()
    for t in cfg.get("targets", []) or []:
        out.append(Target(str(t["name"]), t["url"], float(t.get("timeout", default_timeout)),
                          bool(t.get("insecure", False)), t.get("username"), t.get("password")))
    for spec in cli_targets or []:
        if "=" not in spec:
            sys.exit("--target must be NAME=URL, got: %s" % spec)
        n, u = spec.split("=", 1)
        out.append(Target(n.strip(), u.strip(), default_timeout))
    for t in out:
        if t.name in names:
            sys.exit("duplicate target name: %s" % t.name)
        names.add(t.name)
    return out


def parse_args():
    ap = argparse.ArgumentParser(description="Kannel smppbox multi-target Prometheus exporter",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("-c", "--config", help="YAML/JSON config file (CLI flags override it)")
    ap.add_argument("-t", "--target", action="append", help="NAME=URL (repeatable)")
    ap.add_argument("--listen-address", default=None, help="bind address [default 0.0.0.0]")
    ap.add_argument("-p", "--port", type=int, default=None, help="metrics port [default 9877]")
    ap.add_argument("-i", "--interval", type=float, default=None, help="scrape cycle seconds [default 15]")
    ap.add_argument("--timeout", type=float, default=None, help="per-target HTTP timeout [default 10]")
    ap.add_argument("--workers", type=int, default=None, help="parallel scrapes [default 16]")
    ap.add_argument("--per-session", action="store_true", default=None,
                    help="also export per-session (ip+port) metrics - high cardinality")
    ap.add_argument("--no-plugin-args", action="store_true", default=None,
                    help="do not expose plugin args (URLs) as a label")
    ap.add_argument("--series-retention", type=float, default=None,
                    help="seconds to keep counters of customers/IPs that vanished [default 86400]")
    ap.add_argument("--disable-process-metrics", action="store_true", default=None,
                    help="drop python process/gc metrics from /metrics")
    ap.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING/ERROR [default INFO]")
    ap.add_argument("--once", action="store_true", help="scrape once, print metrics, exit")
    ap.add_argument("--version", action="version", version=__version__)
    return ap.parse_args()


def resolve_options(a):
    cfg = load_config(a.config) if a.config else {}

    def pick(cli, key, default):
        return cli if cli is not None else cfg.get(key, default)

    class O: pass
    o = O()
    o.config = a.config
    o.cli_targets = a.target
    o.listen_address = pick(a.listen_address, "listen_address", "0.0.0.0")
    o.port = int(pick(a.port, "port", 9877))
    o.interval = float(pick(a.interval, "scrape_interval", 15))
    o.timeout = float(pick(a.timeout, "timeout", 10))
    o.workers = int(pick(a.workers, "max_workers", 16))
    o.per_session = bool(pick(a.per_session, "per_session_metrics", False))
    o.plugin_args = not bool(pick(a.no_plugin_args, "hide_plugin_args", False))
    o.series_retention = float(pick(a.series_retention, "series_retention", 86400))
    o.disable_process = bool(pick(a.disable_process_metrics, "disable_process_metrics", False))
    o.log_level = str(pick(a.log_level, "log_level", "INFO")).upper()
    o.max_rate = float(cfg.get("max_customer_rate", 20000))  # msg/s; bigger jumps are treated as glitches
    o.cfg = cfg
    return o


def main():
    a = parse_args()
    o = resolve_options(a)
    logging.basicConfig(level=getattr(logging, o.log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s")
    targets = build_targets(o.cfg, o.cli_targets, o.timeout)
    if not targets:
        sys.exit("no targets: use --config or --target NAME=URL")

    if o.disable_process:
        for c in (prometheus_client.PROCESS_COLLECTOR, prometheus_client.PLATFORM_COLLECTOR,
                  prometheus_client.GC_COLLECTOR):
            try:
                REGISTRY.unregister(c)
            except Exception:  # noqa
                pass

    exp = SmppExporter(o)
    exp.set_targets(targets)
    REGISTRY.register(exp)

    if a.once:
        exp.scrape_all()
        sys.stdout.write(generate_latest(REGISTRY).decode())
        return

    stop = threading.Event()

    def reload(*_):
        if not o.config:
            log.info("SIGHUP ignored (no --config)")
            return
        try:
            o.cfg = load_config(o.config)
            exp.set_targets(build_targets(o.cfg, o.cli_targets, o.timeout))
        except (Exception, SystemExit) as e:  # noqa
            log.error("reload failed, keeping old targets: %s", e)

    signal.signal(signal.SIGHUP, reload)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    start_http_server(o.port, addr=o.listen_address)
    log.info("smpp_exporter %s listening on %s:%d, interval %.0fs, %d targets",
             __version__, o.listen_address, o.port, o.interval, len(targets))
    th = threading.Thread(target=exp.loop, args=(stop,), daemon=True)
    th.start()
    while not stop.is_set():
        stop.wait(1)
    log.info("stopping")


if __name__ == "__main__":
    main()
