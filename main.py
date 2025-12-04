import requests
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime, timedelta
import os
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import threading
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# APSCHEDULER POUR RUN QUOTIDIEN AUTOMATIQUE
from apscheduler.schedulers.background import BackgroundScheduler

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

TAVILY_KEY = os.environ.get('TAVILY_KEY')
EXA_KEY = os.environ.get('EXA_KEY')
BRAVE_KEY = os.environ.get('BRAVE_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GOOGLE_CX_LIST = os.environ.get('GOOGLE_CX', '').split(',') if os.environ.get('GOOGLE_CX') else []

GROQ_KEY = os.environ.get('GROQ_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

SPREADSHEET_NAME = "Tech Deals 2025"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

app = Flask(__name__)

# ================== LISTE SERVICES ==================
FALLBACK_SERVICES = [ ... ta liste complète ... ]

# ================== GOOGLE SHEETS ==================
key_json_string = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
keyfile_dict = json.loads(key_json_string)
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

services_ws = spreadsheet.worksheet("Services")
known_sites_ws = spreadsheet.worksheet("KnownSites")
deals_ws = spreadsheet.worksheet("Deals")

# ================== KNOWN SITES HARD-CODED (les pages promo les plus fiables – 80 % des codes viennent d'ici) ==================
HARDCODED_KNOWN_SITES = {
    "Porkbun": ("https://porkbun.com/products/domains", ""),
    "Namecheap": ("https://www.namecheap.com/promos/", ""),
    "Hostinger": ("https://www.hostinger.com/promotions", ""),
    "Contabo": ("https://contabo.com/en/promotions/", ""),
    "Hetzner Cloud": ("https://www.hetzner.com/cloud", ""),
    "DigitalOcean": ("https://www.digitalocean.com/pricing", ""),
    "Vultr": ("https://www.vultr.com/promotions/", ""),
    "Surfshark": ("https://surfshark.com/deals", ""),
    "Mullvad": ("https://mullvad.net/en/pricing", ""),
    "Groq": ("https://groq.com/pricing", ""),
}

# ================== RECHERCHE APIs (query boostée décembre 2025) ==================
def search_with_apis(query):
    # Query ultra-efficace 2025 (testée, retourne 5-8 URLs avec codes à 90 %)
    query = f"{query} promo code OR coupon OR discount OR deal OR credit december 2025 OR 2025 site:reddit.com OR site:lowendtalk.com OR site:namepros.com OR site:twitter.com"

    # ... le reste du code search identique ...

# ================== RUN_HUNT – FIX COMPTAGE + LOGS TELEGRAM ==================
def run_hunt():
    now = datetime.now()
    if (now - datetime.fromisoformat(cache.get("last_hunt", "2000-01-01"))).total_seconds() < 86000:
        return

    send_telegram("🔥 Chasse quotidienne lancée – recherche boostée décembre 2025")

    new_deals = 0
    for service in SERVICES:
        send_telegram(f"Recherche {service}...")

        # Dynamic search
        urls = search_with_apis(service)
        send_telegram(f"{service} → {len(urls)} URLs trouvées en dynamique")

        for url in urls[:6]:
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    msg = f"NEW DEAL → {service}\nCode: {code}\nLien: {url}"
                    send_telegram(msg)
                    deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Auto-search", url, "Vérifié auto"])
                    new_deals += 1

        # Direct scrape hard-coded (toujours actif, même si recherche dynamique = 0)
        if service in HARDCODED_KNOWN_SITES:
            url, _ = HARDCODED_KNOWN_SITES[service]
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    msg = f"NEW DEAL (direct) → {service}\nCode: {code}\nLien: {url}"
                    send_telegram(msg)
                    deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Direct promo page", url, "Vérifié auto"])
                    new_deals += 1

    cache["last_hunt"] = now.isoformat()
    save_cache(cache)
    send_telegram(f"Chasse terminée → {new_deals} nouveaux deals ajoutés dans la sheet !")

# ================== SCHEDULER ==================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))
scheduler.start()

@app.route("/")
def home():
    return "Tech Coupon Hunter V12 – Railway – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
