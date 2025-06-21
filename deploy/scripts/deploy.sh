#!/bin/bash


set -e

echo "🚀 Starting CTA Dashboard EC2 Deployment..."

if [ "$EUID" -eq 0 ]; then
    echo "❌ Please do not run this script as root. Run as ec2-user or ubuntu."
    exit 1
fi

APP_DIR="$HOME/dashboard_cta"
SERVICE_NAME="cta-dashboard"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "📦 Updating system packages..."
sudo yum update -y || sudo apt update -y

echo "🐍 Installing Python and dependencies..."
if command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip git
elif command -v apt &> /dev/null; then
    sudo apt install -y python3 python3-pip git
else
    echo "❌ Unsupported package manager. Please install Python3, pip, and git manually."
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "📥 Cloning repository..."
    git clone https://github.com/Blankeeir/dashboard_cta.git "$APP_DIR"
else
    echo "📁 Repository already exists, pulling latest changes..."
    cd "$APP_DIR"
    git pull origin main
fi

cd "$APP_DIR"

echo "📚 Creating virtual environment and installing dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "⚙️  Creating systemd service..."
sudo cp deploy/systemd/cta-dashboard.service "$SERVICE_FILE"

sudo sed -i "s|User=ec2-user|User=$USER|g" "$SERVICE_FILE"
sudo sed -i "s|WorkingDirectory=/home/ec2-user/dashboard_cta|WorkingDirectory=$APP_DIR|g" "$SERVICE_FILE"
sudo sed -i "s|Environment=PATH=/home/ec2-user/dashboard_cta/.venv/bin|Environment=PATH=$APP_DIR/.venv/bin|g" "$SERVICE_FILE"
sudo sed -i "s|Environment=PYTHONPATH=/home/ec2-user/dashboard_cta|Environment=PYTHONPATH=$APP_DIR|g" "$SERVICE_FILE"
sudo sed -i "s|ExecStart=/home/ec2-user/dashboard_cta/.venv/bin/python|ExecStart=$APP_DIR/.venv/bin/python|g" "$SERVICE_FILE"

echo "🔄 Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "🔍 Checking service status..."
sleep 3
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ CTA Dashboard service is running successfully!"
    echo "📊 Dashboard should be accessible at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8501"
else
    echo "❌ Service failed to start. Checking logs..."
    sudo systemctl status "$SERVICE_NAME"
    sudo journalctl -u "$SERVICE_NAME" --no-pager -n 20
    exit 1
fi

echo ""
echo "🛠️  Useful commands:"
echo "  Check status: sudo systemctl status $SERVICE_NAME"
echo "  View logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "  Restart:      sudo systemctl restart $SERVICE_NAME"
echo "  Stop:         sudo systemctl stop $SERVICE_NAME"
echo ""
echo "⚠️  IMPORTANT: Make sure your EC2 Security Group allows inbound traffic on port 8501!"
echo "   AWS Console > EC2 > Security Groups > Your SG > Inbound Rules"
echo "   Add rule: Custom TCP, Port 8501, Source: 0.0.0.0/0"
echo ""
echo "🎉 Deployment completed successfully!"
