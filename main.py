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

# ================== GOOGLE SHEETS ==================
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

# ================== TEST APPEND AU BOOT (pour vérifier que la sheet marche) ==================
try:
    deals_ws.append_row(["TEST BOOT", "TEST", "TEST_OK", "If you see this line, sheet writing works 100%", "https://railway.app", datetime.now().strftime("%d/%m/%Y")])
    send_telegram("✅ Test append sheet OK – writing works")
except Exception as e:
    send_telegram(f"ERROR sheet write at boot: {e}")

# ================== OFFICIAL PROMO PAGES HARD-CODED (ma source n°1 – codes valides instantanés) ==================
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
    "Replicate": "https://replicate.com/pricing",
    "Linode": "https://www.linode.com/pricing/",
    "OVHcloud": "https://www.ovhcloud.com/en/promotions/",
    "Cloudflare Registrar": "https://www.cloudflare.com/products/registrar/",
    "Spaceship": "https://www.spaceship.com/pricing/",
    "Dynadot": "https://www.dynadot.com/promotion",
    "NameSilo": "https://www.namesilo.com/promotions",
    "Sav.com": "https://sav.com/promotions",
    "IONOS": "https://www.ionos.com/domains/domain-promotion",
    "Gandi": "https://www.gandi.net/en/promotion",
    "Hover": "https://www.hover.com/promotions/",
}

# ================== TELEGRAM & CACHE ==================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def load_cache():
    if os.path.exists("cache.json"):
        with open("cache.json", "r") as f:
            return json.load(f)
    return {"last_hunt": "2000-01-01"}

def save_cache(cache_dict):
    with open("cache.json", "w") as f:
        json.dump(cache_dict, f)

cache = load_cache()

send_telegram("🚀 Ultimate Tech Coupon Hunter V16 – Grok method December 2025 – Sheet will be filled")

# ================== CRAWL + EXTRACTION ==================
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
    
    found = re.findall(r'[A-Z0-9]{4,30}|[A-Z]{2,20}\d{1,10}|\d{1,4}(OFF|%|DISCOUNT|FREE)|WELCOME\d{1,8}|SAVE\d{1,8}|BFRIDAY\d{2,4}|CYBER\d{2,4}|NEWYEAR\d{2,4}|CHRISTMAS\d{2,4}|FLASH\d{2,4}|SUMMER\d{2,4}|MATRIX\w+', text.upper())
    
    for code in found:
        code = code.strip().replace(" ", "")
        if 4 <= len(code) <= 30 and re.match(r'^[A-Z0-9\-]+$', code):
            codes.add(code)
    
    if GROQ_KEY:
        prompt = f"Extract ONLY valid-looking promo codes for {service_name} from this text. Return ONLY JSON array. Ignore expired. Text: {text[:25000]}"
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

# ================== HUNT QUOTIDIEN ==================
def run_hunt():
    now = datetime.now()
    if (now - datetime.fromisoformat(cache.get("last_hunt", "2000-01-01"))).total_seconds() < 84000:
        return

    send_telegram("🔥 Chasse quotidienne lancée – méthode Grok décembre 2025")

    new_deals = 0

    for service in SERVICES:
        send_telegram(f"--- Recherche {service} ---")
        codes_found = set()

        # 1. Page promo officielle
        for name, url in OFFICIAL_PROMO_PAGES.items():
            if service.upper() in name.upper():
                content = crawl_page(url)
                if content:
                    codes = extract_codes(content, service)
                    send_telegram(f"{service} → {len(codes)} codes trouvés sur page officielle")
                    for code in codes:
                        if code not in codes_found:
                            codes_found.add(code)
                            msg = f"VALIDÉ → {service}\nCode: {code}\nSource: Page officielle"
                            send_telegram(msg)
                            try:
                                deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Page officielle", url, "Vérifié auto"])
                                new_deals += 1
                            except Exception as e:
                                send_telegram(f"ERROR append sheet: {e}")

        # 2. Recherche Reddit etc.
        query = f'"{service}" ("working" OR "valid" OR "current") ("coupon" OR "promo code") ("december 2025" OR "2025" OR "2026") site:reddit.com OR site:lowendtalk.com OR site:namepros.com OR site:twitter.com'
        urls = search_with_apis(query)
        send_telegram(f"{service} → {len(urls)} URLs Reddit/Twitter trouvées")
        for url in urls[:5]:
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    if code not in codes_found:
                        codes_found.add(code)
                        msg = f"VALIDÉ (Reddit) → {service}\nCode: {code}\nLien: {url}"
                        send_telegram(msg)
                        try:
                            deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Reddit/Twitter", url, "Vérifié auto"])
                            new_deals += 1
                        except Exception as e:
                            send_telegram(f"ERROR append sheet: {e}")

    cache["last_hunt"] = now.isoformat()
    save_cache(cache)
    send_telegram(f"✅ Chasse terminée → {new_deals} codes valides ajoutés dans la sheet !")

# ================== SCHEDULER + RUN IMMÉDIAT ==================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))
scheduler.start()

# Run immédiat au boot
threading.Thread(target=run_hunt).start()

@app.route("/")
def home():
    return "Tech Coupon Hunter V16 – Railway – Décembre 2025", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
