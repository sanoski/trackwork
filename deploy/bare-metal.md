# Bare-metal install (no Docker)

Debian or Ubuntu commands. Adjust paths for your host.

```bash
# 1. System packages: Python and the libraries WeasyPrint needs for the PDF report
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
  libcairo2 libgdk-pixbuf-2.0-0 libffi8 fonts-dejavu-core shared-mime-info

# 2. A service user and the code
sudo useradd --system --create-home --home-dir /opt/trackwork trackwork
sudo -u trackwork git clone https://github.com/sanoski/trackwork.git /opt/trackwork
cd /opt/trackwork
sudo -u trackwork python3 -m venv .venv
sudo -u trackwork .venv/bin/pip install -r requirements.txt

# 3. Configuration and the first admin account
sudo -u trackwork deploy/setup.sh --bare

# 4. Run it as a service
sudo cp deploy/systemd/trackwork.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now trackwork
sudo systemctl status trackwork

# 5. HTTPS in front of it: Caddy (simplest) or nginx + certbot (deploy/nginx/trackwork.conf.example)
#    Caddy one-liner, as root, with your host name:
#      caddy reverse-proxy --from mow.example.com --to 127.0.0.1:8000
```

Useful commands afterwards:

```bash
sudo journalctl -u trackwork -n 100 -f          # logs
sudo -u trackwork /opt/trackwork/.venv/bin/python /opt/trackwork/scripts/cli.py --help
```
