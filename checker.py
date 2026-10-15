# language: Python 3.11+, file: checker.py
# *481 sites parallel check — sherlock errorType support.*

import asyncio
import aiohttp
import re
import time

from sites import SITES

REQ_TIMEOUT = 5
CONCURRENCY = 100
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def valid_username(username):
    return bool(re.match(r"^[A-Za-z0-9._-]{1,40}$", username))


async def check_site(session, site, username):
    name = site["name"]
    url = site["url"].format(username)
    errorType = site.get("errorType", "status_code")
    errorMsg = site.get("errorMsg")

    try:
        headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with session.get(
            url, headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT),
            allow_redirects=True, ssl=False,
        ) as r:
            status = r.status

            if errorType == "status_code":
                if 200 <= status < 300:
                    return {"name": name, "url": url, "status": status}
                return None

            elif errorType == "message":
                if errorMsg:
                    try:
                        text = await r.text()
                    except Exception:
                        text = ""
                    if errorMsg.lower() in text.lower():
                        return None
                if 200 <= status < 300:
                    return {"name": name, "url": url, "status": status}
                return None

            elif errorType == "response_url":
                if 200 <= status < 300:
                    return {"name": name, "url": url, "status": status}
                return None

            if 200 <= status < 300:
                return {"name": name, "url": url, "status": status}
            return None

    except Exception:
        return None


async def check_username(username, on_result=None):
    if not valid_username(username):
        return []

    found = []
    sem = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY * 2,
        limit_per_host=5,
        ttl_dns_cache=600,
        ssl=False,
    )

    async def wrapped(site, session):
        async with sem:
            res = await check_site(session, site, username)
            if res:
                found.append(res)
                if on_result:
                    try:
                        await on_result(res)
                    except Exception:
                        pass

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [asyncio.create_task(wrapped(s, session)) for s in SITES]
        await asyncio.gather(*tasks, return_exceptions=True)

    return found


def check_username_sync(username):
    return asyncio.run(check_username(username))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python checker.py <username>")
        sys.exit(1)
    u = sys.argv[1]
    print(f"[*] checking {u} on {len(SITES)} sites...")
    t0 = time.time()
    results = check_username_sync(u)
    dt = time.time() - t0
    print(f"\n[+] {len(results)} found in {dt:.1f}s\n")
    for r in sorted(results, key=lambda x: x["name"]):
        print(f"  OK  {r['name']:<20} {r['url']}")
