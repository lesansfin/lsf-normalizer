import os
import hmac
import hashlib
import base64
import json
import re

from fastapi import FastAPI, Request, HTTPException
import httpx

app = FastAPI()

SHOPIFY_SECRET = os.environ.get("SHOPIFY_SECRET", "")
SHOPIFY_API_TOKEN = os.environ.get("SHOPIFY_API_TOKEN", "")
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # e.g. "yourstore.myshopify.com"


# ---------- UTILITIES ----------

def verify_shopify_hmac(request_body: bytes, hmac_header: str) -> bool:
    """Verify webhook came from Shopify."""
    digest = hmac.new(
        SHOPIFY_SECRET.encode("utf-8"),
        request_body,
        hashlib.sha256
    ).digest()
    calculated_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(calculated_hmac, hmac_header)


# ---- VERY SIMPLE PLACEHOLDER EXTRACTORS (you'll expand these) ----

def extract_designer(text: str) -> str:
    text_l = text.lower()

    # very tiny subset as example; you’ll paste in full map later
    DESIGNER_SYNONYMS = {
        "ysl": "Yves Saint Laurent",
        "yves saint laurent": "Yves Saint Laurent",
        "saint laurent": "Yves Saint Laurent",
        "christian dior": "Christian Dior",
        "dior": "Christian Dior",
        "prada": "Prada",
        "miu miu": "Miu Miu",
        "hermes": "Hermès",
        "hermès": "Hermès",
    }

    for syn, canonical in DESIGNER_SYNONYMS.items():
        if syn in text_l:
            return canonical

    return "unbranded"


CONDITION_MAP = {
    "new with tags": "PRISTINE",
    "nwt": "PRISTINE",
    "never worn": "PRISTINE",
    "like new": "PRISTINE",
    "mint condition": "PRISTINE",
    "deadstock": "PRISTINE",
    "excellent condition": "VERY GOOD",
    "gently used": "VERY GOOD",
    "gently worn": "VERY GOOD",
    "light wear": "VERY GOOD",
    "minor signs of wear": "VERY GOOD",
    "good used condition": "GOOD",
    "moderate wear": "GOOD",
    "normal vintage wear": "GOOD",
    "fair condition": "FAIR",
    "heavily used": "FAIR",
    "for restoration": "FAIR",
}


def extract_condition(text: str) -> str | None:
    t = text.lower()
    for phrase, bucket in CONDITION_MAP.items():
        if phrase in t:
            return bucket
    return None


COLORS = [
    "Black", "White", "Ivory", "Cream", "Beige", "Tan", "Brown", "Navy", "Blue",
    "Red", "Pink", "Green", "Yellow", "Orange", "Purple", "Grey", "Silver",
    "Gold", "Burgundy", "Maroon", "Camel", "Off-white", "Ecru", "Taupe"
    # (you'll swap this with your full list)
]


def extract_colors(text: str) -> list[str]:
    t = text.lower()
    found = []
    for c in COLORS:
        if c.lower() in t:
            found.append(c)
    # dedupe while preserving order
    return list(dict.fromkeys(found))


MEASUREMENT_PATTERN = re.compile(
    r"(bust|chest|p2p|pit to pit|underarm to underarm|armpit to armpit|waist|hips?|length|sleeve(?: length)?|rise|inseam)[^\d]{0,10}(\d+(\.\d+)?)\s*(cm|in|\"|inch|inches)?",
    re.IGNORECASE
)


MEASUREMENT_KEYS = {
    "bust": ["bust", "chest", "p2p", "pit to pit", "underarm to underarm", "armpit to armpit"],
    "waist": ["waist"],
    "hips": ["hips", "hip"],
    "length": ["length"],
    "sleeve_length": ["sleeve length", "sleeve"],
    "rise": ["rise"],
    "inseam": ["inseam"],
}


def normalize_measurement_label(label: str) -> str | None:
    l = label.lower()
    for canonical, synonyms in MEASUREMENT_KEYS.items():
        for s in synonyms:
            if s in l:
                return canonical
    return None


def extract_measurements(text: str) -> dict:
    result = {}
    for match in MEASUREMENT_PATTERN.finditer(text):
        label_raw = match.group(1)
        value = float(match.group(2))
        unit = match.group(4) or "in"
        key = normalize_measurement_label(label_raw)
        if not key:
            continue
        if unit.lower().startswith("cm"):
            value = round(value / 2.54, 2)
        result[key] = value
    return result


def extract_type(text: str) -> str | None:
    t = text.lower()

    TYPE_SYNONYMS = {
        "mini dress": "Mini dress",
        "midi dress": "Midi dress",
        "maxi dress": "Maxi dress",
        "dress": "Dress",
        "blazer": "Blazer",
        "jeans": "Jeans",
        "skirt": "Skirt",
        "trousers": "Trousers",
        "coat": "Coat",
        "jacket": "Jacket",
        "top": "Top",
    }

    for phrase in sorted(TYPE_SYNONYMS.keys(), key=len, reverse=True):
        if phrase in t:
            return TYPE_SYNONYMS[phrase]
    return None


def extract_era(text: str) -> str | None:
    t = text.lower()
    if any(x in t for x in ["1960s", "60s", "sixties", "mod era", "twiggy"]):
        return "1960s"
    if any(x in t for x in ["1970s", "70s", "seventies", "boho era", "disco era", "studio 54"]):
        return "1970s"
    if any(x in t for x in ["1980s", "80s", "eighties", "power dressing"]):
        return "1980s"
    if any(x in t for x in ["1990s", "90s", "nineties", "grunge", "minimalist era"]):
        return "1990s"
    if any(x in t for x in ["y2k", "2000s", "00s", "mcbling"]):
        return "2000s / Y2K"
    return None


def extract_materials(text: str) -> list[str]:
    t = text.lower()
    materials = [
        "cotton", "linen", "silk", "wool", "cashmere", "alpaca", "mohair", "polyester",
        "nylon", "viscose", "rayon", "denim", "leather", "suede", "velvet", "satin"
        # you’ll replace with your big material list
    ]
    found = []
    for m in materials:
        if m in t:
            found.append(m.capitalize())
    return list(dict.fromkeys(found))


def build_metafields_payload(product_id: int, text: str):
    designer = extract_designer(text)
    condition = extract_condition(text)
    colors = extract_colors(text)
    measurements = extract_measurements(text)
    ptype = extract_type(text)
    era = extract_era(text)
    materials = extract_materials(text)

    metafields = []

    def add_field(key, value, type_="single_line_text_field"):
        if value is None:
            return
        metafields.append({
            "namespace": "lsf",
            "key": key,
            "type": type_,
            "value": str(value)
        })

    add_field("designer", designer)
    add_field("condition", condition)
    if colors:
        add_field("primary_color", colors[0])
        if len(colors) > 1:
            add_field("secondary_color", colors[1])
    add_field("type", ptype)
    add_field("era_season", era)
    if materials:
        add_field("materials", ", ".join(materials))

    # measurements numeric
    for key, val in measurements.items():
        metafields.append({
            "namespace": "lsf",
            "key": f"measurements_{key}",
            "type": "number_decimal",
            "value": str(val)
        })

    return {"product_id": product_id, "metafields": metafields}


async def write_metafields_to_shopify(payload: dict):
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/metafields.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 300:
            print("Error from Shopify metafields:", resp.status_code, resp.text)


# ---------- ROUTES ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/products")
async def handle_product_webhook(request: Request):
    raw_body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256")
    if not hmac_header or not verify_shopify_hmac(raw_body, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    data = json.loads(raw_body.decode("utf-8"))

    product_id = data.get("id")
    title = data.get("title") or ""
    body_html = data.get("body_html") or ""

    # crude HTML strip for now
    body_text = re.sub(r"<[^>]+>", " ", body_html)
    text = f"{title}\n{body_text}"

    metafields_payload = build_metafields_payload(product_id, text)
    await write_metafields_to_shopify(metafields_payload)

    return {"status": "processed"}
