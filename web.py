# language: Python 3.11+, file: web.py
# *Flask server — OTP, search, photo search, payment, admin.*

import asyncio
import json
import os
import threading
import time
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, session, redirect, send_from_directory

import db
from checker import check_username
from email_check import check_email
from phone_check import check_phone
from emailer import send_reset_email, send_otp_email
from sites import TRUSTED_SITES

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE)
app.secret_key = os.environ.get("SECRET_KEY", "ghosttrace_secret_change_me")
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_HTTPONLY=False,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_DOMAIN=None,
    PERMANENT_SESSION_LIFETIME=86400,
)

LAST_SEARCH = {}
RATE_LIMIT_SEC = 3
SEARCH_TIMEOUT = 60

PLANS = {
    "starter": {"amount": 20, "credits": 5, "label": "Starter"},
    "pro": {"amount": 50, "credits": 15, "label": "Pro Pack"},
    "mega": {"amount": 99, "credits": 50, "label": "Mega Pack"},
}


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("user_id"):
            return jsonify({"error": "login required"}), 401
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        uid = session.get("user_id")
        if not uid:
            return jsonify({"error": "login required"}), 401
        u = db.get_user_by_id(uid)
        if not u or not u.get("is_admin"):
            return jsonify({"error": "admin only"}), 403
        return f(*a, **k)
    return w


def current_user():
    uid = session.get("user_id")
    return db.get_user_by_id(uid) if uid else None


# ---------- pages ----------

@app.route("/")
def index():
    return send_from_directory(BASE, "landing.html")


@app.route("/dashboard")
def dashboard_page():
    if not session.get("user_id"):
        return redirect("/login")
    return send_from_directory(BASE, "panel.html")


@app.route("/login", methods=["GET"])
def login_page():
    return send_from_directory(BASE, "login.html")


@app.route("/pricing")
def pricing_page():
    return send_from_directory(BASE, "pricing.html")


@app.route("/settings")
def settings_page():
    if not session.get("user_id"):
        return redirect("/login")
    return send_from_directory(BASE, "settings.html")


@app.route("/terms")
def terms_page():
    return send_from_directory(BASE, "terms.html")


@app.route("/privacy")
def privacy_page():
    return send_from_directory(BASE, "privacy.html")


@app.route("/forgot")
def forgot_page():
    return send_from_directory(BASE, "forgot.html")


@app.route("/reset/<token>")
def reset_page(token):
    return send_from_directory(BASE, "reset.html")


@app.route("/search-photo")
def search_photo_page():
    if not session.get("user_id"):
        return redirect("/login")
    return send_from_directory(BASE, "photo.html")


@app.route("/payment")
def payment_page():
    if not session.get("user_id"):
        return redirect("/login")
    return send_from_directory(BASE, "payment.html")


@app.route("/admin", methods=["GET"])
def admin_page():
    if not session.get("user_id"):
        return redirect("/login")
    u = current_user()
    if not u or not u.get("is_admin"):
        return redirect("/")
    return send_from_directory(BASE, "admin.html")


# ---------- auth API ----------

@app.route("/api/signup", methods=["POST"])
def api_signup():
    d = request.get_json(force=True) or {}
    email = str(d.get("email", "")).strip().lower()
    pw = str(d.get("password", ""))
    if not email or "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    if len(pw) < 6:
        return jsonify({"error": "password 6+ chars"}), 400

    existing = db.get_user_by_email(email)
    if existing and existing.get("verified"):
        return jsonify({"error": "email already registered"}), 400

    if existing and not existing.get("verified"):
        conn = db.get_conn()
        conn.run("UPDATE users SET password_hash = :h WHERE id = :i",
                 h=db.hash_password(pw), i=existing["id"])
        conn.close()
    else:
        uid = db.create_user(email, pw, is_admin=False, credits=0, verified=0)
        if not uid:
            return jsonify({"error": "signup failed"}), 400

    otp = db.create_otp(email, purpose="signup", minutes=10)
    try:
        ok, msg = send_otp_email(email, otp)
        print(f"[*] OTP email to {email}: {'sent' if ok else 'failed: ' + msg}")
    except Exception as e:
        print(f"[!] OTP email error: {e}")

    return jsonify({"ok": True, "email": email, "requires_otp": True})


@app.route("/api/verify-otp", methods=["POST"])
def api_verify_otp():
    d = request.get_json(force=True) or {}
    email = str(d.get("email", "")).strip().lower()
    otp = str(d.get("otp", "")).strip()
    if not email or not otp:
        return jsonify({"error": "missing fields"}), 400

    ok, msg = db.verify_otp(email, otp)
    if not ok:
        return jsonify({"error": msg}), 400

    u = db.get_user_by_email(email)
    if not u:
        return jsonify({"error": "user not found"}), 404

    db.verify_user_email(email)
    u = db.get_user_by_email(email)
    session["user_id"] = u["id"]
    session.permanent = True
    return jsonify({"ok": True, "credits": u["credits"], "verified": True})


@app.route("/api/resend-otp", methods=["POST"])
def api_resend_otp():
    d = request.get_json(force=True) or {}
    email = str(d.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    u = db.get_user_by_email(email)
    if not u:
        return jsonify({"error": "user not found"}), 404
    if u.get("verified"):
        return jsonify({"error": "already verified"}), 400

    otp = db.create_otp(email, purpose="signup", minutes=10)
    try:
        send_otp_email(email, otp)
    except Exception as e:
        print(f"[!] resend error: {e}")
    return jsonify({"ok": True, "message": "OTP resent"})


@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(force=True) or {}
    email = str(d.get("email", "")).strip().lower()
    pw = str(d.get("password", ""))
    u = db.login_user(email, pw)
    if not u:
        return jsonify({"error": "invalid credentials"}), 401
    if not u.get("verified") and not u.get("is_admin"):
        return jsonify({"error": "email not verified", "requires_otp": True, "email": email}), 403
    session["user_id"] = u["id"]
    session.permanent = True
    return jsonify({"ok": True, "email": u["email"], "credits": u["credits"], "is_admin": bool(u["is_admin"])})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
@login_required
def api_me():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": u["id"], "email": u["email"], "credits": u["credits"],
        "plan": u["plan"], "plan_expires": str(u["plan_expires"]) if u["plan_expires"] else None,
        "is_admin": bool(u["is_admin"]), "is_premium": db.is_premium(u),
    })


@app.route("/api/lens-url", methods=["POST"])
@login_required
def api_lens_url():
    d = request.get_json(force=True) or {}
    image_url = str(d.get("image_url", "")).strip()
    if not image_url or not image_url.startswith("http"):
        return jsonify({"error": "invalid image URL"}), 400
    lens_url = f"https://lens.google.com/uploadbyurl?url={image_url}"
    return jsonify({"ok": True, "lens_url": lens_url})


@app.route("/api/forgot", methods=["POST"])
def api_forgot():
    d = request.get_json(force=True) or {}
    email = str(d.get("email", "")).strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "invalid email"}), 400
    u = db.get_user_by_email(email)
    print(f"[*] password reset requested for: {email}")
    if u:
        token = db.create_reset_token(u["id"], hours=1)
        base = request.host_url.rstrip("/")
        reset_link = f"{base}/reset/{token}"
        try:
            ok, msg = send_reset_email(email, reset_link)
            print(f"[*] reset email {'sent' if ok else 'failed: ' + msg}")
        except Exception as e:
            print(f"[!] email error: {e}")
    return jsonify({"ok": True, "message": "If this email exists, reset link has been sent."})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    d = request.get_json(force=True) or {}
    token = str(d.get("token", "")).strip()
    newpw = str(d.get("password", ""))
    if not token or not newpw:
        return jsonify({"error": "missing fields"}), 400
    if len(newpw) < 6:
        return jsonify({"error": "password 6+ chars"}), 400
    row = db.verify_reset_token(token)
    if not row:
        return jsonify({"error": "invalid or expired token"}), 400
    conn = db.get_conn()
    conn.run("UPDATE users SET password_hash = :h WHERE id = :i",
             h=db.hash_password(newpw), i=row["user_id"])
    conn.close()
    db.use_reset_token(token)
    return jsonify({"ok": True, "message": "Password reset successful"})


@app.route("/api/change-password", methods=["POST"])
@login_required
def api_change_password():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    d = request.get_json(force=True) or {}
    cur = str(d.get("current", ""))
    new = str(d.get("new", ""))
    if not cur or not new:
        return jsonify({"error": "missing fields"}), 400
    if len(new) < 6:
        return jsonify({"error": "new password 6+ chars"}), 400
    if not db.verify_password(cur, u["password_hash"]):
        return jsonify({"error": "current password is incorrect"}), 400
    conn = db.get_conn()
    conn.run("UPDATE users SET password_hash = :h WHERE id = :i",
             h=db.hash_password(new), i=u["id"])
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/delete-account", methods=["POST"])
@login_required
def api_delete_account():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    d = request.get_json(force=True) or {}
    if d.get("confirm") != "DELETE":
        return jsonify({"error": "confirmation required"}), 400
    conn = db.get_conn()
    conn.run("DELETE FROM users WHERE id = :i", i=u["id"])
    conn.close()
    session.clear()
    return jsonify({"ok": True})


# ---------- search runners ----------

def run_async(fn, *args):
    box = {"data": [], "error": None}
    def worker():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                box["data"] = loop.run_until_complete(fn(*args))
            finally:
                loop.close()
        except Exception as e:
            box["error"] = str(e)
            print("[!] async error:", e)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=SEARCH_TIMEOUT)
    if t.is_alive():
        print("[!] timeout")
        return []
    return box["data"]


def run_sync(fn, *args):
    box = {"data": [], "error": None}
    def worker():
        try:
            box["data"] = fn(*args)
        except Exception as e:
            box["error"] = str(e)
            print("[!] sync error:", e)
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=SEARCH_TIMEOUT)
    if t.is_alive():
        print("[!] timeout")
        return []
    return box["data"]


def detect_type(q):
    q = q.strip()
    if "@" in q:
        return "email"
    digits = q.replace("+", "").replace("-", "").replace(" ", "")
    if digits.isdigit() and len(digits) >= 10:
        return "phone"
    return "username"


@app.route("/api/search", methods=["POST"])
@login_required
def api_search():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    premium = db.is_premium(u)
    is_admin = bool(u.get("is_admin"))

    if not premium and not is_admin and u["credits"] <= 0:
        return jsonify({"error": "out of credits", "out_of_credits": True}), 402

    uid = u["id"]
    now = time.time()
    last = LAST_SEARCH.get(uid, 0)
    if now - last < RATE_LIMIT_SEC:
        return jsonify({"error": f"wait {int(RATE_LIMIT_SEC-(now-last))}s"}), 429
    LAST_SEARCH[uid] = now

    d = request.get_json(force=True) or {}
    q = str(d.get("query", "")).strip()
    stype = str(d.get("type", "")).lower().strip()
    if not q:
        return jsonify({"error": "enter a query"}), 400
    if stype not in ("username", "email", "phone"):
        stype = detect_type(q)

    print(f"[*] search: {q} [{stype}]")

    t0 = time.time()
    try:
        if stype == "username":
            results = run_async(check_username, q)
        elif stype == "email":
            results = run_async(check_email, q)
        else:
            results = run_sync(check_phone, q)
    except Exception as e:
        print("[!] search exception:", e)
        results = []

    if not isinstance(results, list):
        results = []

    elapsed = round(time.time() - t0, 1)
    db.save_search(uid, q, stype, len(results), json.dumps(results))

    if not premium and not is_admin:
        db.decrement_credits(uid, 1)

    remaining = "unlimited" if (premium or is_admin) else u["credits"] - 1
    return jsonify({
        "ok": True, "query": q, "type": stype, "found": len(results),
        "elapsed": elapsed, "results": results,
        "credits_remaining": remaining, "scanned": len(TRUSTED_SITES),
    })


@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    items = db.get_user_searches(u["id"], limit=50)
    out = []
    for it in items:
        try:
            res = json.loads(it["results"]) if it["results"] else []
        except Exception:
            res = []
        out.append({"id": it["id"], "query": it["query"], "type": it.get("type", "username"),
                    "found": it["found_count"], "created_at": str(it["created_at"]), "results": res})
    return jsonify({"ok": True, "history": out})


@app.route("/api/history/clear", methods=["POST"])
@login_required
def api_history_clear():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    db.delete_user_searches(u["id"])
    return jsonify({"ok": True})


@app.route("/api/redeem", methods=["POST"])
@login_required
def api_redeem():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    d = request.get_json(force=True) or {}
    code = str(d.get("code", "")).strip().upper()
    if not code:
        return jsonify({"error": "enter a code"}), 400
    ok, msg = db.redeem_gift_code(code, u["id"])
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


# ---------- payment (test mode) ----------

@app.route("/api/payment/test", methods=["POST"])
@login_required
def api_payment_test():
    u = current_user()
    if not u:
        return jsonify({"error": "not found"}), 404
    d = request.get_json(force=True) or {}
    plan = str(d.get("plan", "")).lower()
    if plan not in PLANS:
        return jsonify({"error": "invalid plan"}), 400
    p = PLANS[plan]
    pid = db.create_payment_request(u["id"], plan, p["amount"], p["credits"], method="test")
    ok, msg = db.approve_payment(pid)
    if not ok:
        return jsonify({"error": msg}), 400
    u = db.get_user_by_id(u["id"])
    return jsonify({"ok": True, "credits_added": p["credits"], "credits": u["credits"]})


# ---------- admin ----------

@app.route("/api/admin/gift", methods=["POST"])
@admin_required
def api_admin_gift():
    u = current_user()
    d = request.get_json(force=True) or {}
    try:
        value = int(d.get("value", 10))
        max_uses = int(d.get("max_uses", 1))
        days = int(d.get("days", 30))
    except Exception:
        return jsonify({"error": "invalid numbers"}), 400
    plan = str(d.get("plan", "pro")).lower()
    if plan not in ("pro", "max", "enterprise"):
        return jsonify({"error": "invalid plan"}), 400
    expires_at = d.get("expires_at") or None
    code = db.create_gift_code(value=value, max_uses=max_uses, plan=plan, days=days,
                               expires_at=expires_at, created_by=u["id"])
    return jsonify({"ok": True, "code": code})


@app.route("/api/admin/codes", methods=["GET"])
@admin_required
def api_admin_codes():
    return jsonify({"ok": True, "codes": db.list_gift_codes()})


@app.route("/api/admin/codes/delete", methods=["POST"])
@admin_required
def api_admin_delete_code():
    d = request.get_json(force=True) or {}
    code = str(d.get("code", "")).strip().upper()
    if not code:
        return jsonify({"error": "invalid"}), 400
    db.delete_gift_code(code)
    return jsonify({"ok": True})


@app.route("/api/admin/users", methods=["GET"])
@admin_required
def api_admin_users():
    return jsonify({"ok": True, "users": db.list_users()})


@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def api_admin_stats():
    return jsonify({"ok": True, "stats": db.get_stats()})


@app.route("/api/admin/payments", methods=["GET"])
@admin_required
def api_admin_payments():
    return jsonify({"ok": True, "payments": db.list_payment_requests()})


@app.route("/api/admin/payments/approve", methods=["POST"])
@admin_required
def api_admin_approve_payment():
    d = request.get_json(force=True) or {}
    pid = int(d.get("id", 0))
    if not pid:
        return jsonify({"error": "invalid id"}), 400
    ok, msg = db.approve_payment(pid)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"ok": True, "message": msg})


@app.route("/api/admin/payments/reject", methods=["POST"])
@admin_required
def api_admin_reject_payment():
    d = request.get_json(force=True) or {}
    pid = int(d.get("id", 0))
    if not pid:
        return jsonify({"error": "invalid id"}), 400
    db.reject_payment(pid)
    return jsonify({"ok": True})


if __name__ == "__main__":
    db.init_db()
    print("[*] database ready")
    print("[*] server starting on http://0.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
