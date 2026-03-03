#!/usr/bin/env python3
"""Generate a .env file with random secrets."""
import secrets
import shutil

def main():
    jwt_secret = secrets.token_hex(32)
    encryption_key = secrets.token_hex(32)
    db_password = secrets.token_urlsafe(24)

    env_content = f"""# Database
POSTGRES_USER=schoolchat
POSTGRES_PASSWORD={db_password}
POSTGRES_DB=schoolchat
DATABASE_URL=postgresql+asyncpg://schoolchat:{db_password}@db:5432/schoolchat

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET={jwt_secret}
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=7

# Encryption (AES-256 — 64 hex chars = 32 bytes)
ENCRYPTION_KEY={encryption_key}

# Server
SERVER_NAME=SchoolChat
ALLOWED_ORIGINS=*
"""
    with open(".env", "w") as f:
        f.write(env_content)

    print("Generated .env with random secrets:")
    print(f"  JWT_SECRET:      {jwt_secret[:8]}...{jwt_secret[-8:]}")
    print(f"  ENCRYPTION_KEY:  {encryption_key[:8]}...{encryption_key[-8:]}")
    print(f"  DB_PASSWORD:     {db_password[:4]}...{db_password[-4:]}")
    print("\n⚠️  Keep this file safe and never commit it to version control!")


if __name__ == "__main__":
    main()
