#!/bin/bash

# Portfolio Tracker Deployment Script for Ubuntu VPS
# Usage: sudo ./deploy.sh <repo_url> <server_ip_or_domain>

REPO_URL=$1
DOMAIN=$2

if [ -z "$REPO_URL" ] || [ -z "$DOMAIN" ]; then
    echo "Usage: sudo ./deploy.sh <repo_url> <server_ip_or_domain>"
    exit 1
fi

echo ">>> Updating system..."
apt update && apt upgrade -y

echo ">>> Installing dependencies..."
apt install -y python3-pip python3-venv git nginx ufw certbot python3-certbot-nginx

echo ">>> Setting up application directory..."
cd /var/www
if [ -d "portfolio-tracker" ]; then
    echo "Directory exists, pulling latest changes..."
    cd portfolio-tracker
    git pull
else
    git clone "$REPO_URL" portfolio-tracker
    cd portfolio-tracker
fi

echo ">>> Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo ">>> Configuring Systemd Service..."
cat > /etc/systemd/system/portfolio.service <<EOL
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
EOL

systemctl daemon-reload
systemctl start portfolio
systemctl enable portfolio
systemctl restart portfolio

echo ">>> Configuring Nginx..."
cat > /etc/nginx/sites-available/portfolio <<EOL
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/portfolio-tracker/portfolio.sock;
    }
}
EOL

ln -sf /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ">>> Configuring Firewall..."
ufw allow 'Nginx Full'
ufw allow OpenSSH
ufw --force enable

echo ">>> Setting up HTTPS with Certbot..."
certbot --nginx -d $DOMAIN -d www.$DOMAIN

echo ">>> Deployment Complete! Visit http://$DOMAIN"
