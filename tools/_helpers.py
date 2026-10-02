#!/usr/bin/env python3
"""Shared Grafana panel helpers for the dashboard generators (exec()-ed by gen_*_dashboard.py)."""

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


