# language: Python 3.11+, file: sites.py
# *2 tier: trusted (55 handpicked, accurate) + sherlock (481).*

import json
import os

SHERLOCK_DATA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "sherlock_data.json"
)

# ---------- TIER 1: handpicked trusted sites ----------
TRUSTED_SITES = [
    # Developer
    {"name": "GitHub", "url": "https://github.com/{}", "errorType": "status_code"},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "errorType": "status_code"},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{}", "errorType": "status_code"},
    {"name": "Dev.to", "url": "https://dev.to/{}", "errorType": "status_code"},
    {"name": "CodePen", "url": "https://codepen.io/{}", "errorType": "status_code"},
    {"name": "Replit", "url": "https://replit.com/@{}", "errorType": "status_code"},
    {"name": "HackerRank", "url": "https://www.hackerrank.com/{}", "errorType": "status_code"},
    {"name": "LeetCode", "url": "https://leetcode.com/{}", "errorType": "status_code"},
    {"name": "Kaggle", "url": "https://www.kaggle.com/{}", "errorType": "status_code"},
    {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={}", "errorType": "message", "errorMsg": "No such user."},
    {"name": "ProductHunt", "url": "https://www.producthunt.com/@{}", "errorType": "status_code"},
    {"name": "NPM", "url": "https://www.npmjs.com/~{}", "errorType": "status_code"},
    {"name": "PyPI", "url": "https://pypi.org/user/{}", "errorType": "status_code"},

    # Social
    {"name": "Twitter/X", "url": "https://twitter.com/{}", "errorType": "status_code"},
    {"name": "Instagram", "url": "https://www.instagram.com/{}", "errorType": "status_code"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "errorType": "status_code"},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "errorType": "status_code"},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}", "errorType": "status_code"},
    {"name": "Tumblr", "url": "https://{}.tumblr.com", "errorType": "status_code"},
    {"name": "Medium", "url": "https://medium.com/@{}", "errorType": "status_code"},
    {"name": "Quora", "url": "https://www.quora.com/profile/{}", "errorType": "status_code"},
    {"name": "Mastodon", "url": "https://mastodon.social/@{}", "errorType": "status_code"},
    {"name": "Bluesky", "url": "https://bsky.app/profile/{}.bsky.social", "errorType": "status_code"},
    {"name": "Threads", "url": "https://www.threads.net/@{}", "errorType": "status_code"},
    {"name": "Telegram", "url": "https://t.me/{}", "errorType": "status_code"},
    {"name": "Discord", "url": "https://discord.com/users/{}", "errorType": "status_code"},
    {"name": "VK", "url": "https://vk.com/{}", "errorType": "status_code"},

    # Video / Music
    {"name": "YouTube", "url": "https://www.youtube.com/@{}", "errorType": "status_code"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "errorType": "status_code"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "errorType": "status_code"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "errorType": "status_code"},
    {"name": "Bandcamp", "url": "https://{}.bandcamp.com", "errorType": "status_code"},
    {"name": "Last.fm", "url": "https://www.last.fm/user/{}", "errorType": "status_code"},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "errorType": "status_code"},
    {"name": "Dailymotion", "url": "https://www.dailymotion.com/{}", "errorType": "status_code"},

    # Gaming
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "errorType": "status_code"},
    {"name": "Roblox", "url": "https://www.roblox.com/user.aspx?username={}", "errorType": "status_code"},
    {"name": "NameMC", "url": "https://namemc.com/profile/{}", "errorType": "status_code"},
    {"name": "Xbox", "url": "https://xboxgamertag.com/search/{}", "errorType": "status_code"},

    # Professional / Design
    {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{}", "errorType": "status_code"},
    {"name": "Behance", "url": "https://www.behance.net/{}", "errorType": "status_code"},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "errorType": "status_code"},
    {"name": "AngelList", "url": "https://angel.co/u/{}", "errorType": "status_code"},

    # Blogging
    {"name": "WordPress", "url": "https://{}.wordpress.com", "errorType": "status_code"},
    {"name": "Blogger", "url": "https://{}.blogspot.com", "errorType": "status_code"},
    {"name": "Substack", "url": "https://{}.substack.com", "errorType": "status_code"},
    {"name": "Wattpad", "url": "https://www.wattpad.com/user/{}", "errorType": "status_code"},

    # Commerce
    {"name": "eBay", "url": "https://www.ebay.com/usr/{}", "errorType": "status_code"},
    {"name": "Etsy", "url": "https://www.etsy.com/shop/{}", "errorType": "status_code"},

    # Misc
    {"name": "About.me", "url": "https://about.me/{}", "errorType": "status_code"},
    {"name": "Imgur", "url": "https://imgur.com/user/{}", "errorType": "status_code"},
    {"name": "9GAG", "url": "https://9gag.com/u/{}", "errorType": "status_code"},
    {"name": "Flickr", "url": "https://www.flickr.com/people/{}", "errorType": "status_code"},
    {"name": "Gravatar", "url": "https://gravatar.com/{}", "errorType": "status_code"},
    {"name": "Keybase", "url": "https://keybase.io/{}", "errorType": "status_code"},
]


def load_sherlock_sites():
    if not os.path.exists(SHERLOCK_DATA):
        return []
    with open(SHERLOCK_DATA, "r", encoding="utf-8") as f:
        raw = json.load(f)
    sites = []
    for name, info in raw.items():
        if name.startswith("$") or not isinstance(info, dict):
            continue
        url = info.get("url")
        if not url:
            continue
        sites.append({
            "name": name,
            "url": url,
            "errorType": info.get("errorType", "status_code"),
            "errorMsg": info.get("errorMsg"),
        })
    return sites


SHERLOCK_SITES = load_sherlock_sites()
SITES = TRUSTED_SITES


def get_sites(mode="trusted"):
    if mode == "all":
        return TRUSTED_SITES + SHERLOCK_SITES
    return TRUSTED_SITES


if __name__ == "__main__":
    print(f"[+] trusted: {len(TRUSTED_SITES)}")
    print(f"[+] sherlock: {len(SHERLOCK_SITES)}")
    print(f"[+] total (all mode): {len(TRUSTED_SITES) + len(SHERLOCK_SITES)}")
