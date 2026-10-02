# Security policy

## Supported versions
Only the latest release receives fixes.

## Reporting a vulnerability
Please **do not open a public issue**. Use GitHub's
[private vulnerability reporting](https://github.com/AISH-HAMZA/smpp-prometheus-exporter/security/advisories/new).
You will get an answer within 7 days.

## Hardening notes
* Status-page passwords live in the exporter config. Keep it readable only by the exporter user
  (`chmod 640`, owned by `root:<exporter group>`) – real configs are git-ignored.
* Passwords are masked (`password=***`) in logs and never appear in `/metrics`.
* `/metrics` has no authentication. Bind to an internal interface (`listen_address`) or firewall ports
  9877-9879 so only Prometheus can reach them.
* Gateway admin ports (13000/14000 …) should only be reachable from the exporter host.
* The Docker image runs as a non-root user; the systemd units use `NoNewPrivileges` and `ProtectSystem`.
