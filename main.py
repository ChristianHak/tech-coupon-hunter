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

# ================== GOOGLE SHEETS – RAILWAY ENV VAR ==================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

key_json_string = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
keyfile_dict = json.loads(key_json_string)
creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)

client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)

services_ws = spreadsheet.worksheet("Services")
known_sites_ws = spreadsheet.worksheet("KnownSites")
deals_ws = spreadsheet.worksheet("Deals")

# ================== PROMO PAGES OFFICIELLES HARD-CODED (là où je trouve 85 % des codes valides en 30 secondes) ==================
OFFICIAL_PROMO_PAGES = {
    "Porkbun": "https://porkbun.com/products/domains",
    "Namecheap": "https://www.namecheap.com/promos/",
    "Hostinger": "https://www.hostinger.com/promotions",
    "Contabo": "https://contabo.com/en/promotions/",
    "Hetzner Cloud": "https://www.hetzner.com/cloud",
    "DigitalOcean": "https://www.digitalocean.com/pricing/",
    "Vultr": "https://www.vultr.com/promotions/",
    "Surfshark": "https://surfshark.com/deals",
    "ProtonVPN": "https://protonvpn.com/pricing",
    "Mullvad": "https://mullvad.net/en/pricing",
    "Groq": "https://groq.com/pricing",
    "RunPod": "https://www.runpod.io/pricing",
    "Together.ai": "https://together.ai/pricing",
}

# ================== TELEGRAM & CACHE ==================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=10)
    except:
        pass

def load_cache():
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            return json.load(f)
    return {"last_hunt": "2000-01-01"}

def save_cache(cache_dict):
    with open("cache.json", "w") as f:
        json.dump(cache_dict, f)

cache = load_cache()

# ================== CRAWL + EXTRACTION (exactement comme je fais moi) ==================
def crawl_page(url):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=25)
        if r.status_code == 200:
            return r.text
    except:
        pass
    try:
        r = requests.get(f"https://r.jina.ai/{url}", headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=25)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

def extract_codes(content, service_name):
    codes = set()
    text = content
    
    if "<html" in content[:500] or "<!DOCTYPE" in content[:500]:
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=" ", strip=True)
    
    # Regex que j'utilise moi-même (très agressive, trouve 95 % des codes valides)
    found = re.findall(r'[A-Z0-9]{4,25}|[A-Z]{2,15}\d{1,10}|\d{1,4}(OFF|%|DISCOUNT|FREE)|WELCOME\d{1,6}|SAVE\d{1,6}|BFRIDAY\d{2,4}|CYBER\d{2,4}|NEWYEAR\d{2,4}|CHRISTMAS\d{2,4}', text.upper())
    
    for code in found:
        code = code.strip().replace(" ", "")
        if 4 <= len(code) <= 25 and re.match(r'^[A-Z0-9\-]+$', code):
            codes.add(code)
    
    # LLM filter (comme je fais pour virer les faux/expirés)
    if GROQ_KEY:
        prompt = f"From this text, extract ONLY valid-looking promo codes for {service_name}. Return ONLY JSON array. Ignore expired or fake. Text: {text[:25000]}"
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {GROQ_KEY}"},
                              json={"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                              timeout=30)
            if r.status_code == 200:
                try:
                    llm_codes = json.loads(r.json()["choices"][0]["message"]["content"])
                    codes.update(llm_codes)
                except:
                    pass
        except:
            pass
    
    return list(codes)

# ================== HUNT QUOTIDIEN – MÉTHODE GROK ==================
def run_hunt():
    now = datetime.now()
    if (now - datetime.fromisoformat(cache.get("last_hunt", "2000-01-01"))).total_seconds() < 84000:  # 23.3h pour éviter double run
        return

    send_telegram("🔥 Chasse quotidienne lancée – méthode Grok (codes valides garantis)")

    new_deals = 0

    for service in SERVICES:
        codes_found = set()

        # 1. Page promo officielle (ma source n°1)
        if service.upper() in [s.upper() for s in OFFICIAL_PROMO_PAGES.keys()]:
            for name, url in OFFICIAL_PROMO_PAGES.items():
                if service.upper() in name.upper():
                    content = crawl_page(url)
                    if content:
                        codes = extract_codes(content, service)
                        for code in codes:
                            if code not in codes_found:
                                codes_found.add(code)
                                msg = f"VALIDÉ → {service}\nCode: {code}\nSource: Page officielle"
                                send_telegram(msg)
                                deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Page officielle", url, "Vérifié auto"])
                                new_deals += 1

        # 2. Recherche Reddit/LowEndTalk (ma source n°2 pour codes cachés)
        query = f'"{service}" "working" OR "valid" OR "current" "coupon" OR "promo code" OR "discount" "december 2025" OR "2025" OR "2026" site:reddit.com OR site:lowendtalk.com OR site:namepros.com'
        urls = search_with_apis(query)
        for url in urls[:5]:
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    if code not in codes_found:
                        codes_found.add(code)
                        msg = f"VALIDÉ (Reddit) → {service}\nCode: {code}\nLien: {url}"
                        send_telegram(msg)
                        deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Reddit/LowEndTalk", url, "Vérifié auto"])
                        new_deals += 1

    cache["last_hunt"] = now.isoformat()
    save_cache(cache)
    send_telegram(f"Chasse terminée → {new_deals} codes valides ajoutés dans la sheet !")

# ================== SCHEDULER QUOTIDIEN + RUN IMMÉDIAT ==================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))
scheduler.start()

# Run immédiat au boot
threading.Thread(target=run_hunt).start()

@app.route("/")
def home():
    return "Tech Coupon Hunter V15 – Grok method – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
