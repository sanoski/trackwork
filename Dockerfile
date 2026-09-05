# MOW Tracker: one container runs the web app, the weekly report timer, and (when enabled)
# the MCP server for AI assistants. Debian slim rather than Alpine: WeasyPrint needs Pango.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

# Native libraries WeasyPrint needs to render the PDF report, plus a body font.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
      libcairo2 libgdk-pixbuf-2.0-0 libffi8 fonts-dejavu-core shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /srv/trackwork

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app app/ ./app/
COPY --chown=app:app mcp_server/ ./mcp_server/
COPY --chown=app:app scripts/ ./scripts/

RUN mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/').status == 200 else 1)"

# Exactly one worker: the weekly report timer runs inside the process and must not be duplicated.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
