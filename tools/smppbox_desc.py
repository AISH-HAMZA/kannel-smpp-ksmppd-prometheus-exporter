# Hover (ⓘ) help text for every panel - applied by gen_dashboard.py
DIR = ("\n\nDirection: 'Submit' = submit_sm PDUs the customer sends TO smppbox (MT traffic). "
       "'Deliver' = deliver_sm PDUs smppbox sends TO the customer (delivery reports / MO).")
FILT = "\n\nFollows the Server, SMSC-ID and Customer filters at the top."
SFILT = "\n\nFollows the Server filter only (gateway-wide numbers, not per customer)."
RANGE = " '(range)' means over the time range selected at top-right."
DESC = {
 "Servers UP": "Number of smppbox servers whose status.xml page the exporter could read on its last scrape. "
               "If a server is missing here it is either down or its status page/password is wrong." + SFILT,
 "Servers DOWN": "Number of smppbox servers whose status page could NOT be read (connection refused, timeout, "
                 "bad XML). Anything above 0 needs attention." + SFILT,
 "Submit rate (MT)": "Messages per second customers are submitting to smppbox right now (averaged over the "
                     "graph resolution)." + DIR + FILT,
 "Deliver rate (DLR/MO)": "Messages per second smppbox is delivering back to customers - mostly delivery "
                          "reports (DLRs), plus any MO messages." + DIR + FILT,
 "Failed rate": "Messages per second smppbox counted as failed for the selected customers (rejected, "
                "throttled, invalid, or not acknowledged)." + FILT,
 "Failure %": "Failed messages as a percentage of submitted messages. Green < 2 %, orange 2-5 %, "
              "red > 5 %." + FILT,
 "Submitted (range)": "Total messages submitted by the selected customers during the selected time range." + FILT,
 "Failed (range)": "Total failed messages for the selected customers during the selected time range." + FILT,
 "Customers connected": "Customers that currently have at least one SMPP session bound (any bind type)." + FILT,
 "Customers disconnected": "Customers that are configured (or were recently seen) but have NO session bound "
                           "right now. They cannot send traffic until they reconnect." + FILT,
 "Active sessions": "Total number of SMPP binds (transceiver + transmitter + receiver) currently open by the "
                    "selected customers." + FILT,
 "Open acks": "PDUs sent but not yet acknowledged (in flight). A high or growing value means the customer "
              "or the gateway is slow to respond (window full)." + FILT,
 "Queued msgs": "Messages waiting in smppbox queues (towards bearerbox and towards customers). Should be "
                "near 0; a growing queue means traffic is not flowing out." + SFILT,
 "Store size": "Messages held in the smppbox persistent store (waiting to be processed/resent). Should stay "
               "small." + SFILT,
 "Bearerbox disconnected": "Number of smppbox servers that lost their connection to bearerbox. If > 0 that "
                           "server cannot route any traffic to the operator." + SFILT,
 "smppbox memory": "Total memory used by the smppbox processes of the selected servers." + SFILT,
 "Overall throughput": "Gateway-wide PDUs per second. From ESMEs = submits from all customers; To ESMEs = "
                       "deliveries to customers; To/From bearerbox = traffic between smppbox and bearerbox "
                       "(the operator side)." + SFILT,
 "Submit rate per server": "Customer submit rate split by smppbox server (stacked, so the top line is the "
                           "total)." + SFILT,
 "Deliver (DLR/MO) rate per server": "Deliveries (DLR/MO) to customers per server, stacked." + SFILT,
 "Gateway-reported load (1m avg)": "The load figures smppbox itself prints in status.xml (1-minute average). "
                                   "Use it to cross-check the exporter's own rates." + SFILT,
 "Queues": "Queued messages per server/side/direction and the store size over time. Flat at 0 is healthy." + SFILT,
 "Messages per interval (bars)": "Messages submitted per graph interval per server - handy to see traffic "
                                 "shape through the day." + SFILT,
 "Server health": "One row per smppbox server: reachability, bearerbox link, host, version, response mode, "
                  "uptime, CPU (% of one core over 5 min), memory, configured logins, logins online, active "
                  "sessions, current submit rate, store size and how long the status scrape took." + SFILT,
 "CPU usage (% of one core)": "CPU used by smppbox. 100 % = one full CPU core." + SFILT,
 "Memory": "Memory used by smppbox per server. A steady climb may indicate a leak." + SFILT,
 "Active sessions per server": "Number of SMPP binds open on each server (stacked)." + SFILT,
 "Customer overview": "One row per customer (ESME system-id) per server.\n"
     "Status = CONNECTED if at least one session is bound, else DISCONNECTED.\n"
     "State for = how long the customer has been in that state (since the exporter noticed).\n"
     "Login = smppbox's own online/offline flag for the login.\n"
     "Sessions / Max sessions = bound now / allowed (all bind types).\n"
     "IPs = distinct source IPs bound.\n"
     "Submit/s, Deliver/s = last 5 min rate." + RANGE + "\n"
     "Fail % = failed / submitted. Open acks = in-flight PDUs.\n"
     "Last reconnect = age of the newest session (small = customer reconnected recently)." + DIR + FILT,
 "Top 10 customers by volume (range)": "Customers with the most submitted messages in the selected time range." + FILT,
 "Top 10 customers by failed (range)": "Customers with the most failed messages in the selected time range." + FILT,
 "Top 10 failure % (range, >100 msgs)": "Worst failure percentage per customer. Customers with 100 or fewer "
                                        "messages in the range are excluded to avoid noise." + FILT,
 "Submit rate per customer": "Messages/s each customer is submitting (stacked). Only customers with traffic "
                             "are shown." + DIR + FILT,
 "Deliver (DLR/MO) rate per customer": "Deliveries/s (DLR/MO) sent to each customer (stacked)." + DIR + FILT,
 "Failed rate per customer": "Failed messages per second per customer." + FILT,
 "Failure % per customer": "Failed as % of submitted, per customer, over time." + FILT,
 "Customer connection state (history)": "Green = CONNECTED (at least one bind), red = DISCONNECTED, for "
                                        "every customer over the selected time range. Hover to see exact "
                                        "times of drops and reconnects." + FILT,
 "Active sessions per customer": "Number of binds each customer holds over time (all bind types). Dips "
                                 "mean sessions dropped." + FILT,
 "Open acks (in-flight) per customer": "Unacknowledged PDUs per customer. Should stay low; a plateau at the "
                                       "window size means the link is congested." + FILT,
 "Session utilisation % (bound / allowed)": "Bound sessions compared with the maximum allowed per bind type. "
                                            "100 % = customer is using all allowed sessions and new binds will "
                                            "be rejected." + FILT,
 "Transceiver sessions": "Open TRANSCEIVER binds (trcv). A transceiver bind can both submit messages and "
                         "receive DLR/MO on the same connection." + FILT,
 "Transmitter sessions": "Open TRANSMITTER binds (trans). Transmitter binds can only submit messages; the "
                         "customer needs a receiver bind to get DLRs." + FILT,
 "Receiver sessions": "Open RECEIVER binds (recv). Receiver binds only receive DLR/MO, they never submit." + FILT,
 "Binds (range)": "Number of new SMPP binds (session connects) in the selected range for the selected bind "
                  "types. Frequent binds mean the customer keeps reconnecting." + FILT,
 "Unbinds / drops (range)": "Number of sessions that disappeared (unbind, timeout, network drop) in the "
                            "selected range. Orange > 5, red > 50." + FILT,
 "Open acks (selected types)": "In-flight (unacknowledged) PDUs on the selected bind types." + FILT,
 "Customer stats per bind type": "One row per customer per bind type:\n"
     "Transceiver (trcv) = submit + receive on one bind; Transmitter (trans) = submit only; Receiver (recv) = "
     "DLR/MO only.\nSessions / Max allowed = bound now / allowed for that bind type.\n"
     "Submit/s, Deliver/s = last 5 min." + RANGE + "\nBinds / Drops = connects and disconnects in the range.\n"
     "Oldest / Newest session = age of the longest-lived and the most recent session of that type."
     + DIR + FILT + " Also follows the Bind type filter.",
 "Submit rate by bind type": "Submits per second split by bind type (transmitter vs transceiver). Receiver "
                             "binds never submit, so they stay at 0." + FILT,
 "Deliver (DLR/MO) rate by bind type": "Deliveries per second split by bind type (receiver vs transceiver). "
                                       "Transmitter binds never receive deliveries." + FILT,
 "Active sessions by bind type": "Open sessions per bind type over time (stacked)." + FILT,
 "Binds & drops per customer": "Bars above zero = new binds, bars below zero = sessions dropped, per customer "
                               "and bind type. Useful to spot flapping connections." + FILT,
 "Submit rate per customer & bind type": "Submit rate for each customer split by the bind type carrying it." + FILT,
 "Connections by source IP": "Every source IP each customer is connected from: sessions open from that IP, "
                             "current rates and totals in the range. Sessions = 0 (red) means that IP was used "
                             "recently but is not connected now." + FILT,
 "Submit rate per source IP": "Submit rate per customer source IP - shows how traffic is balanced across a "
                              "customer's servers/IPs." + FILT,
 "Plugin chains": "All plugins loaded in smppbox per trigger chain, in execution order (#). PDU_FROM_ESME = "
                  "runs on PDUs received from customers, PDU_TO_ESME = runs on PDUs sent to customers. State "
                  "should be 'active'." + SFILT,
 "DB pool utilisation % (CDR / prepaid)": "Share of database connections in use for the CDR and prepaid "
                                          "plugins. Near 100 % means the DB is a bottleneck." + SFILT,
 "SQL statements in queue": "CDR SQL statements waiting to be written to the database. Should be 0; a "
                            "growing number means the DB cannot keep up." + SFILT,
 "Inactive plugins": "Plugins whose state is not 'active'. Should be 0." + SFILT,
 "Plugins loaded": "Total plugins loaded across the selected servers." + SFILT,
 "Scrape duration": "How long the exporter needed to download and parse each status.xml. Should be well below "
                    "the scrape interval." + SFILT,
 "Scrape errors / min": "Failed status page reads per minute (network error, timeout, wrong password)." + SFILT,
 "Seconds since last good scrape": "Time since the exporter last read each status page successfully. Grows "
                                   "while a server is unreachable." + SFILT,
}


def _apply(ps):
    for p in ps:
        if p.get("title") in DESC:
            p["description"] = DESC[p["title"]]
        _apply(p.get("panels", []))


_apply(dash["panels"])
_missing = [p["title"] for p in dash["panels"] if p["type"] != "row" and not p.get("description")]
if _missing:
    print("no description:", _missing)

PEAK = (" Inbound = messages the customers submit TO smppbox (submit_sm). Outbound = messages smppbox sends TO "
        "the customers (DLR/MO). 'Peak' = highest 1-minute average msg/s inside the time range selected at "
        "top-right; 'Current' = last minute.")
DESC.update({
 "Gateway / Build Information": "Identity of every smppbox server as reported in its status page: Kannel "
     "product and version, build date, hostname and IP, OS kernel, response mode (ack / immediate) and MySQL "
     "client version. State shows 'running' when smppbox is healthy." + SFILT,
 "Peak Inbound (msg/s)": "Highest inbound rate of all selected servers combined in the selected time range." + PEAK + SFILT,
 "Peak Outbound (msg/s)": "Highest outbound rate of all selected servers combined in the selected time range." + PEAK + SFILT,
 "Current Inbound (msg/s)": "Inbound rate of all selected servers combined, right now." + PEAK + SFILT,
 "Current Outbound (msg/s)": "Outbound rate of all selected servers combined, right now." + PEAK + SFILT,
 "Peak throughput per server": "Peak and current inbound/outbound rate for each smppbox server." + PEAK + SFILT,
 "Peak throughput per server & customer": "Peak and current inbound/outbound rate for each customer on each "
     "server." + PEAK + FILT,
 "Peak throughput per server, customer & session": "Peak and current rate for every single SMPP session "
     "(source IP + port + bind type) of every customer. Rates here are the in/out msg/s that smppbox itself "
     "reports per session. Requires 'per_session_metrics: true' in smpp_exporter.yml." + PEAK + FILT
     + " Also follows the Bind type filter.",
})
_apply(dash["panels"])
