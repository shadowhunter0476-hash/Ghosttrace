# language: Python 3.11+, file: db.py
# *Postgres (Neon) via pg8000 — pure Python, Termux-compatible.*

import os
import secrets
import hashlib
from datetime import datetime, timedelta
import pg8000.native
from urllib.parse import urlparse, unquote

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable not set")


def _parse_db_url(url):
    p = urlparse(url)
    return {
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "host": p.hostname,
        "port": p.port or 5432,
        "database": (p.path or "/").lstrip("/") or "postgres",
    }


DB_PARAMS = _parse_db_url(DATABASE_URL)


def get_conn():
    return pg8000.native.Connection(**DB_PARAMS)


def init_db():
    conn = get_conn()
    conn.run("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            credits INTEGER DEFAULT 0,
            plan TEXT DEFAULT 'free',
            plan_expires TIMESTAMP,
            verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS searches (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            query TEXT NOT NULL,
            type TEXT DEFAULT 'username',
            found_count INTEGER DEFAULT 0,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            value INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            plan TEXT DEFAULT 'pro',
            days INTEGER DEFAULT 30,
            expires_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS redemptions (
            id SERIAL PRIMARY KEY,
            code TEXT NOT NULL REFERENCES gift_codes(code) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, user_id)
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            otp TEXT NOT NULL,
            purpose TEXT DEFAULT 'signup',
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()


def hash_password(password):
    salt = "ghosttrace_salt_v1"
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


def _cols(conn, table):
    rows = conn.run(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t ORDER BY ordinal_position",
        t=table
    )
    return [r[0] for r in rows]


def create_user(email, password, is_admin=False, credits=0, verified=0):
    conn = get_conn()
    try:
        result = conn.run(
            "INSERT INTO users (email, password_hash, is_admin, credits, verified) VALUES (:e, :p, :a, :c, :v) RETURNING id",
            e=email.lower().strip(), p=hash_password(password),
            a=1 if is_admin else 0, c=credits, v=verified
        )
        uid = result[0][0]
        conn.close()
        return uid
    except Exception as ex:
        conn.close()
        if "duplicate" in str(ex).lower() or "unique" in str(ex).lower():
            return None
        raise


def get_user_by_email(email):
    conn = get_conn()
    rows = conn.run("SELECT * FROM users WHERE email = :e", e=email.lower().strip())
    if not rows:
        conn.close()
        return None
    cols = _cols(conn, "users")
    conn.close()
    return dict(zip(cols, rows[0]))


def get_user_by_id(user_id):
    conn = get_conn()
    rows = conn.run("SELECT * FROM users WHERE id = :i", i=user_id)
    if not rows:
        conn.close()
        return None
    cols = _cols(conn, "users")
    conn.close()
    return dict(zip(cols, rows[0]))


def login_user(email, password):
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def verify_user_email(email):
    conn = get_conn()
    conn.run("UPDATE users SET verified = 1, credits = 5 WHERE email = :e", e=email.lower().strip())
    conn.close()


def is_verified(user):
    return bool(user.get("verified"))


def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


def create_otp(email, purpose="signup", minutes=10):
    conn = get_conn()
    conn.run("DELETE FROM otp_codes WHERE email = :e AND used = 0", e=email.lower().strip())
    otp = generate_otp()
    expires = datetime.now() + timedelta(minutes=minutes)
    conn.run(
        "INSERT INTO otp_codes (email, otp, purpose, expires_at) VALUES (:e, :o, :p, :x)",
        e=email.lower().strip(), o=otp, p=purpose, x=expires
    )
    conn.close()
    return otp


def verify_otp(email, otp):
    conn = get_conn()
    rows = conn.run(
        "SELECT * FROM otp_codes WHERE email = :e AND used = 0 ORDER BY created_at DESC LIMIT 1",
        e=email.lower().strip()
    )
    if not rows:
        conn.close()
        return False, "No active OTP found"
    cols = _cols(conn, "otp_codes")
    rec = dict(zip(cols, rows[0]))
    if rec["attempts"] >= 5:
        conn.close()
        return False, "Too many attempts — request new OTP"
    if rec["expires_at"] < datetime.now():
        conn.close()
        return False, "OTP expired"
    if rec["otp"] != otp.strip():
        conn.run("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = :i", i=rec["id"])
        conn.close()
        return False, "Incorrect OTP"
    conn.run("UPDATE otp_codes SET used = 1 WHERE id = :i", i=rec["id"])
    conn.close()
    return True, "Verified"


def decrement_credits(user_id, amount=1):
    conn = get_conn()
    conn.run("UPDATE users SET credits = GREATEST(0, credits - :a) WHERE id = :i", a=amount, i=user_id)
    conn.close()


def set_credits(user_id, amount):
    conn = get_conn()
    conn.run("UPDATE users SET credits = :a WHERE id = :i", a=amount, i=user_id)
    conn.close()


def is_premium(user):
    if user.get("plan") == "free":
        return False
    exp = user.get("plan_expires")
    if not exp:
        return False
    try:
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        return exp > datetime.now()
    except Exception:
        return False


def upgrade_plan(user_id, plan, days):
    conn = get_conn()
    expires = datetime.now() + timedelta(days=days)
    conn.run("UPDATE users SET plan = :p, plan_expires = :x WHERE id = :i",
             p=plan, x=expires, i=user_id)
    conn.close()


def save_search(user_id, query, search_type, found_count, results_json):
    conn = get_conn()
    conn.run(
        "INSERT INTO searches (user_id, query, type, found_count, results) VALUES (:u, :q, :t, :f, :r)",
        u=user_id, q=query, t=search_type, f=found_count, r=results_json
    )
    conn.close()


def get_user_searches(user_id, limit=50):
    conn = get_conn()
    rows = conn.run(
        "SELECT * FROM searches WHERE user_id = :u ORDER BY created_at DESC LIMIT :l",
        u=user_id, l=limit
    )
    if not rows:
        conn.close()
        return []
    cols = _cols(conn, "searches")
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def delete_user_searches(user_id):
    conn = get_conn()
    conn.run("DELETE FROM searches WHERE user_id = :u", u=user_id)
    conn.close()


def generate_code():
    a = secrets.token_hex(2).upper()
    b = secrets.token_hex(2).upper()
    return f"GHOST-{a}-{b}"


def create_gift_code(value, max_uses=1, plan="pro", days=30, expires_at=None, created_by=None):
    conn = get_conn()
    while True:
        code = generate_code()
        try:
            conn.run(
                "INSERT INTO gift_codes (code, value, max_uses, plan, days, expires_at, created_by) VALUES (:c, :v, :m, :p, :d, :x, :cb)",
                c=code, v=value, m=max_uses, p=plan, d=days, x=expires_at, cb=created_by
            )
            conn.close()
            return code
        except Exception as ex:
            if "duplicate" in str(ex).lower() or "unique" in str(ex).lower():
                continue
            conn.close()
            raise


def get_gift_code(code):
    conn = get_conn()
    rows = conn.run("SELECT * FROM gift_codes WHERE code = :c", c=code.upper().strip())
    if not rows:
        conn.close()
        return None
    cols = _cols(conn, "gift_codes")
    conn.close()
    return dict(zip(cols, rows[0]))


def list_gift_codes():
    conn = get_conn()
    rows = conn.run("SELECT * FROM gift_codes ORDER BY created_at DESC")
    if not rows:
        conn.close()
        return []
    cols = _cols(conn, "gift_codes")
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def delete_gift_code(code):
    conn = get_conn()
    conn.run("DELETE FROM gift_codes WHERE code = :c", c=code)
    conn.close()


def has_redeemed(code, user_id):
    conn = get_conn()
    rows = conn.run("SELECT 1 FROM redemptions WHERE code = :c AND user_id = :u", c=code, u=user_id)
    conn.close()
    return len(rows) > 0


def redeem_gift_code(code, user_id):
    code = code.upper().strip()
    gc = get_gift_code(code)
    if not gc:
        return False, "Invalid gift code"
    if gc.get("expires_at"):
        try:
            exp = gc["expires_at"]
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            if exp < datetime.now():
                return False, "Gift code expired"
        except Exception:
            pass
    if gc["max_uses"] > 0 and gc["used_count"] >= gc["max_uses"]:
        return False, "Gift code fully used"
    if has_redeemed(code, user_id):
        return False, "You already redeemed this code"
    conn = get_conn()
    conn.run("UPDATE gift_codes SET used_count = used_count + 1 WHERE code = :c", c=code)
    conn.run("INSERT INTO redemptions (code, user_id) VALUES (:c, :u)", c=code, u=user_id)
    conn.close()
    upgrade_plan(user_id, gc["plan"], gc["days"])
    return True, f"Redeemed! {gc['plan'].upper()} for {gc['days']} days"


def create_reset_token(user_id, hours=1):
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=hours)
    conn = get_conn()
    conn.run("INSERT INTO reset_tokens (token, user_id, expires_at) VALUES (:t, :u, :x)",
             t=token, u=user_id, x=expires)
    conn.close()
    return token


def verify_reset_token(token):
    conn = get_conn()
    rows = conn.run("SELECT * FROM reset_tokens WHERE token = :t AND used = 0", t=token)
    if not rows:
        conn.close()
        return None
    cols = _cols(conn, "reset_tokens")
    rec = dict(zip(cols, rows[0]))
    conn.close()
    exp = rec["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp < datetime.now():
        return None
    return rec


def use_reset_token(token):
    conn = get_conn()
    conn.run("UPDATE reset_tokens SET used = 1 WHERE token = :t", t=token)
    conn.close()


def get_stats():
    conn = get_conn()
    users = conn.run("SELECT COUNT(*) FROM users")[0][0]
    searches = conn.run("SELECT COUNT(*) FROM searches")[0][0]
    codes = conn.run("SELECT COUNT(*) FROM gift_codes")[0][0]
    redemptions = conn.run("SELECT COUNT(*) FROM redemptions")[0][0]
    conn.close()
    return {"users": users, "searches": searches, "gift_codes": codes, "redemptions": redemptions}


def list_users():
    conn = get_conn()
    rows = conn.run("SELECT id, email, is_admin, credits, plan, plan_expires, verified, created_at FROM users ORDER BY created_at DESC")
    conn.close()
    cols = ["id", "email", "is_admin", "credits", "plan", "plan_expires", "verified", "created_at"]
    return [dict(zip(cols, row)) for row in rows]


def init_with_admin():
    init_db()
    admin_email = "admin@ghosttrace.com"
    admin_pass = "ghosttrace@admin"
    u = get_user_by_email(admin_email)
    if not u:
        create_user(admin_email, admin_pass, is_admin=True, credits=999999, verified=1)
        print(f"[+] admin created: {admin_email}")
    else:
        conn = get_conn()
        conn.run("UPDATE users SET verified = 1 WHERE email = :e", e=admin_email)
        conn.close()
        print(f"[*] admin exists")


if __name__ == "__main__":
    init_with_admin()
    print("[+] database initialized")
