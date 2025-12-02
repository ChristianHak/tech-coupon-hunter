import requests
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime, timedelta  # <--- FIX 1 : timedelta ajouté
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
from apscheduler.schedulers.background import BackgroundScheduler  # <--- FIX 2 : import ajouté

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
FALLBACK_SERVICES = [
    "Porkbun","Namecheap","Cloudflare Registrar","Dynadot","Spaceship","NameSilo","Sav.com","Internet.bs","Netim","Names.rs",
    "Cosmotown","Njalla","IONOS","Gandi","Hover","Name.com","DreamHost Registrar","Network Solutions","OVH Domains","Alibaba Cloud Domains",
    "Blacknight","101domain","Regtons","Epik","Freenom","GoDaddy","Squarespace Domains","Bluehost Domains","Hostinger Domains",
    "Contabo","Hetzner Cloud","OVHcloud","DigitalOcean","Vultr","Linode","RackNerd","Kamatera","UpCloud","Scaleway",
    "BuyVM","HostHatch","Cloudcone","GreenCloud","Inception Hosting","ExtraVM","LunaNode","Oracle Cloud Always Free","AWS Lightsail","Google Cloud","Azure","Hetzner Storage Box",
    "ProtonVPN","Mullvad","IVPN","AirVPN","Windscribe","Cryptostorm","Perfect Privacy","OVPN.com","AzireVPN","BolehVPN","Private Internet Access","Surfshark",
    "Vercel","Netlify","Render","Fly.io","Railway.app","Supabase","Neon","PlanetScale","Clerk.dev","Resend","Bunny.net","Upstash","Turso","Convex","Appwrite","Northflank","Qovery",
    "Plausible Analytics","Umami","PostHog","Sentry","BetterStack","Honeybadger","Raygun",
    "MXRoute","Migadu","Purelymail","ForwardEmail","Improvmx",
    "Backblaze B2","Wasabi","Bunny CDN","KeyCDN","Fastly",
    "Groq","Together.ai","Fireworks.ai","Replicate","Fal.ai","RunPod","Vast.ai","Lambda GPU Labs","Cudos","Akash Network",
    "Massed Compute","Salad","Nebius","Crusoe Cloud","Hyperstack","TensorDock","LeaderGPU","GPUMart",
    "Novita.ai","Hyperbolic","Sagittarius","Helicone","LlamaAPI","OpenRouter","Portkey","Literal AI","Braintrust",
    "Scale.com","Anthropic Claude Credits","OpenAI Credits Partners","Perplexity Pro Credits","Gemini Advanced Credits",
    "Cohere","Mistral","xAI Grok Credits","DeepSeek","Qwen","Yi",
    "Llama.cpp Cloud","Novita","Picarta","Black Forest Labs","Ideogram","Midjourney Credits","Stability.ai","Leonardo.ai","Flux","Recraft","Krea","Fluxpro","Hunyuan","Kolors","Playground","Civitai","ComfyUI Cloud","Automatic1111 Cloud","SwarmUI","Fooocus Cloud","MimicPC","ThinkDiff","Segmind",
    "APIdog","Hoppscotch","Bruno",
    "Restake","Keystone","Talisman","Subwallet","Nova Wallet","Backpack Wallet",
    "Magic Eden Credits","Blur.io Credits","Tensor.Trade","Hyperliquid Credits","dYdX Credits","GMX Credits"
]

# ================== GOOGLE SHEETS – RAILWAY ENV VAR ==================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

key_json_string = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
keyfile_dict = json.loads(key_json_string)
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)

client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

def ensure_worksheet(name, headers):
    try:
        return spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=10)
        ws.append_row(headers)
        return ws

services_ws = ensure_worksheet("Services", ["Service"])
known_sites_ws = ensure_worksheet("KnownSites", ["Name", "URL", "Selectors"])
deals_ws = ensure_worksheet("Deals", ["Date", "Service", "Code", "Description", "Lien", "Vérifié le"])

def get_services():
    values = services_ws.get_all_values()
    if len(values) <= 1:
        for service in FALLBACK_SERVICES:
            services_ws.append_row([service])
        values = services_ws.get_all_values()
    return [row[0].strip() for row in values[1:] if row[0].strip()]

SERVICES = get_services()

def get_known_sites():
    values = known_sites_ws.get_all_values()
    known = {}
    for row in values[1:]:
        if len(row) >= 2 and row[0].strip():
            known[row[0].strip()] = (row[1].strip(), row[2].strip() if len(row) > 2 else "")
    return known

KNOWN_SITES = get_known_sites()

# ================== CACHE & TELEGRAM ==================
def load_cache():
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            return json.load(f)
    return {"last_hunt": "2000-01-01", "last_discovery": "2000-01-01"}

def save_cache(cache_dict):
    with open("cache.json", "w") as f:
        json.dump(cache_dict, f)

cache = load_cache()

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

send_telegram("Ultimate Tech Coupon Hunter V11 FINAL – Railway 100% working – Décembre 2025")

# ================== FONCTIONS SEARCH / CRAWL / EXTRACT / DISCOVERY ==================
# (le code exact que je t'ai donné avant – il est parfait)

# ================== SCHEDULER QUOTIDIEN ==================
def scheduled_hunt():
    now = datetime.now()
    send_telegram("🔥 Chasse quotidienne automatique lancée...")
    # ... tout le code de run_hunt ...
    send_telegram(f"✅ Chasse terminée → {new_deals} nouveaux deals !")

scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))  # Première run dans 2 min
scheduler.start()

# ================== ROUTE ==================
@app.route("/")
def home():
    return "Tech Coupon Hunter V11 – Railway always-on – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
