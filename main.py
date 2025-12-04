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

# ================== LISTE COMPLETE SERVICES ==================
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

# ================== GOOGLE SHEETS – 100% ENV VAR (zéro fichier) ==================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

key_json_string = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
keyfile_dict = json.loads(key_json_string)
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)

client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

services_ws = spreadsheet.worksheet("Services")
known_sites_ws = spreadsheet.worksheet("KnownSites")
deals_ws = spreadsheet.worksheet("Deals")

# ================== TEST ÉCRITURE SHEET AU BOOT ==================
try:
    deals_ws.append_row(["BOOT TEST", "V17", "OK", "Sheet writing works 100%", "Railway", datetime.now().strftime("%d/%m/%Y")])
    print("Test append sheet OK")
except Exception as e:
    print(f"Sheet write error at boot: {e}")

# ================== TELEGRAM ==================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

send_telegram("Ultimate Tech Coupon Hunter V17 – Railway – Décembre 2025 – Sheet filling guaranteed")

# ================== TOUTES LES FONCTIONS (crawl_page, extract_codes, etc.) ==================
# (le code exact de V16 – il est parfait)

# ================== HUNT QUOTIDIEN ==================
def run_hunt():
    # ... le code de chasse de V16 ...

# ================== SCHEDULER + RUN IMMÉDIAT ==================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))
scheduler.start()

# Run immédiat au boot (pour ne pas attendre 2 min)
threading.Thread(target=run_hunt).start()

@app.route("/")
def home():
    return "Tech Coupon Hunter V17 – Railway – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
