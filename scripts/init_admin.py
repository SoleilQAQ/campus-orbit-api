# scripts/init_admin.py
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


def _load_dotenv_if_exists(dotenv_path: Path) -> None:
    """
    Minimal .env loader (no dependency):
    - supports KEY=VALUE
    - ignores blank lines and comments
    - strips surrounding quotes
    - does NOT overwrite existing env vars
    """
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def _ensure_env_or_exit(required_keys: list[str]) -> None:
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        print("[ERROR] Missing required environment variables:")
        for k in missing:
            print(f"  - {k}")
        print("\nFix options:")
        print("  1) Create/Update .env at repo root with these keys")
        print("  2) Export them in your shell environment")
        print("  3) Pass DATABASE_URL/OPENWEATHER_API_KEY via env before running\n")
        print("Example .env:")
        print("  DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/campus_orbit")
        print("  OPENWEATHER_API_KEY=xxxxx\n")
        sys.exit(1)


async def main() -> None:
    # --- resolve paths ---
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]  # scripts/.. = repo root

    # ensure "import app.*" works
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # load .env early (before importing Settings)
    _load_dotenv_if_exists(repo_root / ".env")

    parser = argparse.ArgumentParser(description="Bootstrap platform admin user")
    parser.add_argument("--reset", action="store_true", help="Reset admin password (and enable user)")
    parser.add_argument("--username", type=str, default=None, help="Override admin username (else from settings)")
    parser.add_argument("--password", type=str, default=None, help="Override admin password (else from settings)")
    parser.add_argument("--create-tables", action="store_true", help="Create tables via metadata.create_all (dev only)")
    args = parser.parse_args()

    # Your app Settings requires these at import time -> enforce them now
    _ensure_env_or_exit(["DATABASE_URL", "OPENWEATHER_API_KEY"])

    # --- imports after env ready ---
    from sqlalchemy import select  # noqa: E402

    from app.db.session import AsyncSessionLocal, engine  # noqa: E402
    from app.platform import settings  # noqa: E402
    from app.platform.models import PlatformUser  # noqa: E402
    from app.platform.security import hash_password  # noqa: E402

    # If you have a platform Base for create_all (optional)
    try:
        from app.platform.models.base import Base  # noqa: E402
    except Exception:
        Base = None  # type: ignore

    async def create_tables_if_needed():
        if not args.create_tables:
            return
        if Base is None:
            raise RuntimeError("Base not found. Please ensure app.platform.models.base.Base exists.")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    await create_tables_if_needed()

    admin_username = args.username or settings.bootstrap_admin_username
    admin_password = args.password or settings.bootstrap_admin_password

    if not admin_username or not admin_password:
        raise RuntimeError("Missing admin username/password. Check settings or pass --username/--password")

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(PlatformUser).where(PlatformUser.username == admin_username))
        u = r.scalar_one_or_none()

        if u is None:
            u = PlatformUser(
                username=admin_username,
                role="admin",
                password_hash=hash_password(admin_password),
                is_enabled=True,
            )
            db.add(u)
            await db.commit()
            print(f"[OK] created admin: {admin_username}")
            return

        if u.role != "admin":
            print(f"[WARN] user exists but role={u.role}, will not modify: {admin_username}")
            return

        if args.reset:
            u.password_hash = hash_password(admin_password)
            u.is_enabled = True
            await db.commit()
            print(f"[OK] reset admin password and enabled: {admin_username}")
        else:
            print(f"[OK] admin already exists: {admin_username} (use --reset to reset password)")


if __name__ == "__main__":
    asyncio.run(main())
