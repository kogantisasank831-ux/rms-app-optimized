"""T-001 connectivity checklist — validates provided hackathon infra.

Reads credentials from rms-app/.env (gitignored). No secrets hardcoded here.
Run:  python scripts/check_connectivity.py
Requires (dev-only): psycopg[binary], minio, requests
Exits 0 if all MUST checks pass, 1 otherwise. Safe/idempotent: all writes are rolled back or cleaned up.
"""
from __future__ import annotations
import os
import socket
import sys
from pathlib import Path


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = Path(__file__).resolve().parent.parent / ".env"
    if not p.exists():
        print(f"FATAL: {p} not found. Copy .env.example -> .env and fill T-07 values.")
        sys.exit(2)
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


results: list[tuple[str, bool, str, bool]] = []  # (name, ok, detail, must)


def record(name: str, ok: bool, detail: str = "", must: bool = True) -> None:
    results.append((name, ok, detail, must))
    mark = "PASS" if ok else ("FAIL" if must else "WARN")
    print(f"[{mark}] {name}: {detail}")


def tcp(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    env = load_env()

    # --- derive PG parts from DATABASE_URL (strip +asyncpg driver) ---
    db_url = env.get("DATABASE_URL", "")
    pg_host = db_url.split("@")[-1].split(":")[0] if "@" in db_url else ""
    minio_ep = env.get("MINIO_ENDPOINT", "")
    minio_host, _, minio_port = minio_ep.partition(":")

    print("=" * 70)
    print("T-001 CONNECTIVITY CHECKLIST — Team T-07")
    print("=" * 70)

    # 1. VPN / TCP reachability -------------------------------------------------
    if pg_host:
        record("VPN/TCP PostgreSQL 5432", tcp(pg_host, 5432), f"{pg_host}:5432")
    if minio_host:
        record("VPN/TCP MinIO 9000", tcp(minio_host, int(minio_port or 9000)),
               f"{minio_host}:{minio_port}")

    # 2. PostgreSQL -------------------------------------------------------------
    schema = env.get("PG_SCHEMA", "public")
    try:
        import psycopg
        sync_url = "postgresql://" + db_url.split("://", 1)[1].replace("+asyncpg", "")
        with psycopg.connect(sync_url, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                ver = cur.fetchone()[0]
                record("PG connect + version", True, ver.split(",")[0])

                cur.execute("SHOW server_version_num")
                vnum = int(cur.fetchone()[0])
                record("PG version >= 13 (gen_random_uuid built-in)", vnum >= 130000,
                       f"server_version_num={vnum}")

                # gen_random_uuid available without pgcrypto?
                try:
                    cur.execute("SELECT gen_random_uuid()")
                    record("gen_random_uuid() available", True, str(cur.fetchone()[0]))
                except Exception as e:
                    conn.rollback()
                    record("gen_random_uuid() available", False, str(e).strip(), must=False)

                # schema exists / visible
                cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name=%s", (schema,))
                record(f"schema '{schema}' exists", cur.fetchone() is not None, schema)

                # DDL write permission in schema (create+drop, rolled back)
                try:
                    cur.execute(f'CREATE TABLE "{schema}"._t001_probe (id int)')
                    cur.execute(f'DROP TABLE "{schema}"._t001_probe')
                    conn.rollback()
                    record(f"DDL write in '{schema}'", True, "create/drop table OK (rolled back)")
                except Exception as e:
                    conn.rollback()
                    record(f"DDL write in '{schema}'", False, str(e).strip())

                # citext extension: present or creatable?
                cur.execute("SELECT 1 FROM pg_extension WHERE extname='citext'")
                if cur.fetchone():
                    record("citext extension", True, "already installed on shared DB", must=False)
                else:
                    try:
                        cur.execute("CREATE EXTENSION IF NOT EXISTS citext")
                        conn.rollback()  # don't actually commit during a probe
                        record("citext extension", True, "CREATE EXTENSION permitted (rolled back)", must=False)
                    except Exception as e:
                        conn.rollback()
                        record("citext extension (fallback: lower(email) unique idx)", False,
                               str(e).strip(), must=False)
    except Exception as e:
        record("PG connect", False, f"{type(e).__name__}: {str(e).strip()}")

    # 3. MinIO ------------------------------------------------------------------
    try:
        from minio import Minio
        client = Minio(
            minio_ep,
            access_key=env.get("MINIO_ACCESS_KEY", ""),
            secret_key=env.get("MINIO_SECRET_KEY", ""),
            secure=env.get("MINIO_SECURE", "false").lower() == "true",
        )
        bucket = env.get("MINIO_BUCKET", "")
        exists = client.bucket_exists(bucket)
        record(f"MinIO bucket '{bucket}' accessible", exists, f"bucket_exists={exists}")
        if exists:
            import io
            key = "_t001_probe.txt"
            data = b"t001 connectivity probe"
            client.put_object(bucket, key, io.BytesIO(data), length=len(data),
                              content_type="text/plain")
            got = client.get_object(bucket, key).read()
            client.remove_object(bucket, key)
            record("MinIO put/get/delete", got == data, "round-trip OK (object removed)")
    except Exception as e:
        record("MinIO access", False, f"{type(e).__name__}: {str(e).strip()}")

    # 4. Claude API -------------------------------------------------------------
    try:
        import requests
        model = env.get("CLAUDE_MODEL", "claude-opus-4-8")
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": env.get("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": 8,
                  "messages": [{"role": "user", "content": "ping"}]},
            timeout=30,
        )
        if r.status_code == 200:
            record(f"Claude API ({model})", True, "200 OK, key valid")
        else:
            record(f"Claude API ({model})", False, f"HTTP {r.status_code}: {r.text[:160]}")
    except Exception as e:
        record("Claude API", False, f"{type(e).__name__}: {str(e).strip()}")

    # 5. GitLab (host reachability only; auth is manual/browser) ----------------
    try:
        import requests
        repo = env.get("GITLAB_REPO", "https://tcgrepo.tcgdigital.com")
        host = repo.split("//")[1].split("/")[0]
        r = requests.get(f"https://{host}", timeout=10, allow_redirects=True, verify=False)
        record("GitLab host reachable", r.status_code < 500,
               f"{host} -> HTTP {r.status_code} (login/push is manual)", must=False)
    except Exception as e:
        record("GitLab host reachable", False, f"{type(e).__name__}: {str(e).strip()}", must=False)

    # --- summary ---------------------------------------------------------------
    print("=" * 70)
    must_fail = [n for n, ok, _, must in results if must and not ok]
    warn = [n for n, ok, _, must in results if not must and not ok]
    print(f"MUST checks: {sum(1 for _,ok,_,m in results if m and ok)}/"
          f"{sum(1 for _,_,_,m in results if m)} passed")
    if warn:
        print(f"WARN (non-blocking): {', '.join(warn)}")
    if must_fail:
        print(f"BLOCKING FAILURES: {', '.join(must_fail)}")
        return 1
    print("ALL MUST CHECKS PASSED — T-001 green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
