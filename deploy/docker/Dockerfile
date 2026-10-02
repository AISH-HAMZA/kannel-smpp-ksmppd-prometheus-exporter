# One image for all three exporters. Pick one at runtime with EXPORTER=smppbox|ksmppd|kannel
# (or at build time: --build-arg EXPORTER=kannel).  Build from the repository root:
#   docker build -f deploy/docker/Dockerfile -t kannel-smpp-ksmppd-prometheus-exporter .
FROM python:3.12-slim

ARG EXPORTER=kannel
ENV EXPORTER=${EXPORTER} \
    CONFIG=/etc/smpp-exporter/config.yml \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && useradd --system --uid 10001 --no-create-home exporter

WORKDIR /app
COPY exporters/ /app/exporters/
COPY examples/mock_gateway.py /app/examples/mock_gateway.py
COPY deploy/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod 0755 /app/entrypoint.sh

USER exporter
EXPOSE 9877 9878 9879 8080

# The exporter port follows the exporter type (smppbox 9877, ksmppd 9878, kannel 9879).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request as u; p={'smppbox':9877,'ksmppd':9878,'kannel':9879,'mock':8080}[os.environ['EXPORTER']]; u.urlopen('http://127.0.0.1:%d/%s' % (p, 'healthz' if p == 8080 else 'metrics'), timeout=4)"

ENTRYPOINT ["/app/entrypoint.sh"]
