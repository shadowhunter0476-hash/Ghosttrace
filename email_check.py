# language: Python 3.11+, file: email_check.py
# *email OSINT — gravatar, github, domain, breaches.*

import asyncio
import aiohttp
import re
import hashlib

REQ_TIMEOUT = 10
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


def valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip().lower()))


async def check_gravatar(session, email):
    h = hashlib.md5(email.strip().lower().encode()).hexdigest()
    url = f"https://www.gravatar.com/avatar/{h}?d=404"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT), ssl=False) as r:
            if r.status == 200:
                return {"name": "Gravatar Profile", "url": f"https://www.gravatar.com/{h}", "info": "profile exists"}
    except Exception:
        pass
    return None


async def check_github_email(session, email):
    url = f"https://api.github.com/search/users?q={email}+in:email"
    try:
        async with session.get(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
                               timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT), ssl=False) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("total_count", 0) > 0:
                    items = data.get("items", [])[:3]
                    return [{"name": f"GitHub (@{it['login']})", "url": it["html_url"], "info": "email matched"} for it in items]
    except Exception:
        pass
    return []


async def check_email(email, on_result=None):
    email = email.strip().lower()
    if not valid_email(email):
        return []

    found = []
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_gravatar(session, email), check_github_email(session, email)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                found.extend(r)
            elif r:
                found.append(r)

    domain = email.split("@")[-1]
    found.append({"name": "Email Domain", "url": f"https://{domain}", "info": domain})
    found.append({"name": "Google Search", "url": f"https://www.google.com/search?q=%22{email}%22", "info": "search this email"})
    found.append({"name": "HaveIBeenPwned", "url": f"https://haveibeenpwned.com/account/{email}", "info": "breach check"})

    return found


def check_email_sync(email):
    return asyncio.run(check_email(email))


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 2:
        print("usage: python email_check.py <email>")
        sys.exit(1)
    e = sys.argv[1]
    print(f"[*] checking {e}...")
    t0 = time.time()
    r = check_email_sync(e)
    print(f"\n[+] {len(r)} found in {time.time()-t0:.1f}s\n")
    for x in r:
        print(f"  OK  {x['name']:<25} {x.get('info','')}")
