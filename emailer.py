# language: Python 3.11+, file: emailer.py
# *Gmail SMTP — OTP, reset password emails.*

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ⬇️ tera Gmail
GMAIL_USER = "shadowhunter0476@gmail.com"
# ⬇️ tera App Password (16 chars, spaces ke bina)
GMAIL_APP_PASS = "mwvjicmnnullrvcf"


def send_email(to, subject, html_body):
    """raw email bhejo — returns (success, message)"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"GhostTrace <{GMAIL_USER}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.sendmail(GMAIL_USER, to, msg.as_string())
        return True, "sent"
    except Exception as e:
        return False, str(e)


def send_otp_email(to_email, otp_code):
    """signup OTP email"""
    subject = "GhostTrace — Verify Your Email"
    html = f"""
    <div style="font-family:Inter,sans-serif;background:#0a0e1a;color:#e6edf3;padding:40px;text-align:center">
      <h1 style="color:#60a5fa;margin:0 0 10px">👻 GhostTrace</h1>
      <h2 style="margin:0 0 20px">Verify Your Email</h2>
      <p style="color:#c9d1d9">Your 6-digit verification code:</p>
      <div style="display:inline-block;padding:20px 40px;background:#111827;border:2px solid #3b82f6;border-radius:12px;margin:20px 0">
        <span style="font-size:36px;font-weight:900;letter-spacing:10px;color:#60a5fa;font-family:monospace">{otp_code}</span>
      </div>
      <p style="color:#8b949e;font-size:12px">This code expires in 10 minutes.</p>
      <p style="color:#8b949e;font-size:12px">If you didn't request this, ignore this email.</p>
      <hr style="border:0;border-top:1px solid #1f2937;margin:30px 0">
      <p style="color:#6e7681;font-size:11px">MADE BY AFTAB · @shadow0476</p>
    </div>
    """
    return send_email(to_email, subject, html)


def send_reset_email(to_email, reset_link):
    """password reset email"""
    subject = "GhostTrace — Password Reset"
    html = f"""
    <div style="font-family:Inter,sans-serif;background:#0a0e1a;color:#e6edf3;padding:40px;text-align:center">
      <h1 style="color:#60a5fa;margin:0 0 10px">👻 GhostTrace</h1>
      <h2 style="margin:0 0 20px">Reset Your Password</h2>
      <p style="color:#c9d1d9">Click the button below to set a new password:</p>
      <a href="{reset_link}" style="display:inline-block;padding:14px 30px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;text-decoration:none;border-radius:10px;font-weight:700;margin:20px 0">Reset Password</a>
      <p style="color:#8b949e;font-size:12px">Link expires in 1 hour.</p>
      <hr style="border:0;border-top:1px solid #1f2937;margin:30px 0">
      <p style="color:#6e7681;font-size:11px">MADE BY AFTAB · @shadow0476</p>
    </div>
    """
    return send_email(to_email, subject, html)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python emailer.py <to_email>")
        sys.exit(1)
    print(f"[*] test email to {sys.argv[1]}...")
    ok, msg = send_email(sys.argv[1], "Test", "<h1>✅ Working</h1>")
    print("[+] sent" if ok else f"[!] failed: {msg}")
