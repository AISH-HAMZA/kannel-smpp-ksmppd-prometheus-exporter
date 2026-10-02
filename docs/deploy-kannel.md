# Deploy the Kannel bearerbox exporter

Monitor Kannel 1.4.x (Debian/Ubuntu `apt install kannel`), SVN builds and Kannel-HA with Prometheus and Grafana. Pick **one** of the two ways below – both take about 5 minutes.

| | Same node | Central |
|---|---|---|
| Where the exporter runs | on **each** Kannel bearerbox server | on **one** monitoring server |
| It reads | `127.0.0.1:13000/status.xml` | every server's `/status.xml` over the network |
| Use it when | one server, or the admin port must stay closed | several servers – one place to manage ⭐ |
| Prometheus scrapes | every gateway server `:9879` | only the monitoring server `:9879` |

## Before you start (both ways)

1. Find the admin port and status password: `kannel.conf` → `group = core` → `admin-port` and `status-password` (or `admin-password`).
2. Check the status page answers (on the gateway server):

   ```bash
   curl -s "http://127.0.0.1:13000/status.xml?password=STATUS_PASSWORD" | head -5
   ```

   You should see XML. `Denied` = wrong password. No answer = wrong port.
3. Get the code on the server that will run the exporter:

   ```bash
   git clone https://github.com/AISH-HAMZA/kannel-smpp-ksmppd-prometheus-exporter.git
   cd kannel-smpp-ksmppd-prometheus-exporter
   ```

## Way 1 – same node (exporter on the Kannel bearerbox server)

```bash
sudo ./deploy/install.sh kannel --local --password 'STATUS_PASSWORD'
```

Different port or HTTPS? Give the full URL instead: `--url "https://127.0.0.1:13000/status.xml?password=..."`.
Repeat on every Kannel bearerbox server, then list them all in Prometheus:

```yaml
  - job_name: kannel_exporter
    static_configs:
      - targets: ['192.0.2.30:9879', '192.0.2.31:9879']
```

## Way 2 – central (one monitoring server for all Kannel bearerbox servers) ⭐

On the monitoring server:

```bash
sudo ./deploy/install.sh kannel   --target kannel-a=http://192.0.2.30:13000/status.xml?password=STATUS_PASSWORD   --target kannel-b=http://192.0.2.31:13000/status.xml?password=STATUS_PASSWORD
```

`kannel-a` is the name you will see in Grafana – keep it short and stable. Allow the monitoring server to reach
port 13000 on every gateway. Prometheus only needs one target:

```yaml
  - job_name: kannel_exporter
    static_configs:
      - targets: ['MONITORING_SERVER_IP:9879']
```

Add or remove gateways later: edit `/opt/smpp-exporter/kannel/config.yml`, then `sudo systemctl reload kannel_exporter`.

## Docker instead of systemd (either way)

```bash
cp exporters/kannel/config.example.yml /etc/kannel-exporter.yml        # edit targets + passwords
docker build -f deploy/docker/Dockerfile -t kannel-smpp-ksmppd-prometheus-exporter .
docker run -d --name kannel-exporter --restart unless-stopped --network host   -e EXPORTER=kannel -v /etc/kannel-exporter.yml:/etc/smpp-exporter/config.yml:ro kannel-smpp-ksmppd-prometheus-exporter
```

(`--network host` lets the container reach `127.0.0.1` in same-node mode.)

## Finish: Prometheus, Grafana, alerts

1. Add the `job_name` block above to `prometheus.yml` under `scrape_configs:` and reload Prometheus.
   *Status → Targets* must show `kannel_exporter` as **UP**.
2. Grafana → *Dashboards → New → Import* → upload [`dashboards/kannel_dashboard.json`](../dashboards/kannel_dashboard.json) → pick
   your Prometheus data source.
3. Optional alerts: copy [`alerts/kannel_alerts.yml`](../alerts/kannel_alerts.yml) next to `prometheus.yml` and add it under `rule_files:`.

## Check it works

```bash
systemctl status kannel_exporter
curl -s localhost:9879/metrics | grep kannel_up        # 1 = gateway OK, 0 = see the log
journalctl -u kannel_exporter -n 30
```

## Update or remove

```bash
cd kannel-smpp-ksmppd-prometheus-exporter && git pull && sudo ./deploy/install.sh kannel        # updates the code, keeps your config
sudo ./deploy/install.sh kannel --uninstall            # add --purge to also delete the config
```

All settings: [configuration.md](configuration.md) · Problems: [troubleshooting.md](troubleshooting.md) ·
Metrics: [metrics.md](metrics.md) · Exporter details: [exporters/kannel](../exporters/kannel/README.md)

## What you get

![Kannel bearerbox Grafana dashboard: overview](images/kannel-overview.png)
![Kannel bearerbox Grafana dashboard: gateways peak throughput](images/kannel-gateways-peak-throughput.png)
![Kannel bearerbox Grafana dashboard: smsc links](images/kannel-smsc-links.png)
![Kannel bearerbox Grafana dashboard: SMSC username overview](images/kannel-smsc-username-overview.png)
![Kannel bearerbox Grafana dashboard: traffic per server](images/kannel-traffic-per-server.png)
