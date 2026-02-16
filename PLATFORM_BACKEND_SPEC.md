# Agora Platform Backend Specification

## Overview

This document specifies the backend services for the Agora AI Platform.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGORA PLATFORM                            │
├─────────────────────────────────────────────────────────────┤
│  API Gateway (Rate limiting, Auth)                          │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Auth    │  Hub     │ Exchange │  Class   │  Progress       │
│  Service │  Service │ Service  │  Service │  Service        │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│  Database (PostgreSQL) + Cache (Redis)                      │
├─────────────────────────────────────────────────────────────┤
│  Message Queue (RabbitMQ/SQS)                               │
├─────────────────────────────────────────────────────────────┤
│  Object Storage (S3) - Class packs, manifests               │
└─────────────────────────────────────────────────────────────┘
```

## Services

### 1. Auth Service

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Login with email/phone |
| POST | `/auth/refresh` | Refresh auth token |
| POST | `/auth/logout` | Logout |
| POST | `/auth/device/bind` | Bind device to account |
| POST | `/auth/device/unbind` | Unbind device |
| GET | `/auth/device/list` | List bound devices |

**Data Model:**
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50) UNIQUE,
    public_handle VARCHAR(50) NOT NULL,
    public_key_id VARCHAR(64),
    privacy_mode BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP
);

CREATE TABLE devices (
    device_id VARCHAR(64) PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    device_pubkey_id VARCHAR(64),
    manifest_hash VARCHAR(64),
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Hub Service

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hubs` | List hubs near location |
| GET | `/hubs/{hub_id}` | Get hub details |
| POST | `/hubs/propose` | Propose new hub |
| POST | `/hubs/{hub_id}/vote` | Vote on hub |
| GET | `/hubs/pending` | List pending proposals (mod) |
| POST | `/hubs/{hub_id}/approve` | Approve hub (mod) |

**Data Model:**
```sql
CREATE TABLE hubs (
    hub_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    hub_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    safety_tags TEXT[],
    rating DECIMAL(2, 1) DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    reliability_score DECIMAL(3, 2) DEFAULT 0,
    created_by VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE hub_votes (
    vote_id UUID PRIMARY KEY,
    hub_id VARCHAR(64) REFERENCES hubs(hub_id),
    user_id UUID REFERENCES users(user_id),
    vote_type VARCHAR(20), -- 'up', 'down'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE hub_operating_hours (
    hub_id VARCHAR(64) REFERENCES hubs(hub_id),
    day_of_week INTEGER,
    open_time TIME,
    close_time TIME,
    PRIMARY KEY (hub_id, day_of_week)
);
```

### 3. Exchange Service

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/exchange/log` | Log exchange event |
| GET | `/exchange/history` | Get exchange history |
| GET | `/exchange/credits` | Get credit balance |
| POST | `/exchange/credits/grant` | Grant credits (internal) |
| GET | `/exchange/lockout/{partner_hash}` | Check lockout status |

**Data Model:**
```sql
CREATE TABLE exchange_events (
    event_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    partner_hash VARCHAR(64) NOT NULL,
    hub_id VARCHAR(64) REFERENCES hubs(hub_id),
    event_timestamp TIMESTAMP,
    categories_gained TEXT[],
    artifacts_count INTEGER,
    credits_earned INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE credits_ledger (
    ledger_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    transaction_type VARCHAR(20), -- 'earn', 'spend'
    amount INTEGER,
    balance_after INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE partner_lockouts (
    user_id UUID REFERENCES users(user_id),
    partner_hash VARCHAR(64),
    first_exchange_date DATE,
    last_exchange_date DATE,
    total_exchanges INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, partner_hash)
);
```

**Credit Calculation:**
```python
def calculate_credits(user_id, partner_hash, categories_count, linger_seconds):
    # Base credits
    base = 10
    
    # Novelty multiplier
    partner_stats = get_partner_stats(user_id, partner_hash)
    novelty_mult = partner_stats['novelty_score'] / 2.0  # 0.5 to 1.5
    
    # Linger bonus
    linger_bonus = min(linger_seconds, 30) / 10
    
    # Categories bonus
    categories_bonus = categories_count * 2
    
    return int((base + linger_bonus + categories_bonus) * novelty_mult)
```

### 4. Class Service

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/classes` | List available classes |
| GET | `/classes/{class_id}` | Get class details |
| POST | `/classes/{class_id}/enroll` | Enroll in class |
| GET | `/classes/{class_id}/pack` | Get signed class pack |
| POST | `/classes/{class_id}/complete` | Mark class complete |
| GET | `/classes/enrolled` | List enrolled classes |

**Data Model:**
```sql
CREATE TABLE classes (
    class_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    class_type VARCHAR(50),
    cost INTEGER,
    duration_minutes INTEGER,
    outputs TEXT[],
    requirements JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE class_packs (
    pack_id UUID PRIMARY KEY,
    class_id VARCHAR(64) REFERENCES classes(class_id),
    schema_version VARCHAR(10),
    artifacts JSONB,
    policy JSONB,
    signature VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_classes (
    user_id UUID REFERENCES users(user_id),
    class_id VARCHAR(64) REFERENCES classes(class_id),
    enrolled_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'enrolled',
    PRIMARY KEY (user_id, class_id)
);
```

**Class Types:**
| Type | Description | Outputs |
|------|-------------|---------|
| language_nuance | Language pattern refinement | lexical_patterns, template_quality |
| phonetic | Voice clarity training | voice_params |
| conversation | Dialogue flow enhancement | hybrid_intents, response_patterns |
| visual | Visual recognition practice | vision_params |
| balance | Social balance training | voice_params, behavior_patterns |

### 5. Progress Service

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/progress/manifest` | Sync capability manifest |
| GET | `/progress/manifest` | Get current manifest |
| POST | `/progress/achievements` | Sync achievements |
| GET | `/progress/achievements` | Get achievements |
| GET | `/progress/specialization` | Get specialization radar |
| GET | `/progress/stats` | Get overall stats |

**Data Model:**
```sql
CREATE TABLE capability_manifests (
    manifest_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    device_id VARCHAR(64),
    fingerprint VARCHAR(64),
    template_version VARCHAR(20),
    hybrid_version VARCHAR(20),
    voice_version VARCHAR(20),
    vision_version VARCHAR(20),
    audio_version VARCHAR(20),
    policy_version VARCHAR(20),
    specialization JSONB,
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE achievements (
    achievement_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    achievement_type VARCHAR(50),
    earned_at TIMESTAMP,
    metadata JSONB
);

CREATE TABLE specialization_progress (
    progress_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    domain VARCHAR(50),
    current_value DECIMAL(3, 2),
    max_value DECIMAL(3, 2),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 6. Notification Service (Optional)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/notifications/register` | Register push token |
| POST | `/notifications/unregister` | Unregister push token |
| GET | `/notifications/settings` | Get notification settings |
| POST | `/notifications/settings` | Update settings |

## API Response Format

All API responses follow this format:

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": 1234567890,
    "request_id": "req_..."
  },
  "error": null
}
```

Error response:
```json
{
  "success": false,
  "data": null,
  "meta": {
    "timestamp": 1234567890,
    "request_id": "req_..."
  },
  "error": {
    "code": "INVALID_REQUEST",
    "message": "...",
    "details": { ... }
  }
}
```

## Authentication

### Token-based Auth
1. User logs in with email/phone + password
2. Server returns `auth_token` (JWT) + `refresh_token`
3. Client includes `Authorization: Bearer {token}` header
4. Token expires after 24 hours
5. Use `refresh_token` to get new `auth_token`

### Device Binding
1. Platform app shows QR with: `user_id`, `auth_token`
2. Device scans QR
3. Device calls `/auth/device/bind` with:
   - `device_id`
   - `device_pubkey_id`
   - `manifest_hash`
4. Server stores device binding

## Signed Pack Infrastructure

### Platform Signing Key
- RSA-2048 key pair
- Private key stored in HSM/KMS
- Public key distributed to devices
- Key rotation every 90 days

### Class Pack Signature
```python
import hashlib
import rsa

def sign_class_pack(pack_data, private_key):
    # Canonicalize pack data
    canonical = json.dumps(pack_data, sort_keys=True)
    
    # Hash
    pack_hash = hashlib.sha256(canonical.encode()).hexdigest()
    
    # Sign
    signature = rsa.sign(pack_hash.encode(), private_key, 'SHA-256')
    
    return base64.b64encode(signature).decode()

def verify_class_pack(pack_data, signature, public_key):
    canonical = json.dumps(pack_data, sort_keys=True)
    pack_hash = hashlib.sha256(canonical.encode()).hexdigest()
    
    try:
        rsa.verify(pack_hash.encode(), base64.b64decode(signature), public_key)
        return True
    except rsa.VerificationError:
        return False
```

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/auth/*` | 10 req/min |
| `/hubs/*` | 100 req/min |
| `/exchange/log` | 10 req/min |
| `/classes/*` | 50 req/min |
| `/progress/*` | 100 req/min |

## Deployment

### Docker Compose (Development)
```yaml
version: '3.8'
services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://..."
      - REDIS_URL=redis://redis:6379
  
  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
  
  rabbitmq:
    image: rabbitmq:3-alpine
```

### Kubernetes (Production)
- Horizontal Pod Autoscaler (min: 3, max: 20)
- Ingress with SSL termination
- Prometheus + Grafana monitoring
- Fluentd log aggregation

## Security Checklist

- [ ] All endpoints require authentication (except `/auth/login`, `/auth/register`)
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] CSRF tokens for state-changing operations
- [ ] Rate limiting on all endpoints
- [ ] Audit logging for sensitive operations
- [ ] Encryption at rest (database)
- [ ] Encryption in transit (TLS 1.3)
- [ ] Secrets management (Vault/AWS Secrets Manager)
- [ ] Regular security scans (SAST/DAST)

## Monitoring

### Metrics
- Request rate/latency/errors by endpoint
- Active users
- Exchange events per hour
- Credit transactions
- Class enrollments/completions

### Alerts
- Error rate > 1%
- Latency p99 > 500ms
- Database connections > 80%
- Disk usage > 85%

## License

Part of the Agora AI Platform.
Copyright 2025 Sunni (Sir) Morningstar & Cael Devo