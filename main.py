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

# APSCHEDULER POUR RUN QUOTIDIEN AUTOMATIQUE (zéro pinger, zéro visite nécessaire)
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

# ================== GOOGLE SHEETS – 100% ENV VAR (Railway december 2025) ==================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    key_json_string = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
    keyfile_dict = json.loads(key_json_string)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
except Exception as e:
    print(f"ERROR loading Google credentials: {e}")
    creds = None  # Will crash later if used, but app boots

if creds:
    client = gspread.authorize(creds)
    spreadsheet = client.open(SPREADSHEET_NAME)
else:
    spreadsheet = None
    print("Google Sheets disabled – check GOOGLE_SERVICE_ACCOUNT_JSON variable")

# ... (ensure_worksheet, get_services, etc. with if spreadsheet: guards if you want, but for simplicity we assume it's set)

# ================== TOUTES LES FONCTIONS (identiques) ==================

# ================== SCHEDULER QUOTIDIEN ==================
def scheduled_hunt():
    if not spreadsheet:
        return
    now = datetime.now()
    send_telegram("🔥 Chasse quotidienne automatique lancée...")
    # ... tout le code de run_hunt ...
    send_telegram(f"✅ Chasse terminée → {new_deals} nouveaux deals !")

scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=1))  # Première run dans 1 min
scheduler.start()

# ================== ROUTE (pour health check) ==================
@app.route("/")
def home():
    return "Tech Coupon Hunter V10 – Railway always-on daily hunter – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
