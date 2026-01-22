## AWS Deployment Guide

This document describes how to deploy the inverter monitoring backend on AWS
in a cost-effective but production-ready way.

### 1. Components

- **EC2**: Django app, Mosquitto broker
- **RDS PostgreSQL**: primary database (standard PostgreSQL, no extensions needed)
- **(Optional) Application Load Balancer**: HTTPS termination and routing

**Note**: Redis and TimescaleDB have been removed for cost optimization. 
MQTT messages are processed synchronously.

### 2. EC2 Setup

1. Launch an EC2 instance (Ubuntu 22.04, type `t3.small` or `t3.medium`).
2. Open security groups:
   - SSH (22) from your IP.
   - HTTP (80) and HTTPS (443) from the internet (or via ALB).
   - MQTT port (1883) from your devices/VPC only.
3. Install system packages:

```bash
sudo apt update
sudo apt install -y git python3-pip python3-venv docker.io docker-compose
```

4. Clone your repository and configure `.env` with RDS credentials.

### 3. RDS PostgreSQL

1. Create an RDS PostgreSQL instance (db.t3.micro or db.t3.small).
2. No special extensions needed - standard PostgreSQL is sufficient.
3. Set the `DB_*` environment variables in `.env` to point to your RDS instance.

**Database Optimization Tips**:
- Enable automated backups with 7-day retention
- Configure connection pooling if needed
- Monitor storage usage and set up auto-scaling
- Consider partitioning old data (>1 year) to reduce costs

### 4. Running the Application

- Apply migrations:

```bash
python manage.py migrate
```

- Start Django (via gunicorn or uvicorn behind Nginx/ALB).
- Start Mosquitto using your configuration pointing devices to the EC2 public/VPC address.

**Note**: No Celery workers needed - MQTT messages are processed synchronously.

### 5. Logging & Monitoring

- Send Django logs to CloudWatch via the CloudWatch agent or ship `logs/application.log`.
- Set CloudWatch alarms on:
  - EC2 CPU, memory (via agent).
  - RDS CPU, connections, storage.
- Optionally add Prometheus + Grafana for detailed application metrics.

### 6. Cost Optimisation Tips

- Use small instances (t3 family) and monitor utilisation before scaling up.
- Prefer 1‑year Reserved Instances for EC2 and RDS to cut cost.
- Configure RDS storage auto-scaling and backups with 7–14 day retention.
- Offload old logs to S3 and rotate them aggressively.
- **No Redis/ElastiCache costs** - synchronous processing eliminates message queue
- **No TimescaleDB licensing** - standard PostgreSQL is sufficient for 15-minute intervals
- Consider archiving data older than 1 year to S3 to reduce database storage costs
- Use autoscaling groups for EC2 if you expect variable load.

