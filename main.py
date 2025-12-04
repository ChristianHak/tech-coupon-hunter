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

# ================== LISTE COMPLETE SERVICES (138+) ==================
FALLBACK_SERVICES = [
    "Porkbun", "Namecheap", "Cloudflare Registrar", "Dynadot", "Spaceship", "NameSilo", "Sav.com", "Internet.bs", "Netim", "Names.rs",
    "Cosmotown", "Njalla", "IONOS", "Gandi", "Hover", "Name.com", "DreamHost Registrar", "Network Solutions", "OVH Domains", "Alibaba Cloud Domains",
    "Blacknight", "101domain", "Regtons", "Epik", "Freenom", "GoDaddy", "Squarespace Domains", "Bluehost Domains", "Hostinger Domains",
    "Contabo", "Hetzner Cloud", "OVHcloud", "DigitalOcean", "Vultr", "Linode", "RackNerd", "Kamatera", "UpCloud", "Scaleway",
    "BuyVM", "HostHatch", "Cloudcone", "GreenCloud", "Inception Hosting", "ExtraVM", "LunaNode", "Oracle Cloud Always Free", "AWS Lightsail", "Google Cloud", "Azure", "Hetzner Storage Box",
    "ProtonVPN", "Mullvad", "IVPN", "AirVPN", "Windscribe", "Cryptostorm", "Perfect Privacy", "OVPN.com", "AzireVPN", "BolehVPN", "Private Internet Access", "Surfshark",
    "Vercel", "Netlify", "Render", "Fly.io", "Railway.app", "Supabase", "Neon", "PlanetScale", "Clerk.dev", "Resend", "Bunny.net", "Upstash", "Turso", "Convex", "Appwrite", "Northflank", "Qovery",
    "Plausible Analytics", "Umami", "PostHog", "Sentry", "BetterStack", "Honeybadger", "Raygun",
    "MXRoute", "Migadu", "Purelymail", "ForwardEmail", "Improvmx",
    "Backblaze B2", "Wasabi", "Bunny CDN", "KeyCDN", "Fastly",
    "Groq", "Together.ai", "Fireworks.ai", "Replicate", "Fal.ai", "RunPod", "Vast.ai", "Lambda GPU Labs", "Cudos", "Akash Network",
    "Massed Compute", "Salad", "Nebius", "Crusoe Cloud", "Hyperstack", "TensorDock", "LeaderGPU", "GPUMart",
    "Novita.ai", "Hyperbolic", "Sagittarius", "Helicone", "LlamaAPI", "OpenRouter", "Portkey", "Literal AI", "Braintrust",
    "Scale.com", "Anthropic Claude Credits", "OpenAI Credits Partners", "Perplexity Pro Credits", "Gemini Advanced Credits",
    "Cohere", "Mistral", "xAI Grok Credits", "DeepSeek", "Qwen", "Yi",
    "Llama.cpp Cloud", "Novita", "Picarta", "Black Forest Labs", "Ideogram", "Midjourney Credits", "Stability.ai", "Leonardo.ai", "Flux", "Recraft", "Krea", "Fluxpro", "Hunyuan", "Kolors", "Playground", "Civitai", "ComfyUI Cloud", "Automatic1111 Cloud", "SwarmUI", "Fooocus Cloud", "MimicPC", "ThinkDiff", "Segmind",
    "APIdog", "Hoppscotch", "Bruno",
    "Restake", "Keystone", "Talisman", "Subwallet", "Nova Wallet", "Backpack Wallet",
    "Magic Eden Credits", "Blur.io Credits", "Tensor.Trade", "Hyperliquid Credits", "dYdX Credits", "GMX Credits"
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

send_telegram("🚀 Ultimate Tech Coupon Hunter V13 FINAL – Railway – Décembre 2025 – Run quotidien automatique")

# ================== RECHERCHE APIs ==================
def search_with_apis(query):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    if TAVILY_KEY:
        try:
            r = requests.post("https://api.tavily.com/search", json={"api_key": TAVILY_KEY, "query": query, "search_depth": "advanced", "max_results": 10}, timeout=15)
            if r.status_code == 200:
                return [item["url"] for item in r.json().get("results", [])[:8]]
        except:
            pass

    if EXA_KEY:
        try:
            r = requests.post("https://api.exa.ai/search", headers={"x-api-key": EXA_KEY}, json={"query": query, "numResults": 10}, timeout=15)
            if r.status_code == 200:
                return [item["url"] for item in r.json().get("results", [])[:8]]
        except:
            pass

    if BRAVE_KEY:
        try:
            r = requests.get(f"https://api.search.brave.com/res/v1/web/search?q={query}&count=10", headers={"X-Subscription-Token": BRAVE_KEY}, timeout=15)
            if r.status_code == 200:
                return [item["url"] for item in r.json().get("web", {}).get("results", [])[:8]]
        except:
            pass

    if GOOGLE_API_KEY and GOOGLE_CX_LIST:
        try:
            cx_index = cache.get("google_cx_index", 0) % len(GOOGLE_CX_LIST)
            cx = GOOGLE_CX_LIST[cx_index]
            cache["google_cx_index"] = cx_index + 1
            save_cache(cache)
            r = requests.get(f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={cx}", timeout=15)
            if r.status_code == 200:
                return [item["link"] for item in r.json().get("items", [])[:8]]
        except:
            pass
    
    return []

# ================== CRAWL PAGE ==================
def crawl_page(url):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.text
    except:
        pass
    try:
        r = requests.get(f"https://r.jina.ai/{url}", headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=20)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None

# ================== EXTRACTION CODES ==================
def extract_codes(content, service_name):
    codes = set()
    text = content
    
    if "<html" in content[:500] or "<!DOCTYPE" in content[:500]:
        try:
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text(separator=" ", strip=True)
        except:
            text = content
    
    found = re.findall(r'[A-Z0-9]{5,25}|[A-Z]{3,20}\d{1,10}|\d{2,4}(OFF|%|DISCOUNT|FREE)|WELCOME\d{1,6}|SAVE\d{1,6}|SPRING\d{2,4}|BLACKFRIDAY\d{2,4}|CYBER\d{2,4}|HOLIDAY\d{2,4}', text.upper())
    
    for code in found:
        code = code.strip().replace(" ", "").replace("\n", "")
        if 5 <= len(code) <= 25 and re.match(r'^[A-Z0-9\-]+$', code):
            codes.add(code)
    
    if GROQ_KEY or GEMINI_KEY:
        prompt = f"""Extract ALL valid-looking promo codes for {service_name} from this text. 
Return ONLY a valid JSON array like ["ABC123", "WELCOME20"]. Ignore expired ones if obvious. If none, return [].

Text:
{text[:28000]}"""
        try:
            if GROQ_KEY:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2},
                    timeout=25
                )
                if r.status_code == 200:
                    try:
                        llm_codes = json.loads(r.json()["choices"][0]["message"]["content"].strip("```json").strip("```").strip())
                        codes.update(llm_codes)
                    except:
                        pass
        except:
            pass
    
    return list(codes)

# ================== AUTO-DISCOVERY (hebdo) ==================
def discovery_new_services():
    if (datetime.now() - datetime.fromisoformat(cache.get("last_discovery", "2000-01-01"))).days < 7:
        return
    
    queries = [
        "best domain registrars 2025 reddit OR namepros OR lowendtalk",
        "best vps OR cloud providers 2025 lowendtalk OR reddit",
        "best privacy vpn 2025 reddit OR privacyguides",
        "best ai inference OR gpu providers 2025 reddit",
        "top saas referral credits 2025 indiehackers OR reddit"
    ]
    
    discovered = set()
    for query in queries:
        urls = search_with_apis(query)
        for url in urls[:3]:
            content = crawl_page(url)
            if not content:
                continue
            prompt = "Extract ONLY company/service names recommended in this page. Return ONLY a valid JSON array of strings. Example: [\"Porkbun\", \"Hetzner\"]"
            try:
                if GROQ_KEY:
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                                      headers={"Authorization": f"Bearer {GROQ_KEY}"},
                                      json={"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt + "\n\nContent:\n" + content[:20000]}],
                                            "temperature": 0.3}, timeout=20)
                    if r.status_code == 200:
                        names = json.loads(r.json()["choices"][0]["message"]["content"].strip("```json").strip("```").strip())
                        discovered.update(names)
            except:
                pass
    
    new_added = 0
    for name in discovered:
        name = name.strip()
        if name and len(name) > 2 and name.lower() not in [s.lower() for s in SERVICES]:
            services_ws.append_row([name])
            SERVICES.append(name)
            send_telegram(f"🆕 Nouvelle cible auto-découverte : {name}")
            new_added += 1
    
    if new_added > 0:
        send_telegram(f"Discovery terminée → {new_added} nouvelles cibles ajoutées !")
    
    cache["last_discovery"] = datetime.now().isoformat()
    save_cache(cache)

# ================== HUNT QUOTIDIEN AUTOMATIQUE ==================
def run_hunt():
    now = datetime.now()
    last_hunt = cache.get("last_hunt", "2000-01-01")
    if (now - datetime.fromisoformat(last_hunt)).total_seconds() < 86000:  # 24h
        return
    
    send_telegram("🔥 Chasse quotidienne automatique lancée...")
    discovery_new_services()
    
    new_deals = 0
    for service in SERVICES:
        query = f'"{service}" (promo code OR coupon OR discount OR credit OR deal) december 2025 OR january 2026 -expired'
        urls = search_with_apis(query)
        
        for url in urls[:6]:
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    msg = f"🔥 NEW DEAL → {service}\nCode: {code}\nLien: {url}"
                    send_telegram(msg)
                    deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Auto-search", url, now.strftime("%d/%m/%Y")])
                    new_deals += 1
            time.sleep(3)
        
        if service in KNOWN_SITES:
            url, _ = KNOWN_SITES[service]
            content = crawl_page(url)
            if content:
                codes = extract_codes(content, service)
                for code in codes:
                    msg = f"🔥 NEW DEAL (direct) → {service}\nCode: {code}\nLien: {url}"
                    send_telegram(msg)
                    deals_ws.append_row([now.strftime("%d/%m/%Y"), service, code, "Known site", url, now.strftime("%d/%m/%Y")])
                    new_deals += 1
        
        time.sleep(4)
    
    cache["last_hunt"] = now.isoformat()
    save_cache(cache)
    send_telegram(f"✅ Chasse quotidienne terminée → {new_deals} nouveaux deals trouvés et ajoutés dans la sheet !")

# ================== SCHEDULER (run quotidien + run immédiate au boot) ==================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_hunt, trigger="interval", hours=24, next_run_time=datetime.now() + timedelta(minutes=2))  # Première run dans 2 min au boot
scheduler.start()

# Run immédiat au boot (pour ne pas attendre 2 min)
threading.Thread(target=run_hunt).start()

@app.route("/")
def home():
    return "Tech Coupon Hunter V13 – Railway – Décembre 2025 – Always-on daily hunter", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
