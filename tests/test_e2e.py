"""End-to-end: start the mock gateway, run each exporter with --once and check the /metrics text."""
import json
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from conftest import ROOT


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def mock():
    port = _free_port()
    proc = subprocess.Popen([sys.executable, str(ROOT / "examples" / "mock_gateway.py"), "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield base
    proc.terminate()
    proc.wait(5)


def _once(script, target):
    out = subprocess.run([sys.executable, str(ROOT / "exporters" / script), "--once", "-t", target],
                         capture_output=True, text=True, timeout=60)
    return out.stdout


@pytest.mark.parametrize("script,gw,path,metric", [
    ("smppbox/smpp_exporter.py", "smppbox-a", "status.xml", "smppbox_logins_online"),
    ("ksmppd/ksmppd_exporter.py", "ksmppd-a", "esme-status.xml", "ksmppd_esme_mt_total"),
    ("ksmppd/ksmppd_exporter.py", "ksmppd-b", "esme-status", "ksmppd_esme_mt_total"),
    ("kannel/kannel_exporter.py", "kannel-ha-a", "status.xml", "kannel_smsc_online"),
])
def test_exporter_once(mock, script, gw, path, metric):
    text = _once(script, "%s=%s/%s/%s?password=demo" % (gw, mock, gw, path))
    prefix = metric.split("_")[0]
    assert '%s_up{server="%s"} 1.0' % (prefix, gw) in text
    assert metric in text
    assert "password=demo" not in text                      # passwords are never exposed


@pytest.mark.parametrize("script,prefix,path", [
    ("smppbox/smpp_exporter.py", "smppbox", "smppbox-a/status.xml"),
    ("ksmppd/ksmppd_exporter.py", "ksmppd", "ksmppd-a/esme-status.xml"),
    ("kannel/kannel_exporter.py", "kannel", "kannel-a/status.xml"),
])
def test_wrong_password_is_down(mock, script, prefix, path):
    text = _once(script, "gw=%s/%s?password=WRONG" % (mock, path))
    assert '%s_up{server="gw"} 0.0' % prefix in text


@pytest.mark.parametrize("name", ["smppbox", "ksmppd", "kannel"])
def test_dashboard_json(name):
    d = json.loads((ROOT / "dashboards" / ("%s_dashboard.json" % name)).read_text())
    assert d["uid"] and d["title"] and len(d["panels"]) > 50
    exprs = [t.get("expr", "") for p in d["panels"] for t in p.get("targets", [])]
    assert all(e.startswith(("ksmppd", "kannel", "smppbox")) or prefix_ok(e) for e in exprs if e)


def prefix_ok(expr):
    return any(k in expr for k in ("smppbox_", "ksmppd_", "kannel_"))
