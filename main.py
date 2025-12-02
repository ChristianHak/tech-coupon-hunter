import requests
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime
import os
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random
import threading
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

TAVILY_KEY = os.environ.get('TAVILY_KEY')
EXA_KEY = os.environ.get('EXA_KEY')
BRAVE_KEY = os.environ.get('BRAVE_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GOOGLE_CX_LIST = os.environ.get('GOOGLE_CX', '').split(',') if os.environ.get('GOOGLE_CX') else []

GROQ_KEY = os.environ.get('GROQ_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')

GOOGLE_JSON_KEYFILE = "key.json"
SPREADSHEET_NAME = "Tech Deals 2025"
CACHE_FILE = "cache.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

app = Flask(__name__)

# === LISTE DES SERVICES (138+) === (colle ta liste complète ici, je la raccourcis pour la réponse)
FALLBACK_SERVICES = ["Porkbun", "Namecheap", ...]  # colle toute ta liste

# === GOOGLE SHEETS + CACHE + TELEGRAM === (le code exact que je t'ai donné avant)

# === TOUTES LES FONCTIONS (search_with_apis, crawl_page, extract_codes, discovery_new_services) === (exactement comme V6)

# === HUNT QUOTIDIEN ===
def run_hunt():
    now = datetime.now()
    if (now - datetime.fromisoformat(cache.get("last_hunt", "2000-01-01"))).total_seconds() < 86400:  # 24h
        return
    
    send_telegram("🔥 Chasse quotidienne lancée...")
    discovery_new_services()
    # ... tout le code de chasse
    send_telegram(f"✅ Chasse terminée → {new_deals} nouveaux deals !")

@app.route("/")
def home():
    threading.Thread(target=run_hunt).start()
    return "Tech Coupon Hunter alive – OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
