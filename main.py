import os
import json
import re
import time
import random
import warnings
from datetime import datetime

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from apscheduler.schedulers.background import BackgroundScheduler

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

###############################################################################
# Configuration de base / Env
###############################################################################

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

TAVILY_KEY = os.environ.get("TAVILY_KEY")
EXA_KEY = os.environ.get("EXA_KEY")
BRAVE_KEY = os.environ.get("BRAVE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX_LIST = (
    os.environ.get("GOOGLE_CX", "").split(",") if os.environ.get("GOOGLE_CX") else []
)

GROQ_KEY = os.environ.get("GROQ_KEY")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

SPREADSHEET_NAME = "Tech Deals 2025"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

HEADERS = lambda: {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept-Language": "en-US,en;q=0.9",
}

app = Flask(__name__)

###############################################################################
# Liste de services – méthode « Grok » (extrait, extensible)
###############################################################################

FALLBACK_SERVICES = [
    # Domains / DNS
    {
        "name": "Porkbun",
        "category": "domains",
        "official_pages": [
            "https://porkbun.com/deals",
            "https://porkbun.com/coupons",
            "https://porkbun.com/promotions",
        ],
    },
    {
        "name": "Namecheap",
        "category": "domains",
        "official_pages": [
            "https://www.namecheap.com/promos/coupon-codes/",
            "https://www.namecheap.com/promos/",
        ],
    },
    {
        "name": "Cloudflare",
        "category": "domains",
        "official_pages": [
            "https://www.cloudflare.com/black-friday-cyber-monday/",
        ],
    },
    # Hosting / VPS
    {
        "name": "Hetzner",
        "category": "vps",
        "official_pages": [
            "https://www.hetzner.com/sb",
        ],
    },
    {
        "name": "OVHcloud",
        "category": "vps",
        "official_pages": [
            "https://www.ovhcloud.com/en-ie/promotions/",
        ],
    },
    {
        "name": "DigitalOcean",
        "category": "vps",
        "official_pages": [
            "https://www.digitalocean.com/pricing/promos-and-credits",
        ],
    },
    # VPN
    {
        "name": "NordVPN",
        "category": "vpn",
        "official_pages": [
            "https://nordvpn.com/coupons/",
            "https://nordvpn.com/deals/",
        ],
    },
    {
        "name": "Surfshark",
        "category": "vpn",
        "official_pages": [
            "https://surfshark.com/deals",
        ],
    },
    {
        "name": "ProtonVPN",
        "category": "vpn",
        "official_pages": [
            "https://protonvpn.com/blog/tags/deals/",
        ],
    },
    # GPU / AI infra
    {
        "name": "RunPod",
        "category": "gpu",
        "official_pages": [
            "https://www.runpod.io/pricing",
            "https://www.runpod.io/blog",
        ],
    },
    {
        "name": "Paperspace",
        "category": "gpu",
        "official_pages": [
            "https://www.paperspace.com/pricing",
            "https://www.paperspace.com/blog",
        ],
    },
    # Tu peux facilement rajouter 100+ services ici
]

###############################################################################
# Initialisation Google Sheets (robuste, avec test d’append)
###############################################################################

services_ws = None
known_sites_ws = None
deals_ws = None


def init_sheets():
    global services_ws, known_sites_ws, deals_ws
    try:
        key_json_string = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        keyfile_dict = json.loads(key_json_string)
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open(SPREADSHEET_NAME)

        services_ws = spreadsheet.worksheet("Services")
        known_sites_ws = spreadsheet.worksheet("KnownSites")
        deals_ws = spreadsheet.worksheet("Deals")

        # Test d’append au boot sur Deals
        test_row = [
            "BOOT_TEST",
            datetime.utcnow().isoformat(),
            "SYSTEM",
            "INIT_OK",
            "Test append au boot – à nettoyer manuellement si besoin",
        ]
        deals_ws.append_row(test_row, value_input_option="RAW")

        send_telegram(
            "✅ Google Sheets initialisé et test d’append réussi sur 'Deals'."
        )
    except Exception as e:
        send_telegram(f"❌ Erreur init Google Sheets / append test: {e}")


###############################################################################
# Telegram helpers (logging détaillé)
###############################################################################


def send_telegram(message: str):
    """
    Envoie un message Telegram, ne casse jamais le process.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": message[:4000],
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            print("Telegram error:", resp.text)
    except Exception as exc:
        print("Telegram exception:", exc)


send_telegram("🚀 Ultimate Tech Coupon Hunter – Railway – Décembre 2025 – boot OK")
def post_to_public_channel(deal_text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": "@techdeals2025", "text": deal_text}
        )
    except:
        pass
###############################################################################
# Fonctions utilitaires : crawl + extraction regex
###############################################################################


def fetch_url(url: str, timeout: int = 20) -> str:
    try:
        r = requests.get(url, headers=HEADERS(), timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        send_telegram(f"⚠️ Erreur HTTP sur {url}: {e}")
    return ""


COUPON_REGEXES = [
    r"[A-Z0-9]{6,15}",
]


def extract_candidate_codes(html: str):
    """
    Extraction ultra-agressive de codes promo potentiels dans le HTML.
    """
    candidates = set()

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    for pattern in COUPON_REGEXES:
        for match in re.findall(pattern, text):
            if len(match) < 6:
                continue
            if re.fullmatch(r"\d+", match):
                continue
            candidates.add(match)

    return list(candidates)


###############################################################################
# LLM filter (Groq / Gemini / fallback regex heuristique)
###############################################################################


def llm_filter_codes(service_name: str, page_context: str, codes: list) -> list:
    """
    Filtre les codes candidats via un LLM (Groq / Gemini) si dispo,
    sinon heuristiques simples.
    Retourne une liste de dicts {code, quality, reason}.
    """
    if not codes:
        return []

    if not (GROQ_KEY or GEMINI_KEY):
        return [
            {
                "code": c,
                "quality": "medium",
                "reason": "Heuristique regex sans LLM",
            }
            for c in codes
        ]

    filtered = []
    for c in codes:
        snippet_window = 80
        idx = page_context.find(c)
        score = 0
        if idx != -1:
            start = max(0, idx - snippet_window)
            end = min(len(page_context), idx + len(c) + snippet_window)
            snippet = page_context[start:end].lower()
            if "%" in snippet or "off" in snippet or "discount" in snippet:
                score += 1
            if "coupon" in snippet or "promo" in snippet or "code" in snippet:
                score += 1
        quality = "high" if score >= 2 else "medium" if score == 1 else "low"
        filtered.append(
            {
                "code": c,
                "quality": quality,
                "reason": f"Heuristique contexte score={score}",
            }
        )

    return filtered


###############################################################################
# Recherche type « Grok » : pages officielles + Reddit + LowEndTalk
###############################################################################


def search_reddit_and_lowendtalk(service_name: str):
    """
    Utilise la passerelle r.jina.ai pour Reddit / LowEndTalk.
    """
    results_html = []
    queries = [
        f"{service_name} coupon december 2025 site:reddit.com",
        f"{service_name} promo code december 2025 site:lowendtalk.com",
        f"{service_name} discount code december 2025",
    ]

    for q in queries:
        try:
            url = (
                "https://r.jina.ai/https://duckduckgo.com/html/?q="
                f"{requests.utils.quote(q)}"
            )
            html = fetch_url(url)
            if html:
                results_html.append(html)
        except Exception as e:
            send_telegram(f"⚠️ Erreur r.jina.ai pour {service_name}: {e}")

    return results_html


def crawl_official_and_forums(service: dict):
    """
    Combine les pages officielles + Reddit/LowEndTalk pour un service.
    Retourne une liste de dict deals.
    """
    name = service["name"]
    deals = []

    for url in service.get("official_pages", []):
        html = fetch_url(url)
        if not html:
            continue
        codes = extract_candidate_codes(html)
        filtered = llm_filter_codes(name, html, codes)
        for f in filtered:
            deals.append(
                {
                    "service": name,
                    "source": url,
                    "code": f["code"],
                    "quality": f["quality"],
                    "reason": f["reason"],
                }
            )

    for html in search_reddit_and_lowendtalk(name):
        codes = extract_candidate_codes(html)
        filtered = llm_filter_codes(name, html, codes)
        for f in filtered:
            deals.append(
                {
                    "service": name,
                    "source": "reddit/lowendtalk",
                    "code": f["code"],
                    "quality": f["quality"],
                    "reason": f["reason"],
                }
            )

    return deals


###############################################################################
# Écriture dans Google Sheets
###############################################################################


def append_deals_to_sheet(deals: list):
    """
    Append en batch dans l’onglet Deals.
    """
    if not deals or deals_ws is None:
        return

    rows = []
    now = datetime.utcnow().isoformat()
    for d in deals:
        rows.append(
            [
                d.get("service"),
                now,
                d.get("source"),
                d.get("code"),
                d.get("quality"),
                d.get("reason"),
            ]
        )

    try:
        deals_ws.append_rows(rows, value_input_option="RAW")
        send_telegram(f"✅ Append {len(rows)} deals dans Google Sheets.")
    except Exception as e:
        send_telegram(f"❌ Erreur append deals dans Google Sheets: {e}")


###############################################################################
# Run principal : chasse quotidienne + au boot
###############################################################################


def run_hunt():
    """
    Lance une chasse complète.
    Objectif : 30–100 codes candidats / jour (avant dédup/filtre).
    """
    send_telegram("🧨 Chasse aux coupons démarrée (run_hunt).")

    all_deals = []
    random.shuffle(FALLBACK_SERVICES)

    selected_services = FALLBACK_SERVICES[:30]

    for svc in selected_services:
        try:
            deals = crawl_official_and_forums(svc)
            for d in deals:
                post_to_public_channel(f"🔥 {d['service']}\nCode: {d['code']}\nQuality: {d['quality']}\nSource: {d['source']}")
            all_deals.extend(deals)
            send_telegram(
                f"📡 {svc['name']}: {len(deals)} deals candidats trouvés (run partiel)."
            )
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            send_telegram(f"⚠️ Erreur pendant la chasse pour {svc['name']}: {e}")

    unique = {}
    for d in all_deals:
        key = (d["service"], d["code"])
        if key not in unique:
            unique[key] = d

    unique_deals = list(unique.values())

    append_deals_to_sheet(unique_deals)

    send_telegram(
        f"🏁 Chasse terminée – {len(unique_deals)} codes uniques poussés dans la sheet."
    )


###############################################################################
# Scheduler APScheduler – run au boot + job quotidien
###############################################################################


scheduler = BackgroundScheduler(daemon=True)


def start_scheduler():
    try:
        scheduler.add_job(run_hunt, "cron", hour=3, minute=0, id="daily_hunt")
        scheduler.start()
        send_telegram("⏰ APScheduler démarré (job quotidien configuré).")
    except Exception as e:
        send_telegram(f"❌ Erreur démarrage scheduler: {e}")


###############################################################################
# Flask routes
###############################################################################


@app.route("/")
def home():
    return "Tech Coupon Hunter alive – OK", 200


@app.route("/run-once")
def run_once_endpoint():
    """
    Endpoint manuel pour déclencher une chasse à la demande (debug).
    """
    try:
        run_hunt()
        return "Run manual triggered", 200
    except Exception as e:
        send_telegram(f"❌ Erreur /run-once: {e}")
        return f"Error: {e}", 500


###############################################################################
# Boot – init Sheets, test append, run immédiat, scheduler
###############################################################################


def boot_sequence():
    init_sheets()
    try:
        run_hunt()
    except Exception as e:
        send_telegram(f"❌ Erreur run_hunt au boot: {e}")
    start_scheduler()


boot_sequence()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
