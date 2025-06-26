# EC2 Security Group Configuration for CTA Dashboard

## Required Security Group Rules

To make your CTA Dashboard accessible at `http://<EC2-public-IP>:8501`, you need to configure your EC2 Security Group to allow inbound traffic on port 8501.

### AWS Console Method

1. **Navigate to EC2 Console**
   - Go to AWS Console > EC2 > Security Groups
   - Find your instance's security group

2. **Add Inbound Rule**
   - Click "Edit inbound rules"
   - Click "Add rule"
   - Configure the rule:
     - **Type**: Custom TCP
     - **Port range**: 8501
     - **Source**: 0.0.0.0/0 (for public access) or your specific IP range
     - **Description**: CTA Dashboard Streamlit Port

3. **Save Rules**
   - Click "Save rules"

### AWS CLI Method

```bash
# Get your security group ID
SECURITY_GROUP_ID=$(aws ec2 describe-instances \
  --instance-ids YOUR_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)

# Add inbound rule for port 8501
aws ec2 authorize-security-group-ingress \
  --group-id $SECURITY_GROUP_ID \
  --protocol tcp \
  --port 8501 \
  --cidr 0.0.0.0/0
```

### Terraform Configuration

```hcl
resource "aws_security_group_rule" "cta_dashboard" {
  type              = "ingress"
  from_port         = 8501
  to_port           = 8501
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = var.security_group_id
  description       = "CTA Dashboard Streamlit Port"
}
```

## Security Considerations

### Production Deployment
For production environments, consider restricting access:

```bash
# Allow access only from your office IP
--cidr YOUR_OFFICE_IP/32

# Allow access from specific IP range
--cidr 10.0.0.0/8
```

### Additional Security Measures
1. **Use HTTPS**: Consider setting up a reverse proxy (nginx) with SSL
2. **Authentication**: The dashboard has built-in controller mode authentication
3. **VPC**: Deploy in a private subnet with NAT gateway if possible
4. **Monitoring**: Enable CloudWatch logs and monitoring

## Verification

After configuring the security group:

1. **Check port accessibility**:
   ```bash
   # From your local machine
   telnet YOUR_EC2_PUBLIC_IP 8501
   ```

2. **Test dashboard access**:
   ```bash
   curl -I http://YOUR_EC2_PUBLIC_IP:8501
   ```

3. **Access in browser**:
   ```
   http://YOUR_EC2_PUBLIC_IP:8501
   ```

## Troubleshooting

If the dashboard is not accessible:

1. **Check security group rules**: Ensure port 8501 is open
2. **Check service status**: `sudo systemctl status cta-dashboard`
3. **Check local firewall**: `sudo iptables -L` (usually not an issue on EC2)
4. **Check application logs**: `sudo journalctl -u cta-dashboard -f`
5. **Verify Streamlit is binding to 0.0.0.0**: Check service configuration
