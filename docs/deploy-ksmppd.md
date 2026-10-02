# Deploy the KSMPPD exporter

Monitor KSMPPD (XML `esme-status.xml` or plain-text `esme-status`) with Prometheus and Grafana. Pick **one** of the two ways below – both take about 5 minutes.

| | Same node | Central |
|---|---|---|
| Where the exporter runs | on **each** KSMPPD server | on **one** monitoring server |
| It reads | `127.0.0.1:14000/esme-status.xml` | every server's `/esme-status.xml` over the network |
| Use it when | one server, or the admin port must stay closed | several servers – one place to manage ⭐ |
| Prometheus scrapes | every gateway server `:9878` | only the monitoring server `:9878` |

## Before you start (both ways)

1. Find the admin port and status password: your KSMPPD config: the HTTP admin port and its password.
2. Check the status page answers (on the gateway server):

   ```bash
   curl -s "http://127.0.0.1:14000/esme-status.xml?password=STATUS_PASSWORD" | head -5
   ```

   You should see XML. `Denied` = wrong password. No answer = wrong port.
3. Get the code on the server that will run the exporter:

   ```bash
   git clone https://github.com/AISH-HAMZA/smpp-prometheus-exporter.git
   cd smpp-prometheus-exporter
   ```

## Way 1 – same node (exporter on the KSMPPD server)

```bash
sudo ./deploy/install.sh ksmppd --local --password 'STATUS_PASSWORD'
```

Different port or HTTPS? Give the full URL instead: `--url "https://127.0.0.1:14000/esme-status.xml?password=..."`.
Repeat on every KSMPPD server, then list them all in Prometheus:

```yaml
  - job_name: ksmppd_exporter
    static_configs:
      - targets: ['192.0.2.20:9878', '192.0.2.21:9878']
```

## Way 2 – central (one monitoring server for all KSMPPD servers) ⭐

On the monitoring server:

```bash
sudo ./deploy/install.sh ksmppd   --target ksmppd-a=http://192.0.2.20:14000/esme-status.xml?password=STATUS_PASSWORD   --target ksmppd-b=http://192.0.2.21:14000/esme-status.xml?password=STATUS_PASSWORD
```

`ksmppd-a` is the name you will see in Grafana – keep it short and stable. Allow the monitoring server to reach
port 14000 on every gateway. Prometheus only needs one target:

```yaml
  - job_name: ksmppd_exporter
    static_configs:
      - targets: ['MONITORING_SERVER_IP:9878']
```

Add or remove gateways later: edit `/opt/smpp-exporter/ksmppd/config.yml`, then `sudo systemctl reload ksmppd_exporter`.

## Docker instead of systemd (either way)

```bash
cp exporters/ksmppd/config.example.yml /etc/ksmppd-exporter.yml        # edit targets + passwords
docker build -f deploy/docker/Dockerfile -t smpp-prometheus-exporter .
docker run -d --name ksmppd-exporter --restart unless-stopped --network host   -e EXPORTER=ksmppd -v /etc/ksmppd-exporter.yml:/etc/smpp-exporter/config.yml:ro smpp-prometheus-exporter
```

(`--network host` lets the container reach `127.0.0.1` in same-node mode.)

## Finish: Prometheus, Grafana, alerts

1. Add the `job_name` block above to `prometheus.yml` under `scrape_configs:` and reload Prometheus.
   *Status → Targets* must show `ksmppd_exporter` as **UP**.
2. Grafana → *Dashboards → New → Import* → upload [`dashboards/ksmppd_dashboard.json`](../dashboards/ksmppd_dashboard.json) → pick
   your Prometheus data source.
3. Optional alerts: copy [`alerts/ksmppd_alerts.yml`](../alerts/ksmppd_alerts.yml) next to `prometheus.yml` and add it under `rule_files:`.

## Check it works

```bash
systemctl status ksmppd_exporter
curl -s localhost:9878/metrics | grep ksmppd_up        # 1 = gateway OK, 0 = see the log
journalctl -u ksmppd_exporter -n 30
```

## Update or remove

```bash
cd smpp-prometheus-exporter && git pull && sudo ./deploy/install.sh ksmppd        # updates the code, keeps your config
sudo ./deploy/install.sh ksmppd --uninstall            # add --purge to also delete the config
```

All settings: [configuration.md](configuration.md) · Problems: [troubleshooting.md](troubleshooting.md) ·
Metrics: [metrics.md](metrics.md) · Exporter details: [exporters/ksmppd](../exporters/ksmppd/README.md)

## What you get

![KSMPPD Grafana dashboard: overview tps limits](images/ksmppd-overview-tps-limits.png)
![KSMPPD Grafana dashboard: servers peak throughput](images/ksmppd-servers-peak-throughput.png)
![KSMPPD Grafana dashboard: customers overview](images/ksmppd-customers-overview.png)
![KSMPPD Grafana dashboard: customer traffic errors](images/ksmppd-customer-traffic-errors.png)
![KSMPPD Grafana dashboard: binds sessions](images/ksmppd-binds-sessions.png)
