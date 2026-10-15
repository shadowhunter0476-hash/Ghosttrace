# language: Python 3.11+, file: phone_check.py
# *phone OSINT — country, whatsapp, telegram, truecaller.*

import re

COUNTRY_CODES = {
    "91": "India", "1": "USA/Canada", "44": "UK", "61": "Australia",
    "971": "UAE", "966": "Saudi Arabia", "92": "Pakistan",
    "880": "Bangladesh", "977": "Nepal", "94": "Sri Lanka",
    "86": "China", "81": "Japan", "82": "South Korea",
    "49": "Germany", "33": "France", "39": "Italy",
    "7": "Russia", "55": "Brazil", "27": "South Africa",
}


def normalize_phone(phone):
    return re.sub(r"\D", "", phone or "")


def valid_phone(phone):
    d = normalize_phone(phone)
    return 10 <= len(d) <= 15


def get_country(phone):
    d = normalize_phone(phone)
    for code, name in sorted(COUNTRY_CODES.items(), key=lambda x: -len(x[0])):
        if d.startswith(code):
            return name, code
    return "Unknown", None


def check_phone(phone):
    d = normalize_phone(phone)
    if not valid_phone(phone):
        return []

    country, code = get_country(d)
    if code and d.startswith(code):
        local = d[len(code):]
    else:
        local = d

    results = [
        {"name": "Country", "url": "", "info": country},
        {"name": "Full Number", "url": "", "info": f"+{d}"},
        {"name": "Local Number", "url": "", "info": local},
        {"name": "WhatsApp", "url": f"https://wa.me/{d}", "info": "click to check"},
        {"name": "Telegram", "url": f"https://t.me/+{d}", "info": "check if registered"},
        {"name": "Truecaller", "url": f"https://www.truecaller.com/search/in/{d}", "info": "caller ID search"},
        {"name": "Google Search", "url": f"https://www.google.com/search?q=%2B{d}", "info": "search this number"},
        {"name": "NumVerify", "url": f"https://numverify.com/", "info": "carrier lookup"},
    ]
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python phone_check.py <phone>")
        sys.exit(1)
    r = check_phone(sys.argv[1])
    for x in r:
        print(f"  {x['name']:<20} {x['info']}")
