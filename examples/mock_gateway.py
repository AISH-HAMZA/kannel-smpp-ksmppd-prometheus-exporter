#!/usr/bin/env python3
"""
mock_gateway.py - fake SMS gateway status pages with live, moving counters (demo + tests only).

Serves several virtual gateways from ONE port, selected by the first path element:

  http://localhost:8080/smppbox-a/status.xml?password=demo       Kannel smppbox
  http://localhost:8080/ksmppd-a/esme-status.xml?password=demo   KSMPPD (XML)
  http://localhost:8080/ksmppd-a/esme-status?password=demo       KSMPPD (plain text)
  http://localhost:8080/ksmppd-a/uptime.xml?password=demo        KSMPPD uptime
  http://localhost:8080/kannel-a/status.xml?password=demo        Kannel bearerbox (kannel-ha-* = Kannel-HA build)

A wrong password returns "Denied" exactly like the real gateways. All names, IPs and numbers are fictional
(RFC 5737 documentation addresses). Only the Python standard library is used.

  python3 examples/mock_gateway.py --port 8080 --password demo
  python3 examples/mock_gateway.py --dump examples/pages      # write static sample pages and exit
"""

import argparse
import math
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

START = time.time()
LOCK = threading.Lock()


def wave(t, period, phase=0.0, low=0.3, high=1.0):
    """Smooth 'day/night' traffic shape compressed to `period` seconds, plus a little noise."""
    x = (math.sin(2 * math.pi * (t / period) + phase) + 1) / 2
    return (low + (high - low) * x) * random.uniform(0.92, 1.08)


def hms(sec):
    sec = int(sec)
    return "%dd %dh %dm %ds" % (sec // 86400, sec % 86400 // 3600, sec % 3600 // 60, sec % 60)


def trip(a, b, c):
    return "%.2f,%.2f,%.2f" % (a, b, c)


class Flow:
    """A counter pair (in/out) that grows with a varying rate."""

    def __init__(self, base_rate, phase=0.0, period=900.0, out_ratio=0.97, start_total=0):
        self.base, self.phase, self.period, self.out_ratio = base_rate, phase, period, out_ratio
        self.inn = float(start_total)
        self.out = float(start_total) * out_ratio
        self.failed = 0.0
        self.rate_in = self.rate_out = 0.0
        self.avg5 = self.avg1 = 0.0

    def step(self, now, dt):
        r = self.base * wave(now - START, self.period, self.phase)
        self.rate_in, self.rate_out = r, r * self.out_ratio * random.uniform(0.95, 1.02)
        self.inn += r * dt
        self.out += self.rate_out * dt
        self.failed += r * dt * random.uniform(0.0, 0.01)
        self.avg1 += (r - self.avg1) * min(1.0, dt / 60)
        self.avg5 += (r - self.avg5) * min(1.0, dt / 300)


# --------------------------------------------------------------------------- smppbox
class Smppbox:
    kind = "smppbox"
    CUSTOMERS = [("customer-001", "route-a", 120), ("customer-002", "route-a", 45), ("customer-003", "route-b", 18),
                 ("customer-004", "route-b", 6), ("customer-005", "route-c", 0)]

    def __init__(self, name, ip, scale, seed):
        self.name, self.ip, self.scale = name, ip, scale
        self.rnd = random.Random(seed)
        self.sessions = []
        self.port = 40000
        for i, (esme, smsc, rate) in enumerate(self.CUSTOMERS):
            for btype in (("trcv", "trcv") if rate > 50 else ("trcv",) if rate else ()):
                self._new_session(esme, smsc, rate * scale / 2, btype, i, age=self.rnd.randint(3600, 90000))
        self.last = time.time()

    def _new_session(self, esme, smsc, rate, btype, idx, age=0):
        self.port += 1
        self.sessions.append({"esme": esme, "smsc": smsc, "type": btype, "port": self.port,
                              "ip": "203.0.113.%d" % (10 + idx), "start": time.time() - age,
                              "flow": Flow(rate, phase=idx, start_total=rate * age * 0.5)})

    def tick(self, now):
        dt, self.last = now - self.last, now
        for s in list(self.sessions):
            s["flow"].step(now, dt)
            if self.rnd.random() < 0.002 * dt:           # occasional reconnect -> session counters restart at 0
                self.sessions.remove(s)
                self._new_session(s["esme"], s["smsc"], s["flow"].base, s["type"],
                                  [c[0] for c in self.CUSTOMERS].index(s["esme"]))

    def render(self, now):
        up = now - START + 3 * 86400 + 4 * 3600
        tin = sum(s["flow"].inn for s in self.sessions)
        tout = sum(s["flow"].out for s in self.sessions)
        rin = sum(s["flow"].rate_in for s in self.sessions)
        rout = sum(s["flow"].rate_out for s in self.sessions)
        x = ['<?xml version="1.0"?>', "<gateway>",
             "<version>Kannel smppbox/1.5.0 version `1.5.0'.\nBuild `Oct  1 2026 10:00:00', compiler `12.2.0'.\n"
             "System Linux, release 6.1.0-25-amd64, version #1 SMP, machine x86_64.\n"
             "Hostname %s, IP %s.\nLibxml version 2.9.14.\nCompiled with MySQL 8.0.36, using MySQL 8.0.36.</version>"
             % (self.name, self.ip),
             "<status>running, uptime %s, CPU time %d:%05.2f, resp mode async</status>" % (hms(up), up / 90, (up / 1.5) % 60)]
        for side, a, b, ra, rb in (("bearerbox", tout, tin, rout, rin), ("esme", tin, tout, rin, rout)):
            x.append("<%s><status>connected</status><received><total>%d</total><queued>%d</queued></received>"
                     "<sent><total>%d</total><queued>0</queued></sent><inbound>%s</inbound><outbound>%s</outbound></%s>"
                     % (side, a, self.rnd.randint(0, 5), b, trip(ra, ra * 0.95, ra * 0.8), trip(rb, rb * 0.95, rb * 0.8), side))
        x.append("<store><size>%d</size><status>1</status></store><memory><total>%.2fM</total></memory>"
                 % (self.rnd.randint(0, 40), 300 + self.rnd.random() * 30))
        x.append("<logins><count>%d</count>" % len(self.CUSTOMERS))
        for esme, smsc, _ in self.CUSTOMERS:
            n = sum(1 for s in self.sessions if s["esme"] == esme)
            state = "online" if n else "offline"
            x.append("<smsc><id>%s</id><smsc-id>%s</smsc-id><shortcode></shortcode><keyword></keyword>"
                     "<status>%s, trans -/2, recv -/2, trcv %d/4, resp mode async</status></smsc>" % (esme, smsc, state, n))
        x.append("</logins><sessions><count>%d</count>" % len(self.sessions))
        for s in self.sessions:
            f = s["flow"]
            x.append("<session><esme>%s</esme><ip>%s</ip><port>%d</port><type>%s</type><status>online %ds, rcvd %d "
                     "sent %d failed %d, resp %d PDUs, open %d acks, in %.2f msg/s, out %.2f msg/s</status></session>"
                     % (s["esme"], s["ip"], s["port"], s["type"], now - s["start"], f.inn, f.out, f.failed,
                        f.inn + f.out, self.rnd.randint(0, 8), f.rate_in, f.rate_out))
        x.append("</sessions><plugins><trigger-chain><trigger-type>submit_sm</trigger-type><count>2</count>"
                 "<plugin><id>mysql-log</id><args>db=sms_log</args><state>running</state><async>yes</async>"
                 "<status>%d/10 idle database connections, %d SQL statements in queue</status></plugin>"
                 "<plugin><id>route-by-prefix</id><args>table=routes</args><state>running</state><async>no</async>"
                 "<status>ok</status></plugin></trigger-chain></plugins></gateway>"
                 % (self.rnd.randint(4, 10), self.rnd.randint(0, 30)))
        return "".join(x)


# --------------------------------------------------------------------------- ksmppd
class Ksmppd:
    kind = "ksmppd"
    CUSTOMERS = [("ESME_DEMO_01", 100, 80), ("ESME_DEMO_02", 50, 30), ("ESME_DEMO_03", 20, 9), ("ESME_DEMO_04", 10, 2)]

    def __init__(self, name, ip, scale, seed):
        self.name, self.ip, self.rnd = name, ip, random.Random(seed)
        self.esmes = []
        for i, (sid, limit, rate) in enumerate(self.CUSTOMERS):
            nb = 2 if rate > 20 else 1
            self.esmes.append({"id": sid, "limit": limit, "mt": Flow(rate * scale, phase=i, start_total=rate * 40000),
                               "dlr": 0.0, "mo": 0.0, "err": 0.0,
                               "binds": [{"id": i * 10 + b + 1, "ip": "203.0.113.%d" % (40 + i), "type": 3 if b == 0 else 2,
                                          "start": time.time() - self.rnd.randint(600, 50000)} for b in range(nb)]})
        self.last = time.time()

    def tick(self, now):
        dt, self.last = now - self.last, now
        for e in self.esmes:
            e["mt"].step(now, dt)
            e["dlr"] += e["mt"].rate_out * dt * 0.98
            e["mo"] += e["mt"].rate_in * dt * 0.02
            e["err"] += e["mt"].rate_in * dt * self.rnd.uniform(0, 0.015)

    def _rows(self):
        for e in self.esmes:
            f = e["mt"]
            yield e, f, (f.rate_in, f.rate_in * 1.02, f.avg1), (f.rate_out, f.rate_out, f.avg1 * 0.98)

    def render_xml(self, now):
        tin = sum(e["mt"].inn for e in self.esmes)
        tout = sum(e["dlr"] + e["mo"] for e in self.esmes)
        ri = sum(e["mt"].rate_in for e in self.esmes)
        x = ["<esmes><summary><unique>%d</unique><inbound-processed>%d</inbound-processed>"
             "<outbound-processed>%d</outbound-processed><inbound-load>%.2f/%.2f/%.2f</inbound-load>"
             "<outbound-load>%.2f/%.2f/%.2f</outbound-load></summary>" % (len(self.esmes), tin, tout, ri * .7, ri, ri * .97,
                                                                           ri * .68, ri * .98, ri * .95)]
        for e, f, il, ol in self._rows():
            x.append("<esme><system-id>%s</system-id><bind-count>%d</bind-count><max-binds>4</max-binds>"
                     "<inbound-load>%.2f/%.2f/%.2f</inbound-load><outbound-load>%.2f/%.2f/%.2f</outbound-load>"
                     "<max-inbound-load>%d</max-inbound-load><mt>%d</mt><mo>%d</mo><dlr>%d</dlr><errors>%d</errors>"
                     % ((e["id"], len(e["binds"])) + il + ol + (e["limit"], f.inn, e["mo"], e["dlr"], e["err"])))
            for b in e["binds"]:
                share = 1.0 / len(e["binds"])
                x.append("<bind><bind-id>%d</bind-id><ip>%s</ip><uptime>%d</uptime><bind-type>%d</bind-type>"
                         "<open-acks>%d</open-acks><simulate>no</simulate><inbound-load>%.2f</inbound-load>"
                         "<inbound-queued>0</inbound-queued><inbound-processed>%d</inbound-processed>"
                         "<inbound-routing>0</inbound-routing><outbound-load>%.2f</outbound-load>"
                         "<outbound-queued>0</outbound-queued><outbound-processed>%d</outbound-processed>"
                         "<mt>%d</mt><mo>%d</mo><dlr>%d</dlr><errors>%d</errors></bind>"
                         % (b["id"], b["ip"], now - b["start"], b["type"], self.rnd.randint(0, 5), f.rate_in * share,
                            f.inn * share, f.rate_out * share, (e["dlr"] + e["mo"]) * share, f.inn * share,
                            e["mo"] * share, e["dlr"] * share, e["err"] * share))
            x.append("</esme>")
        x.append("</esmes>")
        return "".join(x)

    def render_text(self, now):
        tin = sum(e["mt"].inn for e in self.esmes)
        tout = sum(e["dlr"] + e["mo"] for e in self.esmes)
        ri = sum(e["mt"].rate_in for e in self.esmes)
        x = ["Unique known ESME's: %d" % len(self.esmes),
             "Total inbound processed: %d load: %.2f/%.2f/%.2f" % (tin, ri * .7, ri, ri * .97),
             "Total outbound processed: %d load: %.2f/%.2f/%.2f" % (tout, ri * .68, ri * .98, ri * .95), ""]
        for e, f, il, ol in self._rows():
            x.append("%s - binds:%d/4, total inbound load:(%.2f/%.2f/%.2f)/%d/sec, outbound load:(%.2f/%.2f/%.2f)/sec, "
                     "mt/mo/dlr/errors:(%d/%d/%d/%d)" % ((e["id"], len(e["binds"])) + il + (e["limit"],) + ol
                                                        + (f.inn, e["mo"], e["dlr"], e["err"])))
            for b in e["binds"]:
                share = 1.0 / len(e["binds"])
                x.append("-- id:%d ip:%s uptime:%s, type:%d, open-acks:%d, simulate: no, inbound "
                         "(load/queued/processed/routing):%.2f/0/%d/0, outbound (load/queued/processed):%.2f/0/%d, "
                         "mt/mo/dlr/errors:%d/%d/%d/%d"
                         % (b["id"], b["ip"], hms(now - b["start"]), b["type"], self.rnd.randint(0, 5), f.rate_in * share,
                            f.inn * share, f.rate_out * share, (e["dlr"] + e["mo"]) * share, f.inn * share,
                            e["mo"] * share, e["dlr"] * share, e["err"] * share))
        return "\n".join(x) + "\n"

    def render_uptime(self, now):
        return "<uptime>%d</uptime>" % (now - START + 5 * 86400)


# --------------------------------------------------------------------------- kannel bearerbox
class Kannel:
    kind = "kannel"
    LINKS = [("operator-a", "SMPP:198.51.100.21:2775/2775:ESME_DEMO_01:smpp", 2, 60),
             ("operator-b", "SMPP:198.51.100.22:2775/2775:ESME_DEMO_02:smpp", 1, 25),
             ("operator-c", "SMPP:198.51.100.23:2776/0:ESME_DEMO_03:NULL", 1, 8),
             ("lab-fake", "FAKE:10001", 1, 1)]

    def __init__(self, name, ip, scale, seed, ha=False):
        self.name, self.ip, self.ha, self.rnd = name, ip, ha, random.Random(seed)
        self.links = []
        for i, (sid, conn, inst, rate) in enumerate(self.LINKS):
            for _ in range(inst):                                    # instances = N -> same admin-id N times
                self.links.append({"id": sid, "name": conn, "flow": Flow(rate * scale / inst, phase=i, start_total=rate * 30000),
                                   "state": "online", "since": time.time() - self.rnd.randint(600, 80000), "q": 0})
        self.last = time.time()

    def tick(self, now):
        dt, self.last = now - self.last, now
        for i, l in enumerate(self.links):
            if l["state"] == "online":
                l["flow"].step(now, dt)
                l["q"] = self.rnd.randint(0, 20)
                if i == len(self.links) - 2 and self.rnd.random() < 0.004 * dt:  # one link flaps now and then
                    l["state"], l["since"] = "re-connecting", now
            elif now - l["since"] > self.rnd.randint(20, 60):
                l["state"], l["since"] = "online", now
            else:
                l["flow"].rate_in = l["flow"].rate_out = 0.0
                l["q"] += int(5 * dt)

    def render(self, now):
        up = now - START + 2 * 86400
        prod = "Kannel-HA bearerbox version `svn-b-r430'" if self.ha else "Kannel bearerbox version `1.4.5'"
        mt = sum(l["flow"].inn for l in self.links)
        dlr = sum(l["flow"].out for l in self.links)
        r = sum(l["flow"].rate_in for l in self.links)
        ro = sum(l["flow"].rate_out for l in self.links)
        mo = mt * 0.02
        x = ['<?xml version="1.0"?>', "<gateway>",
             "<version>%s.\nBuild `Oct  1 2026 10:00:00', compiler `12.2.0'.\nSystem Linux, release 6.1.0-25-amd64, "
             "version #1 SMP, machine x86_64.\nHostname %s, IP %s.\nLibxml version 2.9.14.</version>"
             % (prod, self.name, self.ip),
             "<status>running, uptime %s</status>" % hms(up),
             "<wdp><received><total>0</total><queued>0</queued></received><sent><total>0</total><queued>0</queued></sent>"
             "<inbound>0.00,0.00,0.00</inbound><outbound>0.00,0.00,0.00</outbound></wdp>",
             "<sms><received><total>%d</total><queued>%d</queued></received><sent><total>%d</total><queued>%d</queued></sent>"
             "<storesize>%d</storesize>%s<inbound>%s</inbound><outbound>%s</outbound></sms>"
             % (mo, 0, mt, sum(l["q"] for l in self.links), self.rnd.randint(0, 60),
                "<ha-route>%d</ha-route>" % self.rnd.randint(0, 3) if self.ha else "",
                trip(r * 0.02, r * 0.02, r * 0.015), trip(r, r * 0.97, r * 0.8)),
             "<dlr><received><total>%d</total></received><sent><total>%d</total></sent><inbound>%s</inbound>"
             "<outbound>%s</outbound><queued>%d</queued><storage>internal</storage></dlr>"
             % (dlr, dlr, trip(ro, ro * 0.97, ro * 0.8), trip(ro, ro * 0.97, ro * 0.8), self.rnd.randint(100, 900)),
             "<boxes>"]
        for i, (btype, bid) in enumerate((("smsbox", "smsbox-1"), ("smsbox", "smppbox-a"), ("smsbox", "ksmppd-a"))):
            x.append("<box><type>%s</type><id>%s</id><IP>192.0.2.%d</IP><queue>%d</queue><status>on-line %s</status><ssl>no</ssl>"
                     % (btype, bid, 60 + i, self.rnd.randint(0, 10), hms(up - 100 * i)))
            if self.ha:
                x.append("<open-acks>%d</open-acks><failed>%d</failed><ack-buffer>%d</ack-buffer>"
                         "<received><sms>%d</sms><dlr>0</dlr></received><sent><sms>%d</sms><dlr>%d</dlr></sent>"
                         "<load><incoming><sms>%s</sms><dlr>0,0,0</dlr></incoming><outgoing><sms>%s</sms><dlr>%s</dlr></outgoing></load>"
                         % (self.rnd.randint(0, 9), mt * 0.001, self.rnd.randint(0, 50), mt / 3, mo / 3, dlr / 3,
                            trip(r / 3, r / 3, r / 4), trip(r / 150, r / 150, r / 200), trip(ro / 3, ro / 3, ro / 4)))
            x.append("</box>")
        x.append("</boxes><smscs><count>%d</count>" % len(self.links))
        for l in self.links:
            f = l["flow"]
            status = "online %ds" % (now - l["since"]) if l["state"] == "online" else "re-connecting"
            x.append("<smsc><name>%s</name><admin-id>%s</admin-id><id>%s</id>%s<status>%s</status><failed>%d</failed>"
                     "<queued>%d</queued><sms><received>%d</received><sent>%d</sent><inbound>%s</inbound><outbound>%s</outbound>"
                     "</sms><dlr><received>%d</received><sent>0</sent><inbound>%s</inbound><outbound>0.00,0.00,0.00</outbound></dlr></smsc>"
                     % (l["name"], l["id"], l["id"], "<queue>normal</queue>" if self.ha else "", status, f.failed, l["q"],
                        f.inn * 0.02, f.inn, trip(f.rate_in * 0.02, f.rate_in * 0.02, f.avg5 * 0.02),
                        trip(f.rate_in, f.avg1, f.avg5), f.out, trip(f.rate_out, f.avg1 * 0.97, f.avg5 * 0.97)))
        x.append("</smscs></gateway>")
        return "".join(x)


GATEWAYS = {
    "smppbox-a": Smppbox("smppbox-a", "192.0.2.10", 1.0, 1), "smppbox-b": Smppbox("smppbox-b", "192.0.2.11", 0.4, 2),
    "ksmppd-a": Ksmppd("ksmppd-a", "192.0.2.20", 1.0, 3), "ksmppd-b": Ksmppd("ksmppd-b", "192.0.2.21", 0.5, 4),
    "kannel-a": Kannel("kannel-a", "192.0.2.30", 1.0, 5), "kannel-ha-a": Kannel("kannel-ha-a", "192.0.2.31", 0.7, 6, ha=True),
}


def page(gw, path, now):
    with LOCK:
        gw.tick(now)
        if gw.kind == "smppbox" and path == "status.xml":
            return gw.render(now)
        if gw.kind == "kannel" and path == "status.xml":
            return gw.render(now)
        if gw.kind == "ksmppd":
            return {"esme-status.xml": gw.render_xml, "esme-status": gw.render_text, "uptime.xml": gw.render_uptime}.get(
                path, lambda n: None)(now)
    return None


class Handler(BaseHTTPRequestHandler):
    password = "demo"

    def do_GET(self):  # noqa: N802
        u = urlsplit(self.path)
        parts = u.path.strip("/").split("/")
        if parts == [""] or parts == ["healthz"]:
            return self._send(200, "ok\n" + "\n".join("/%s/" % n for n in GATEWAYS) + "\n", "text/plain")
        gw = GATEWAYS.get(parts[0])
        if gw is None or len(parts) != 2:
            return self._send(404, "not found\n", "text/plain")
        if parse_qs(u.query).get("password", [""])[0] != self.password:
            body = "<gateway>Denied</gateway>" if gw.kind == "kannel" else "Denied"
            return self._send(200, body, "text/xml" if gw.kind == "kannel" else "text/plain")
        body = page(gw, parts[1], time.time())
        if body is None:
            return self._send(404, "not found\n", "text/plain")
        self._send(200, body, "text/plain" if parts[1] == "esme-status" else "text/xml")

    def _send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def dump(outdir):
    os.makedirs(outdir, exist_ok=True)
    random.seed(42)
    now = START + 120
    files = {"smppbox_status.xml": ("smppbox-a", "status.xml"), "ksmppd_esme-status.xml": ("ksmppd-a", "esme-status.xml"),
             "ksmppd_esme-status.txt": ("ksmppd-a", "esme-status"), "ksmppd_uptime.xml": ("ksmppd-a", "uptime.xml"),
             "kannel_status.xml": ("kannel-a", "status.xml"), "kannel-ha_status.xml": ("kannel-ha-a", "status.xml")}
    for fn, (gw, p) in files.items():
        with open(os.path.join(outdir, fn), "w", newline="\n") as fh:
            fh.write(page(GATEWAYS[gw], p, now))
        print("wrote", os.path.join(outdir, fn))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("MOCK_PORT", 8080)))
    ap.add_argument("--password", default=os.environ.get("MOCK_PASSWORD", "demo"))
    ap.add_argument("--dump", metavar="DIR", help="write static sample pages to DIR and exit")
    a = ap.parse_args()
    if a.dump:
        return dump(a.dump)
    Handler.password = a.password
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    print("mock gateway on :%d  (%s)" % (a.port, ", ".join(GATEWAYS)), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
