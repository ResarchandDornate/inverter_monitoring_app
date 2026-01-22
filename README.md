## Inverter Monitoring Application

This project is a Django-based backend for monitoring solar inverters.  
It ingests telemetry from an MQTT broker (Mosquitto), stores it in PostgreSQL
(optimized for 15-minute interval data), and exposes real-time and historical 
data over REST APIs and WebSockets.

### Architecture

```mermaid
flowchart TB
  subgraph mqttLayer [MQTT Layer]
    mosquitto[Mosquitto Broker]
    mqttClient[MQTT Client (paho-mqtt)]
  end

  subgraph appLayer [Application Layer]
    validator[Message Validator (services.py)]
    processor[Synchronous Processor]
  end

  subgraph dataLayer [Data Layer]
    postgresDB[(PostgreSQL)]
  end

  subgraph apiLayer [API Layer]
    djangoAPI[Django REST API]
    websocket[WebSocket (Channels)]
  end

  mosquitto -->|MQTT messages| mqttClient
  mqttClient -->|validate & process| validator
  validator -->|synchronous write| processor
  processor -->|write| postgresDB
  djangoAPI -->|read| postgresDB
  websocket -->|real-time updates| mqttClient
```

### Tech Stack

- **Backend**: Django, Django REST Framework, Django Channels
- **Messaging**: Mosquitto (MQTT), paho-mqtt
- **Database**: PostgreSQL (optimized for 15-minute interval time-series data)
- **Auth**: JWT (djangorestframework-simplejwt)

### Cost Optimization

- **No TimescaleDB**: Uses standard PostgreSQL with optimized indexes
- **No Redis**: Synchronous processing eliminates need for message queue
- **Efficient Storage**: Optimized table structure for 15-minute data intervals

### Local Setup

1. Create and activate a virtualenv, then install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file next to `inverter_app_backend/settings.py` with at least:

```bash
SECRET_KEY=your-secret-key
DB_NAME=inverter
DB_USER=inverter
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

3. Run migrations and start services:

```bash
python manage.py migrate
python manage.py runserver
mosquitto -c /etc/mosquitto/mosquitto.conf  # or your local config
```

### AWS Deployment (High Level)

- Use an EC2 instance (t3.small or t3.medium) for Django and Mosquitto.
- Use RDS PostgreSQL (standard instance, no extensions needed) for data storage.
- Terminate HTTPS at an Application Load Balancer or an Nginx reverse proxy.

See `DEPLOYMENT.md` for a step-by-step AWS guide.

