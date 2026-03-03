# SchoolChat Server

A self-hosted, Discord-like text chat server with encrypted message storage, real-time WebSocket messaging, and role-based access control. Designed to run on **Unraid** via Docker.

---

## Quick Start (Any Docker Host)

```bash
# 1. Clone / copy this directory to your server
# 2. Generate secrets
python3 scripts/generate_secrets.py

# 3. Generate self-signed TLS certs (dev only)
bash scripts/generate_certs.sh

# 4. Start everything
docker compose up -d

# 5. Check logs
docker compose logs -f app
```

The server will be available at:
- **HTTPS**: `https://your-server-ip`  (port 443)
- **Web UI**: `https://your-server-ip/` (built-in testing dashboard)
- **WebSocket**: `wss://your-server-ip/ws?token=<JWT>`
- **Health check**: `https://your-server-ip/health`

---

## Deploying on Unraid

Unraid supports Docker natively. There are two approaches: **Docker Compose** (recommended) or **manual container setup** via the Unraid GUI.

### Option A: Docker Compose on Unraid (Recommended)

Unraid 6.12+ supports Docker Compose natively via the **Compose Manager** plugin.

#### Step 1 — Install Compose Manager

1. Open the Unraid web UI → **Apps** tab
2. Search for **"Docker Compose Manager"** (by dcflacmern)
3. Click **Install**

#### Step 2 — Copy the Project to Unraid

Copy the entire `schoolchat-server/` directory to a share on your Unraid server. A good location is:

```
/mnt/user/appdata/schoolchat/
```

You can do this via SMB/NFS file sharing, SCP, or the Unraid terminal:

```bash
scp -r schoolchat-server/ root@<UNRAID_IP>:/mnt/user/appdata/schoolchat/
```

#### Step 3 — Generate Secrets

SSH into your Unraid server (or use the built-in terminal from the web UI):

```bash
cd /mnt/user/appdata/schoolchat
python3 scripts/generate_secrets.py
```

If Python 3 isn't available on bare Unraid, use Docker:

```bash
docker run --rm -v /mnt/user/appdata/schoolchat:/app -w /app python:3.12-slim \
    python scripts/generate_secrets.py
```

#### Step 4 — Generate TLS Certificates

**For local network use (self-signed):**

```bash
cd /mnt/user/appdata/schoolchat
bash scripts/generate_certs.sh
```

Or via Docker if openssl isn't available:

```bash
docker run --rm -v /mnt/user/appdata/schoolchat:/app -w /app alpine/openssl \
    req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /app/nginx/certs/privkey.pem \
    -out /app/nginx/certs/fullchain.pem \
    -subj "/CN=schoolchat.local/O=SchoolChat/C=AU"
```

**For internet-facing deployments:**

Use the **Nginx Proxy Manager** or **Swag** container (available in Unraid Community Apps) to handle TLS with Let's Encrypt. In that case, remove the `nginx` service from `docker-compose.yml` and point your proxy manager at port 8000.

#### Step 5 — Launch

```bash
cd /mnt/user/appdata/schoolchat
docker compose up -d
```

The Compose Manager plugin also lets you manage this from the Unraid web UI under **Docker → Compose**.

#### Step 6 — Verify

```bash
docker compose ps
docker compose logs -f app
curl -k https://localhost/health
```

You should see `{"status":"ok","service":"SchoolChat"}`.

Then open `https://your-server-ip/` in a browser to access the built-in testing dashboard, where you can register users, create channels, and chat in real time.

---

### Option B: Manual Container Setup (Unraid GUI)

If you prefer the Unraid Docker GUI over Compose, set up each container manually.

#### B.1 — Create a Docker Network

From the Unraid terminal:

```bash
docker network create schoolchat-net
```

#### B.2 — PostgreSQL Container

In Unraid web UI → **Docker** → **Add Container**:

| Field | Value |
|---|---|
| Name | `schoolchat-db` |
| Repository | `postgres:16-alpine` |
| Network Type | `schoolchat-net` |

**Environment Variables:**
- `POSTGRES_USER` = `schoolchat`
- `POSTGRES_PASSWORD` = *(your generated password)*
- `POSTGRES_DB` = `schoolchat`

**Path:** `/var/lib/postgresql/data` → `/mnt/user/appdata/schoolchat/pgdata` (RW)

#### B.3 — Redis Container

| Field | Value |
|---|---|
| Name | `schoolchat-redis` |
| Repository | `redis:7-alpine` |
| Network Type | `schoolchat-net` |
| Post Arguments | `redis-server --appendonly yes` |

**Path:** `/data` → `/mnt/user/appdata/schoolchat/redisdata` (RW)

#### B.4 — Build the App Image

```bash
cd /mnt/user/appdata/schoolchat
docker build -t schoolchat-app .
```

#### B.5 — App Container

| Field | Value |
|---|---|
| Name | `schoolchat-app` |
| Repository | `schoolchat-app` |
| Network Type | `schoolchat-net` |
| Port | Host `8000` → Container `8000` |

**Environment Variables** (copy from your `.env` file):
- `DATABASE_URL` = `postgresql+asyncpg://schoolchat:<password>@schoolchat-db:5432/schoolchat`
- `REDIS_URL` = `redis://schoolchat-redis:6379/0`
- `JWT_SECRET` = *(your generated secret)*
- `ENCRYPTION_KEY` = *(your generated key)*
- `JWT_ACCESS_EXPIRE_MINUTES` = `15`
- `JWT_REFRESH_EXPIRE_DAYS` = `7`
- `SERVER_NAME` = `SchoolChat`
- `ALLOWED_ORIGINS` = `*`

#### B.6 — Reverse Proxy

If you already run **Nginx Proxy Manager** or **Swag** on your Unraid box, point it at `schoolchat-app:8000`. Enable WebSocket support for the `/ws` path.

---

## Unraid-Specific Tips

### Data Persistence

| Data | Docker Compose Volume | Manual Host Path |
|---|---|---|
| PostgreSQL | `pgdata` volume | `/mnt/user/appdata/schoolchat/pgdata` |
| Redis | `redisdata` volume | `/mnt/user/appdata/schoolchat/redisdata` |
| TLS Certs | `./nginx/certs` bind mount | `/mnt/user/appdata/schoolchat/nginx/certs` |

### Backups

Back up the appdata directory. **Critical:** the `.env` file contains your encryption key — if you lose it, all stored messages become unrecoverable.

```bash
#!/bin/bash
# Add to Unraid's User Scripts plugin for scheduled backups
BACKUP_DIR="/mnt/user/backups/schoolchat/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

docker compose -f /mnt/user/appdata/schoolchat/docker-compose.yml stop app
docker exec schoolchat-db pg_dump -U schoolchat schoolchat | gzip > "$BACKUP_DIR/db.sql.gz"
cp /mnt/user/appdata/schoolchat/.env "$BACKUP_DIR/.env"
docker compose -f /mnt/user/appdata/schoolchat/docker-compose.yml start app

echo "Backup completed: $BACKUP_DIR"
```

### Firewall / Network

- For local-only access: ensure port 443 (or 8000) is reachable on LAN but not exposed to the internet.
- For internet access: use Unraid's **Swag** container for automatic Let's Encrypt certificates.

### Updating

```bash
cd /mnt/user/appdata/schoolchat
docker compose build app
docker compose up -d
```

Database migrations run automatically on container start (`alembic upgrade head`).

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register (first user becomes admin) |
| POST | `/api/auth/login` | Login, receive JWT tokens |
| POST | `/api/auth/refresh` | Refresh expired access token |
| GET  | `/api/auth/me` | Get current user profile |

### Users

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/users` | List all users |
| GET | `/api/users/online` | List currently online users |
| GET | `/api/users/{id}` | Get a specific user |
| PATCH | `/api/users/me` | Update your display name |
| PATCH | `/api/users/{id}/role` | Set user role (admin only) |

### Channels

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/channels` | List visible channels |
| POST | `/api/channels` | Create channel (mod/admin) |
| PATCH | `/api/channels/{id}` | Edit channel (mod/admin) |
| GET | `/api/channels/{id}/members` | List members |
| POST | `/api/channels/{id}/members` | Add member (mod/admin) |
| DELETE | `/api/channels/{id}/members/{uid}` | Remove member (mod/admin) |
| GET | `/api/channels/{id}/messages` | Paginated message history |
| POST | `/api/channels/{id}/messages` | Send message (via REST) |
| PATCH | `/api/channels/messages/{id}` | Edit message |
| DELETE | `/api/channels/messages/{id}` | Delete message |
| GET | `/api/channels/{id}/search?q=` | Search messages in channel |

### WebSocket Protocol

Connect: `wss://host/ws?token=<JWT_ACCESS_TOKEN>`

**Client sends:**
```json
{"type": "channel.subscribe", "channel_id": "uuid"}
{"type": "channel.unsubscribe", "channel_id": "uuid"}
{"type": "message.send", "channel_id": "uuid", "content": "Hello!", "reply_to": null}
{"type": "typing.start", "channel_id": "uuid"}
{"type": "typing.stop", "channel_id": "uuid"}
```

**Server sends:**
```json
{"type": "channel.subscribed", "channel_id": "uuid"}
{"type": "message.new", "id": "uuid", "channel_id": "uuid", "sender_id": "uuid", "sender_name": "Alice", "content": "Hello!", "created_at": "ISO8601"}
{"type": "presence.update", "user_id": "uuid", "username": "Alice", "status": "online"}
{"type": "typing.start", "channel_id": "uuid", "user_id": "uuid", "username": "Alice"}
{"type": "error", "detail": "Error description"}
```

---

## First-Time Setup

1. Open the web UI at `https://your-server-ip/` in your browser.
2. Register the first user — they automatically become **admin**.
3. Admin creates channels via the web UI or POST `/api/channels`.
4. Admin promotes trusted users to moderator via PATCH `/api/users/{id}/role`.
5. Additional users register and get the **member** role by default.
6. Moderators/admins create channels and add members.
7. Chat directly in the web UI for testing, or connect via the Python client.
