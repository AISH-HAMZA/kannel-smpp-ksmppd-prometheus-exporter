"""Parser tests against the fictional sample pages in examples/pages (regenerate with mock_gateway.py --dump)."""
import pytest


# --------------------------------------------------------------------------- smppbox
def test_smppbox_info(smppbox, page):
    d = smppbox.parse_status_xml(page("smppbox_status.xml"))
    assert d["info"]["version"] == "1.5.0"
    assert d["info"]["hostname"] == "smppbox-a"
    assert d["info"]["host_ip"] == "192.0.2.10"
    assert d["info"]["mysql_client"] == "8.0.36"
    assert d["state"] == "running"
    assert d["uptime"] > 86400
    assert d["memory"] > 300 * 1024 ** 2


def test_smppbox_logins_and_sessions(smppbox, page):
    d = smppbox.parse_status_xml(page("smppbox_status.xml"))
    logins = {x["esme"]: x for x in d["logins"]}
    assert set(logins) == {"customer-001", "customer-002", "customer-003", "customer-004", "customer-005"}
    assert logins["customer-001"]["online"] == 1.0
    assert logins["customer-005"]["online"] == 0.0
    assert logins["customer-001"]["sessions"]["trcv"] == (2.0, 4.0)
    assert logins["customer-001"]["sessions"]["trans"] == (0.0, 2.0)   # "-/2" means none bound
    s = d["sessions"][0]
    assert s["type"] == "trcv" and s["state"] == "online"
    assert s["rcvd"] > 0 and s["sent"] > 0 and s["in_rate"] > 0


def test_smppbox_plugins(smppbox, page):
    d = smppbox.parse_status_xml(page("smppbox_status.xml"))
    p = d["chains"][0]["plugins"][0]
    assert d["chains"][0]["chain"] == "submit_sm"
    assert p["plugin"] == "mysql-log" and p["db_max"] == 10.0 and p["sql_queue"] is not None


def test_smppbox_helpers(smppbox):
    assert smppbox.parse_duration("1d 2h 3m 4s") == 93784
    assert smppbox.parse_cpu("1:02:03.5") == 3723.5
    assert smppbox.parse_size("1.5K") == 1536
    assert smppbox.parse_triplet("1.5,2,3.25") == [1.5, 2.0, 3.25]
    assert "secret" not in smppbox.mask_url("http://h:1/status.xml?password=secret")


def test_smppbox_rejects_garbage(smppbox):
    with pytest.raises(ValueError):
        smppbox.parse_status_xml(b"Denied")


def _sess(port, rcvd, online):
    return {"esme": "customer-001", "ip": "203.0.113.10", "port": str(port), "type": "trcv", "state": "online",
            "online": online, "rcvd": rcvd, "sent": rcvd, "failed": 0, "resp": 0, "open_acks": 0,
            "in_rate": 0, "out_rate": 0}


@pytest.fixture
def acc(smppbox):
    return smppbox.SessionAccumulator(tolerance=30, retention=86400, interval=15, max_rate=20000)


def test_accumulator_first_scrape_is_baseline(acc):
    acc.update([_sess(40001, 1_000_000_000, 90000)], now=1000)   # huge history after exporter restart
    assert acc.esme["customer-001"][0] == 0                       # no billion-size burst
    acc.update([_sess(40001, 1_000_000_150, 90015)], now=1015)
    assert acc.esme["customer-001"][0] == 150


def test_accumulator_reconnect_counts_new_session_from_zero(acc):
    acc.update([_sess(40001, 5000, 9000)], now=1000)
    acc.update([_sess(40001, 5100, 9015)], now=1015)
    acc.update([_sess(40002, 20, 10)], now=1030)                  # re-bind: counters restart at 0
    assert acc.esme["customer-001"][0] == 120
    assert acc.events[("customer-001", "trcv")] == [1.0, 1.0]     # one connect, one disconnect


def test_accumulator_session_gap_is_not_recounted(acc):
    acc.update([_sess(40001, 5000, 9000)], now=1000)
    acc.update([_sess(40001, 5100, 9015)], now=1015)
    acc.update([], now=1030)                                       # missing from one scrape (glitch)
    acc.update([_sess(40001, 5200, 9045)], now=1045)               # comes back: only +100, not +5200
    assert acc.esme["customer-001"][0] == 200


def test_accumulator_caps_impossible_jump(acc):
    acc.update([_sess(40001, 0, 9000)], now=1000)
    acc.update([_sess(40001, 10_000_000_000, 9015)], now=1015)    # > max_rate * window -> glitch
    assert acc.esme["customer-001"][0] == 0


# --------------------------------------------------------------------------- ksmppd
def test_ksmppd_xml(ksmppd, page):
    d = ksmppd.parse_status(page("ksmppd_esme-status.xml"))
    assert d["summary"]["unique"] == 4
    e = {x["id"]: x for x in d["esmes"]}
    assert e["ESME_DEMO_01"]["limit"] == 100
    assert len(e["ESME_DEMO_01"]["binds"]) == 2
    assert {b["type"] for b in e["ESME_DEMO_01"]["binds"]} == {"trx", "rx"}


def test_ksmppd_text_matches_xml(ksmppd, page):
    a = ksmppd.parse_status(page("ksmppd_esme-status.xml"))
    b = ksmppd.parse_status(page("ksmppd_esme-status.txt"))
    assert a["summary"]["unique"] == b["summary"]["unique"]
    for x, y in zip(a["esmes"], b["esmes"]):
        assert (x["id"], x["mt"], x["mo"], x["dlr"], x["errors"], x["limit"]) == \
               (y["id"], y["mt"], y["mo"], y["dlr"], y["errors"], y["limit"])
        assert len(x["binds"]) == len(y["binds"])


def test_ksmppd_denied_and_urls(ksmppd):
    with pytest.raises(ValueError, match="Denied"):
        ksmppd.parse_status(b"Denied")
    assert ksmppd.uptime_url("http://h:14000/esme-status.xml?password=x") == "http://h:14000/uptime.xml?password=x"
    assert ksmppd.btype("3") == "trx" and ksmppd.btype("1") == "tx" and ksmppd.btype("2") == "rx"


# --------------------------------------------------------------------------- kannel
def test_kannel_vanilla(kannel, page):
    d = kannel.parse_status(page("kannel_status.xml"))
    assert d["info"]["version"] == "1.4.5"
    assert d["info"]["flavour"] == "kannel" and d["info"]["build_type"] == "release"
    links = [s["link"] for s in d["smscs"]]
    assert links.count("operator-a") == 1 and "operator-a#2" in links   # instances = 2 -> unique keys
    assert d["boxes"][0]["online"] == 1.0 and d["boxes"][0]["ha"] is False


def test_kannel_ha(kannel, page):
    d = kannel.parse_status(page("kannel-ha_status.xml"))
    assert d["info"]["flavour"] == "kannel-ha" and d["info"]["build_type"] == "svn"
    assert d["sms"]["ha_route"] is not None
    assert d["boxes"][0]["ha"] is True and "open_acks" in d["boxes"][0]


def test_kannel_smsc_name(kannel):
    c = kannel.parse_smsc_name("SMPP:198.51.100.7:2775/2776:ESME_DEMO_01:smpp")
    assert c == {"protocol": "SMPP", "host": "198.51.100.7", "port": "2775", "receive_port": "2776",
                 "username": "ESME_DEMO_01", "system_type": "smpp"}
    assert kannel.parse_smsc_name("FAKE:10001")["username"] == "(none)"


@pytest.mark.parametrize("body", [b"<gateway>Denied</gateway>", b"Denied"])
def test_kannel_denied(kannel, body):
    with pytest.raises(ValueError):
        kannel.parse_status(body)
