# CTA Dashboard EC2 Deployment Guide

This directory contains all the necessary files and scripts to deploy the CTA Strategy Dashboard on an EC2 instance.

## Quick Deployment

### Prerequisites
- EC2 instance running Amazon Linux 2, Ubuntu, or similar
- SSH access to the instance
- Security group configured to allow port 8501 (see `scripts/setup-security-group.md`)

### One-Command Deployment

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-ip

# Run the deployment script
curl -sSL https://raw.githubusercontent.com/Blankeeir/dashboard_cta/main/deploy/scripts/deploy.sh | bash
```

### Manual Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Blankeeir/dashboard_cta.git
   cd dashboard_cta
   ```

2. **Run deployment script**:
   ```bash
   chmod +x deploy/scripts/deploy.sh
   ./deploy/scripts/deploy.sh
   ```

## Files Overview

### `systemd/cta-dashboard.service`
Systemd service file that:
- Runs the dashboard as a system service
- Automatically restarts on failure
- Starts on system boot
- Logs to systemd journal

### `scripts/deploy.sh`
Automated deployment script that:
- Installs system dependencies
- Sets up Python environment
- Installs application dependencies
- Configures systemd service
- Starts the dashboard

### `scripts/setup-security-group.md`
Comprehensive guide for configuring AWS Security Groups to allow access on port 8501.

## Post-Deployment

### Access Your Dashboard
```
http://YOUR_EC2_PUBLIC_IP:8501
```

### Service Management
```bash
# Check status
sudo systemctl status cta-dashboard

# View logs
sudo journalctl -u cta-dashboard -f

# Restart service
sudo systemctl restart cta-dashboard

# Stop service
sudo systemctl stop cta-dashboard

# Start service
sudo systemctl start cta-dashboard
```

### Update Dashboard
```bash
cd ~/dashboard_cta
git pull origin main
sudo systemctl restart cta-dashboard
```

## Configuration

### Environment Variables
The service supports these environment variables (set in the systemd service file):
- `ADMIN_PASSWORD`: Override default controller password
- `PYTHONPATH`: Python module search path

### Streamlit Configuration
The dashboard runs with these Streamlit settings:
- `--server.port 8501`: Listen on port 8501
- `--server.address 0.0.0.0`: Accept connections from any IP
- `--server.headless true`: Run without browser auto-open

## Troubleshooting

### Common Issues

1. **Dashboard not accessible**:
   - Check security group allows port 8501
   - Verify service is running: `sudo systemctl status cta-dashboard`
   - Check logs: `sudo journalctl -u cta-dashboard -f`

2. **Service fails to start**:
   - Check Python dependencies: `pip3 list`
   - Verify file permissions
   - Check systemd service file syntax

3. **Performance issues**:
   - Monitor system resources: `htop`
   - Check application logs for errors
   - Consider upgrading EC2 instance type

### Getting Help

1. Check service logs: `sudo journalctl -u cta-dashboard --no-pager -n 50`
2. Verify network connectivity: `curl -I http://localhost:8501`
3. Test Python imports: `python3 -c "import streamlit; print('OK')"`

## Security Notes

- The dashboard includes controller mode authentication
- Consider using HTTPS in production (nginx reverse proxy)
- Restrict security group access to specific IP ranges in production
- Regularly update system packages and Python dependencies

## Architecture

```
Internet → EC2 Security Group (Port 8501) → EC2 Instance → Systemd Service → Streamlit App
```

The deployment creates a robust, production-ready setup that automatically handles:
- Service restarts on failure
- System boot startup
- Logging and monitoring
- Process management
