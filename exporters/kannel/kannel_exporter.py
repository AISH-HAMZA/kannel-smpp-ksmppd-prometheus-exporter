#!/usr/bin/env python3
"""
kannel_exporter.py - Centralised Prometheus exporter for Kannel bearerbox (vanilla 1.4.x / SVN builds and Kannel-HA).

Scrapes the bearerbox admin page  http://<host>:<admin-port>/status.xml?password=<status-password>
of many servers from one place and exposes everything on a single /metrics endpoint (label `server`).

Field meanings (verified against the Kannel 1.4.5 source: gw/bearerbox.c, gw/bb_smscconn.c, gw/bb_boxc.c):
  gateway  sms received = MO messages received from all SMSCs      sms sent = MT messages sent to all SMSCs
           dlr received = delivery reports received from SMSCs     dlr queued = DLRs waiting in dlr-storage
           storesize    = messages in the store (-1 = store disabled)
  smsc     sms sent = MT sent on this link   sms received = MO from this link   failed = MT that failed
           queued = MT waiting for this link  dlr received = DLRs from this link
           status: online <s> | connecting | re-connecting | disconnected | dead
  box      smsbox / wapbox (and ksmppd/smppbox that connect as smsbox) with their queue
  load a,b,c = messages/s over the last 60 s, 300 s and since start (bearerbox + SMSC level)
Kannel-HA builds add: sms <ha-route>, SMSC <queue> type, and per-box ip/port/open-acks/failed/ack-buffer/
per-box sms+dlr counters and loads - all exported when present.

Requirements:  pip3 install prometheus_client pyyaml
Examples:
  ./kannel_exporter.py --config /opt/smpp-exporter/kannel/config.yml
  ./kannel_exporter.py -p 9879 -t kannel-a=http://192.0.2.30:12000/status.xml?password=CHANGE_ME
  ./kannel_exporter.py -c config.yml --once        # scrape once, print metrics, exit
Reload targets without restart:  kill -HUP <pid>   (systemctl reload kannel_exporter)
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

__version__ = "1.1.0"
log = logging.getLogger("kannel_exporter")

WINDOWS = ("1m", "5m", "overall")
SMSC_STATES = {"dead": 0, "disconnected": 1, "connecting": 2, "re-connecting": 3, "online": 4}
GW_STATES = ("running", "suspended", "isolated", "full", "shutting down")


# --------------------------------------------------------------------------- helpers
def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _t(el, path, d=""):
    if el is None:
        return d
    n = el.find(path)
    return n.text.strip() if n is not None and n.text is not None else d


def _any(el, *paths):
    for p in paths:
        v = _t(el, p)
        if v != "":
            return v
    return ""


def triplet(s):
    n = [_f(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s or "")]
    return (n + [0.0, 0.0, 0.0])[:3]


def duration(s):
    m = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return float(sum(int(a) * m[b] for a, b in re.findall(r"(\d+)\s*([dhms])\b", s or "")))


def mask_url(url):
    p = urlsplit(url)
    q = [(k, "***" if k.lower() in ("password", "pass", "pwd") else v) for k, v in parse_qsl(p.query, True)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q, safe="*"), p.fragment))


def parse_smsc_name(name):
    """Kannel SMSC name -> connection details.
    SMPP:198.51.100.7:2775/2775:ESME_DEMO_01:smpp  ->  protocol SMPP, host 198.51.100.7, port 2775, receive port 2775,
    username ESME_DEMO_01, system-type smpp.  Other drivers (FAKE:10001, HTTP:..., CIMD2:host:port:user) best effort."""
    p = (name or "").split(":")
    d = {"protocol": p[0] if p and p[0] else "unknown", "host": "", "port": "", "receive_port": "", "username": "",
         "system_type": ""}
    rest = p[1:]
    if rest and not rest[0].isdigit():
        d["host"] = rest.pop(0)
    if rest and re.match(r"^\d+(/\d+)?$", rest[0]):
        ports = rest.pop(0).split("/")
        d["port"] = ports[0]
        d["receive_port"] = ports[1] if len(ports) > 1 else ""
    if rest:
        d["username"] = rest.pop(0)
    if rest:
        d["system_type"] = rest.pop(0)
    for k in ("username", "system_type"):
        if d[k].upper() == "NULL":
            d[k] = ""
    if not d["username"]:
        d["username"] = "(none)"
    return d


def unique(keys):
    """Make repeated names unique:  a, a, b  ->  a, a#2, b   (Kannel lists instances with the same admin-id)."""
    seen, out = {}, []
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
        out.append(k if seen[k] == 1 else "%s#%d" % (k, seen[k]))
    return out


# --------------------------------------------------------------------------- parser
def parse_status(raw):
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    if "<gateway" not in text:
        if "Denied" in text or "denied" in text:
            raise ValueError("Kannel answered 'Denied' - wrong status/admin password")
        raise ValueError("not a Kannel status.xml page")
    text = text[text.find("<gateway"):]
    text = text[: text.rfind("</gateway>") + len("</gateway>")]
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    root = ET.fromstring(text.encode("utf-8"))
    if root.find("status") is None:
        body = (root.text or "").strip()
        raise ValueError("Kannel answered %r - wrong status/admin password?" % (body[:40] or "empty page"))
    d = {}
    ver = _t(root, "version")
    head = ver.splitlines()[0] if ver else ""
    d["info"] = {
        "product": head.split(" bearerbox")[0].strip() if " bearerbox" in head else "Kannel",
        "version": re.search(r"version `([^']+)'", ver).group(1) if re.search(r"version `([^']+)'", ver) else "unknown",
        "build": (re.search(r"Build `([^']+)'", ver).group(1) if re.search(r"Build `([^']+)'", ver) else ""),
        "hostname": (re.search(r"Hostname\s+([^,\s]+)", ver).group(1) if re.search(r"Hostname\s+([^,\s]+)", ver) else ""),
        "host_ip": (re.search(r"Hostname\s+[^,]+,\s*IP\s+([0-9A-Fa-f:.]*[0-9A-Fa-f])", ver).group(1)
                    if re.search(r"Hostname\s+[^,]+,\s*IP\s+([0-9A-Fa-f:.]*[0-9A-Fa-f])", ver) else ""),
        "os_release": (re.search(r"release\s+([^,]+),", ver).group(1) if re.search(r"release\s+([^,]+),", ver) else ""),
    }
    d["info"]["flavour"] = "kannel-ha" if "HA" in d["info"]["product"] else "kannel"
    d["info"]["build_type"] = "svn" if d["info"]["version"].startswith("svn") else "release"
    st = _t(root, "status")
    d["state"] = st.split(",")[0].strip() or "unknown"
    m = re.search(r"uptime\s+((?:\d+[dhms]\s*)+)", st)
    d["uptime"] = duration(m.group(1)) if m else 0.0

    d["wdp"] = {k: _f(_t(root, "wdp/%s" % k)) for k in ("received/total", "received/queued", "sent/total", "sent/queued")}
    sms = root.find("sms")
    d["sms"] = {k: _f(_t(sms, k)) for k in ("received/total", "received/queued", "sent/total", "sent/queued")}
    d["sms"]["storesize"] = _f(_t(sms, "storesize"), -1)
    d["sms"]["ha_route"] = _f(_t(sms, "ha-route")) if sms is not None and sms.find("ha-route") is not None else None
    d["sms"]["inbound"], d["sms"]["outbound"] = triplet(_t(sms, "inbound")), triplet(_t(sms, "outbound"))
    dl = root.find("dlr")
    d["dlr"] = {"received": _f(_t(dl, "received/total")), "sent": _f(_t(dl, "sent/total")),
                "inbound": triplet(_t(dl, "inbound")), "outbound": triplet(_t(dl, "outbound")),
                "queued": _f(_t(dl, "queued")), "storage": _t(dl, "storage") or "unknown"}

    boxes = []
    for b in root.findall("boxes/box"):
        s = _t(b, "status")
        box = {"type": _t(b, "type") or "unknown", "id": _t(b, "id") or "none", "ip": _any(b, "ip", "IP") or "unknown",
               "port": _t(b, "port"), "queue": _f(_t(b, "queue")), "ssl": _t(b, "ssl") or "no", "status": s,
               "online": 1.0 if s.lower().startswith(("on-line", "online")) else 0.0, "uptime": duration(s),
               "ha": b.find("open-acks") is not None}
        if box["ha"]:
            box.update({"open_acks": _f(_t(b, "open-acks")), "failed": _f(_t(b, "failed")),
                        "ack_buffer": _f(_t(b, "ack-buffer")),
                        "rx_sms": _f(_t(b, "received/sms")), "rx_dlr": _f(_t(b, "received/dlr")),
                        "tx_sms": _f(_t(b, "sent/sms")), "tx_dlr": _f(_t(b, "sent/dlr")),
                        "in_sms": triplet(_t(b, "load/incoming/sms")), "in_dlr": triplet(_t(b, "load/incoming/dlr")),
                        "out_sms": triplet(_t(b, "load/outgoing/sms")), "out_dlr": triplet(_t(b, "load/outgoing/dlr"))})
        boxes.append(box)
    for box, key in zip(boxes, unique(["%s/%s" % (b["type"], b["id"]) for b in boxes])):
        box["key"] = key
    d["boxes"] = boxes

    smscs = []
    for c in root.findall("smscs/smsc"):
        s = _t(c, "status")
        word = s.split()[0].lower() if s else "unknown"
        smscs.append({
            "name": _t(c, "name"), "admin_id": _t(c, "admin-id") or "none", "id": _t(c, "id") or "none",
            "queue_type": _t(c, "queue"), "status": word, "conn": parse_smsc_name(_t(c, "name")),
            "state": float(SMSC_STATES.get(word, -1)), "online": 1.0 if word == "online" else 0.0,
            "online_s": _f(re.search(r"online\s+(\d+)s", s).group(1)) if re.search(r"online\s+(\d+)s", s) else 0.0,
            "failed": _f(_t(c, "failed")), "queued": _f(_t(c, "queued")),
            "sms_rx": _f(_t(c, "sms/received")), "sms_tx": _f(_t(c, "sms/sent")),
            "sms_in": triplet(_t(c, "sms/inbound")), "sms_out": triplet(_t(c, "sms/outbound")),
            "dlr_rx": _f(_t(c, "dlr/received")), "dlr_tx": _f(_t(c, "dlr/sent")),
            "dlr_in": triplet(_t(c, "dlr/inbound")), "dlr_out": triplet(_t(c, "dlr/outbound"))})
    for smsc, key in zip(smscs, unique([s["admin_id"] for s in smscs])):
        smsc["link"] = key
    d["smscs"] = smscs
    d["smsc_count"] = _f(_t(root, "smscs/count"), len(smscs))
    return d


# --------------------------------------------------------------------------- state tracking
class Tracker:
    """Remembers since when each SMSC link / box is in its current state, and counts link state changes."""

    def __init__(self):
        self.primed = False
        self.smsc = {}      # link -> [state, since]
        self.flaps = {}     # (smsc_id, link) -> number of times the link left 'online'
        self.box = {}

    def update(self, d, now):
        for s in d["smscs"]:
            k = (s["id"], s["link"])
            cur = self.smsc.get(k)
            if cur is None or cur[0] != s["state"]:
                if self.primed and cur is not None and cur[0] == SMSC_STATES["online"]:
                    self.flaps[k] = self.flaps.get(k, 0.0) + 1
                self.smsc[k] = [s["state"], now if cur is not None or s["status"] != "online" else now - s["online_s"]]
            self.flaps.setdefault(k, 0.0)
        live = {(s["id"], s["link"]) for s in d["smscs"]}
        for k in [k for k in self.smsc if k not in live]:
            self.smsc.pop(k, None)
        self.primed = True


# --------------------------------------------------------------------------- scraping
class Target:
    def __init__(self, name, url, timeout=10, insecure=False, username=None, password=None):
        self.name, self.url, self.timeout = name, url, timeout
        self.insecure, self.username, self.password = insecure, username, password

    def fetch(self):
        req = urllib.request.Request(self.url, headers={"User-Agent": "kannel_exporter/" + __version__})
        if self.username:
            tok = base64.b64encode(("%s:%s" % (self.username, self.password or "")).encode()).decode()
            req.add_header("Authorization", "Basic " + tok)
        ctx = ssl._create_unverified_context() if self.insecure else None
        with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
            return r.read()


class State:
    def __init__(self):
        self.up, self.data, self.duration, self.errors, self.scrapes, self.last_ok = 0.0, None, 0.0, 0.0, 0.0, 0.0
        self.tracker = Tracker()


class KannelExporter:
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
                self.states.setdefault(t.name, State())
        log.info("targets: %s", ", ".join("%s=%s" % (t.name, mask_url(t.url)) for t in targets))

    def _scrape(self, t):
        t0 = time.time()
        try:
            return t, parse_status(t.fetch()), time.time() - t0, None
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
                    st.up, st.data = 0.0, None
                    st.errors += 1
                    log.warning("scrape %s failed (%.2fs): %s", t.name, dur, err)
                else:
                    st.tracker.update(data, now)
                    st.up, st.data, st.last_ok = 1.0, data, now

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

    def collect(self):
        with self.lock:
            snap = [(n, s.up, s.data, s.duration, s.errors, s.scrapes, s.last_ok,
                     {k: list(v) for k, v in s.tracker.smsc.items()}, dict(s.tracker.flaps))
                    for n, s in self.states.items()]
        S = ["server"]
        L = ["server", "smsc_id", "admin_id"]
        BX = ["server", "box_type", "box_id"]
        m = {}

        def g(n, doc, lbl): m[n] = GaugeMetricFamily(n, doc, labels=lbl)

        def c(n, doc, lbl): m[n] = CounterMetricFamily(n, doc, labels=lbl)

        g("kannel_up", "1 if the last scrape of the bearerbox status page succeeded", S)
        g("kannel_scrape_duration_seconds", "Duration of the last status page scrape", S)
        c("kannel_scrape_errors", "Failed status page scrapes since exporter start", S)
        c("kannel_scrapes", "Status page scrapes since exporter start", S)
        g("kannel_last_scrape_success_timestamp_seconds", "Unix time of the last successful scrape", S)
        g("kannel_gateway_info", "bearerbox build / host information (value 1)",
          S + ["product", "flavour", "build_type", "version", "build", "hostname", "host_ip", "os_release", "dlr_storage"])
        g("kannel_gateway_state", "1 for the current bearerbox state (running, suspended, isolated, full, shutting down)",
          S + ["state"])
        g("kannel_uptime_seconds", "bearerbox uptime", S)
        c("kannel_sms", "SMS counted by bearerbox. direction=received (MO from SMSCs) | sent (MT to SMSCs)", S + ["direction"])
        g("kannel_sms_queued", "SMS waiting in bearerbox queues. direction=received|sent", S + ["direction"])
        c("kannel_dlr", "DLRs counted by bearerbox. direction=received (from SMSCs) | sent", S + ["direction"])
        g("kannel_dlr_queued", "DLR entries waiting in dlr-storage for their delivery report", S)
        c("kannel_wdp", "WDP packets (WAP). direction=received|sent", S + ["direction"])
        g("kannel_wdp_queued", "WDP packets queued. direction=received|sent", S + ["direction"])
        g("kannel_sms_store_size", "Messages in the store-file / store (-1 = store disabled)", S)
        g("kannel_sms_ha_route", "Kannel-HA: SMS waiting for HA routing", S)
        g("kannel_load_messages_per_second", "bearerbox load. type=sms|dlr, direction=inbound|outbound, window=1m|5m|overall",
          S + ["type", "direction", "window"])
        g("kannel_smscs_configured", "SMSC links configured", S)
        g("kannel_smscs_online", "SMSC links online", S)
        g("kannel_boxes_connected", "Boxes (smsbox/wapbox/ksmppd/smppbox) connected", S + ["box_type"])
        # smsc links
        g("kannel_smsc_info", "SMSC link information (value 1)", L + ["name", "queue_type", "status"])
        g("kannel_smsc_connection_info", "SMSC link connection details parsed from the name (value 1): "
          "protocol, operator host, port, receive port, SMSC username (system-id), system-type",
          L + ["protocol", "host", "port", "receive_port", "username", "system_type"])
        g("kannel_smsc_online", "1 if the SMSC link is online", L)
        g("kannel_smsc_state", "SMSC state code: 4 online, 3 re-connecting, 2 connecting, 1 disconnected, 0 dead", L)
        g("kannel_smsc_online_seconds", "Seconds the link has been online (0 if not online)", L)
        g("kannel_smsc_state_since_timestamp_seconds", "Unix time the link entered its current state", L)
        c("kannel_smsc_state_drops", "Times the link left the online state (seen by the exporter)", L)
        c("kannel_smsc_sms", "SMS on the link. direction=sent (MT to operator) | received (MO from operator)", L + ["direction"])
        c("kannel_smsc_dlr", "DLRs on the link. direction=received (from operator) | sent", L + ["direction"])
        c("kannel_smsc_failed", "MT messages that failed on the link", L)
        g("kannel_smsc_queued", "MT messages queued for the link", L)
        g("kannel_smsc_load_messages_per_second", "Link load. type=sms|dlr direction=inbound|outbound window=1m|5m|overall",
          L + ["type", "direction", "window"])
        # boxes
        g("kannel_box_info", "Connected box information (value 1)", BX + ["ip", "port", "ssl", "status"])
        g("kannel_box_online", "1 if the box is on-line", BX)
        g("kannel_box_uptime_seconds", "Seconds the box has been connected", BX)
        g("kannel_box_queue", "Messages queued towards the box", BX)
        g("kannel_box_open_acks", "Kannel-HA: open acks towards the box", BX)
        g("kannel_box_ack_buffer", "Kannel-HA: ack buffer fill of the box", BX)
        c("kannel_box_failed", "Kannel-HA: failed messages of the box", BX)
        c("kannel_box_messages", "Kannel-HA: messages from/to the box. type=sms|dlr direction=received|sent",
          BX + ["type", "direction"])
        g("kannel_box_load_messages_per_second", "Kannel-HA box load. type, direction=incoming|outgoing, window",
          BX + ["type", "direction", "window"])
        g("kannel_exporter_build_info", "Exporter version", ["version"])
        g("kannel_exporter_targets", "Configured targets", [])
        m["kannel_exporter_build_info"].add_metric([__version__], 1)
        m["kannel_exporter_targets"].add_metric([], len(snap))

        for name, up, d, dur, errs, scrapes, last_ok, sstate, flaps in snap:
            s = [name]
            m["kannel_up"].add_metric(s, up)
            m["kannel_scrape_duration_seconds"].add_metric(s, dur)
            m["kannel_scrape_errors"].add_metric(s, errs)
            m["kannel_scrapes"].add_metric(s, scrapes)
            m["kannel_last_scrape_success_timestamp_seconds"].add_metric(s, last_ok)
            if not d:
                continue
            i = d["info"]
            m["kannel_gateway_info"].add_metric(s + [i["product"], i["flavour"], i["build_type"], i["version"], i["build"],
                                                     i["hostname"], i["host_ip"], i["os_release"], d["dlr"]["storage"]], 1)
            states = set(GW_STATES) | {d["state"]}
            for stt in states:
                m["kannel_gateway_state"].add_metric(s + [stt], 1.0 if stt == d["state"] else 0.0)
            m["kannel_uptime_seconds"].add_metric(s, d["uptime"])
            m["kannel_sms"].add_metric(s + ["received"], d["sms"]["received/total"])
            m["kannel_sms"].add_metric(s + ["sent"], d["sms"]["sent/total"])
            m["kannel_sms_queued"].add_metric(s + ["received"], d["sms"]["received/queued"])
            m["kannel_sms_queued"].add_metric(s + ["sent"], d["sms"]["sent/queued"])
            m["kannel_dlr"].add_metric(s + ["received"], d["dlr"]["received"])
            m["kannel_dlr"].add_metric(s + ["sent"], d["dlr"]["sent"])
            m["kannel_dlr_queued"].add_metric(s, d["dlr"]["queued"])
            m["kannel_wdp"].add_metric(s + ["received"], d["wdp"]["received/total"])
            m["kannel_wdp"].add_metric(s + ["sent"], d["wdp"]["sent/total"])
            m["kannel_wdp_queued"].add_metric(s + ["received"], d["wdp"]["received/queued"])
            m["kannel_wdp_queued"].add_metric(s + ["sent"], d["wdp"]["sent/queued"])
            m["kannel_sms_store_size"].add_metric(s, d["sms"]["storesize"])
            if d["sms"]["ha_route"] is not None:
                m["kannel_sms_ha_route"].add_metric(s, d["sms"]["ha_route"])
            for typ, src in (("sms", d["sms"]), ("dlr", d["dlr"])):
                for direction in ("inbound", "outbound"):
                    for w, v in zip(WINDOWS, src[direction]):
                        m["kannel_load_messages_per_second"].add_metric(s + [typ, direction, w], v)
            m["kannel_smscs_configured"].add_metric(s, d["smsc_count"])
            m["kannel_smscs_online"].add_metric(s, sum(x["online"] for x in d["smscs"]))
            btypes = {}
            for b in d["boxes"]:
                btypes[b["type"]] = btypes.get(b["type"], 0) + b["online"]
            for bt in set(btypes) | {"smsbox", "wapbox"}:
                m["kannel_boxes_connected"].add_metric(s + [bt], btypes.get(bt, 0))

            for x in d["smscs"]:
                l = [name, x["id"], x["link"]]
                m["kannel_smsc_info"].add_metric(l + [x["name"], x["queue_type"], x["status"]], 1)
                cn = x["conn"]
                m["kannel_smsc_connection_info"].add_metric(l + [cn["protocol"], cn["host"], cn["port"], cn["receive_port"],
                                                                 cn["username"], cn["system_type"]], 1)
                m["kannel_smsc_online"].add_metric(l, x["online"])
                m["kannel_smsc_state"].add_metric(l, x["state"])
                m["kannel_smsc_online_seconds"].add_metric(l, x["online_s"])
                st = sstate.get((x["id"], x["link"]))
                if st:
                    m["kannel_smsc_state_since_timestamp_seconds"].add_metric(l, st[1])
                m["kannel_smsc_state_drops"].add_metric(l, flaps.get((x["id"], x["link"]), 0.0))
                m["kannel_smsc_sms"].add_metric(l + ["sent"], x["sms_tx"])
                m["kannel_smsc_sms"].add_metric(l + ["received"], x["sms_rx"])
                m["kannel_smsc_dlr"].add_metric(l + ["received"], x["dlr_rx"])
                m["kannel_smsc_dlr"].add_metric(l + ["sent"], x["dlr_tx"])
                m["kannel_smsc_failed"].add_metric(l, x["failed"])
                m["kannel_smsc_queued"].add_metric(l, x["queued"])
                for typ in ("sms", "dlr"):
                    for direction, key in (("inbound", "_in"), ("outbound", "_out")):
                        for w, v in zip(WINDOWS, x[typ + key]):
                            m["kannel_smsc_load_messages_per_second"].add_metric(l + [typ, direction, w], v)

            for b in d["boxes"]:
                bid = b["key"].split("/", 1)[1]
                bl = [name, b["type"], bid]
                m["kannel_box_info"].add_metric(bl + [b["ip"], b["port"], b["ssl"], b["status"].split(" ")[0]], 1)
                m["kannel_box_online"].add_metric(bl, b["online"])
                m["kannel_box_uptime_seconds"].add_metric(bl, b["uptime"])
                m["kannel_box_queue"].add_metric(bl, b["queue"])
                if b["ha"]:
                    m["kannel_box_open_acks"].add_metric(bl, b["open_acks"])
                    m["kannel_box_ack_buffer"].add_metric(bl, b["ack_buffer"])
                    m["kannel_box_failed"].add_metric(bl, b["failed"])
                    for typ in ("sms", "dlr"):
                        m["kannel_box_messages"].add_metric(bl + [typ, "received"], b["rx_" + typ])
                        m["kannel_box_messages"].add_metric(bl + [typ, "sent"], b["tx_" + typ])
                        for direction, key in (("incoming", "in_"), ("outgoing", "out_")):
                            for w, v in zip(WINDOWS, b[key + typ]):
                                m["kannel_box_load_messages_per_second"].add_metric(bl + [typ, direction, w], v)
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
    out = [Target(str(t["name"]), t["url"], float(t.get("timeout", timeout)), bool(t.get("insecure", False)),
                  t.get("username"), t.get("password")) for t in (cfg.get("targets") or [])]
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
    ap = argparse.ArgumentParser(description="Kannel bearerbox multi-target Prometheus exporter",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("-c", "--config", help="YAML/JSON config (CLI flags override it)")
    ap.add_argument("-t", "--target", action="append", help="NAME=URL (repeatable)")
    ap.add_argument("--listen-address", default=None, help="bind address [0.0.0.0]")
    ap.add_argument("-p", "--port", type=int, default=None, help="metrics port [9879]")
    ap.add_argument("-i", "--interval", type=float, default=None, help="scrape cycle seconds [15]")
    ap.add_argument("--timeout", type=float, default=None, help="per-target HTTP timeout [10]")
    ap.add_argument("--workers", type=int, default=None, help="parallel scrapes [16]")
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
    o.port = int(pick(a.port, "port", 9879))
    o.interval = float(pick(a.interval, "scrape_interval", 15))
    o.timeout = float(pick(a.timeout, "timeout", 10))
    o.workers = int(pick(a.workers, "max_workers", 16))
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
        for col in (prometheus_client.PROCESS_COLLECTOR, prometheus_client.PLATFORM_COLLECTOR, prometheus_client.GC_COLLECTOR):
            try:
                REGISTRY.unregister(col)
            except Exception:  # noqa
                pass
    exp = KannelExporter(o)
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
    log.info("kannel_exporter %s on %s:%d, interval %.0fs, %d targets", __version__, o.listen, o.port, o.interval, len(targets))
    threading.Thread(target=exp.loop, args=(stop,), daemon=True).start()
    while not stop.is_set():
        stop.wait(1)


if __name__ == "__main__":
    main()
