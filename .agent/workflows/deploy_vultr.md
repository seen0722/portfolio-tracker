---
description: Deploy Portfolio Tracker to Vultr VPS (Ubuntu)
---

# Deploy Portfolio Tracker to Vultr

This guide assumes you have a Vultr VPS running **Ubuntu 22.04 LTS** or **24.04 LTS**.

## 1. Initial Server Setup

SSH into your server:
```bash
ssh root@<your_server_ip>
```

Update system packages:
```bash
apt update && apt upgrade -y
```

Install essential tools:
```bash
apt install -y python3-pip python3-venv git nginx ufw
```

## 2. Clone the Repository

Navigate to the web root (or your preferred directory):
```bash
cd /var/www
git clone <your_repository_url> portfolio-tracker
cd portfolio-tracker
```
*(Note: If you haven't pushed your code to a remote git repo yet, you can copy the files using `scp` or `rsync` from your local machine)*

## 3. Setup Python Environment

Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## 4. Configure Gunicorn Systemd Service

Create a systemd service file to keep the app running:

```bash
nano /etc/systemd/system/portfolio.service
```

Paste the following configuration (adjust paths if necessary):

```ini
[Unit]
Description=Gunicorn instance to serve Portfolio Tracker
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/portfolio-tracker
Environment="PATH=/var/www/portfolio-tracker/.venv/bin"
Environment="PORTFOLIO_FILE=portfolio.json"
ExecStart=/var/www/portfolio-tracker/.venv/bin/gunicorn --workers 3 --bind unix:portfolio.sock -m 007 dashboard_app:app

[Install]
WantedBy=multi-user.target
```

Start and enable the service:
```bash
systemctl start portfolio
systemctl enable portfolio
systemctl status portfolio
```

## 5. Configure Nginx Reverse Proxy

Create a new Nginx server block:

```bash
nano /etc/nginx/sites-available/portfolio
```

Paste the following:

```nginx
server {
    listen 80;
    server_name <your_domain_or_ip>;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/portfolio-tracker/portfolio.sock;
    }
}
```

Enable the site and restart Nginx:
```bash
ln -s /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled
nginx -t
systemctl restart nginx
```

## 6. Configure Firewall

Allow SSH and HTTP traffic:
```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

## 7. (Optional) SSL with Certbot

If you have a domain name pointing to your IP:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d <your_domain>
```

## 8. Verify

Open your browser and visit `http://<your_server_ip>` (or your domain). You should see the Portfolio Tracker dashboard.
