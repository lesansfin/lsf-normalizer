import os
import hmac
import hashlib
import base64
import json
import re

from fastapi import FastAPI, Request, HTTPException
import httpx

app = FastAPI()

SHOPIFY_SECRET = os.environ.get("SHOPIFY_SECRET", "")  # Webhook signing secret (hex string from Webhooks UI)
SHOPIFY_API_TOKEN = os.environ.get("SHOPIFY_API_TOKEN", "")  # Admin API access token (shpat_...)
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")  # e.g. "hq1p0n-cm.myshopify.com"

# ---------- UTILITIES ----------

def verify_shopify_hmac(request_body: bytes, hmac_header: str) -> bool:
    """Verify webhook came from Shopify."""
    if not SHOPIFY_SECRET:
        # Fail closed if secret missing
        return False

    digest = hmac.new(
        SHOPIFY_SECRET.encode("utf-8"),
        request_body,
        hashlib.sha256,
    ).digest()
    calculated_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(calculated_hmac, hmac_header)


# ---- EXTRACTORS ----

def extract_designer(text: str) -> str:
    text_l = text.lower()

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
    "Black", "White", "Ivory", "Cream", "Beige", "Tan", "Brown",
    "Navy", "Blue", "Red", "Pink", "Green", "Yellow", "Orange",
    "Purple", "Grey", "Silver", "Gold", "Burgundy", "Maroon",
    "Camel", "Off-white", "Ecru", "Taupe",
]


def extract_colors(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    for c in COLORS:
        if c.lower() in t:
            found.append(c)
    # dedupe while preserving order
    return list(dict.fromkeys(found))


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

    # longest phrases first so "mini dress" wins over "dress"
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
        "nylon", "viscose", "rayon", "denim", "leather", "suede", "velvet", "satin",
    ]
    found: list[str] = []
    for m in materials:
        if m in t:
            found.append(m.capitalize())
    return list(dict.fromkeys(found))


def build_metafields_payload(product_id: int, text: str) -> dict:
    designer = extract_designer(text)
    condition = extract_condition(text)
    colors = extract_colors(text)
    ptype = extract_type(text)
    era = extract_era(text)
    materials = extract_materials(text)

    metafields: list[dict] = []

    def add_field(key: str, value, type_: str = "single_line_text_field"):
        if value is None:
            return
        metafields.append(
            {
                "namespace": "custom",
                "key": key,
                "type": type_,
                "value": str(value),
            }
        )

    # Match your metafield definitions
    add_field("designer", designer)
    add_field("condition_rating", condition)
    
    if colors:
        add_field("color", colors[0])
    
    add_field("product_type", ptype)
    add_field("season", era)
    
    if materials:
        add_field("material", ", ".join(materials))

    return {"product_id": product_id, "metafields": metafields}


async def write_metafields_to_shopify(product_id: int, metafields: list[dict]):
    """
    NOTE: Shopify's REST API creates product metafields at:
    POST /admin/api/2024-01/products/{product_id}/metafields.json
    one metafield at a time, not as a bulk list.
    """
    if not SHOPIFY_API_TOKEN or not SHOPIFY_STORE_DOMAIN:
        print("Shopify credentials missing; skipping metafield write.")
        return

    base_url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products/{product_id}/metafields.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for mf in metafields:
            payload = {"metafield": mf}
            resp = await client.post(base_url, headers=headers, json=payload)
            if resp.status_code >= 300:
                print("Error from Shopify metafields:", resp.status_code, resp.text)


# ---------- ROUTES ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/products")
async def handle_product_webhook(request: Request):
    # 1) Get raw body exactly as Shopify sent it
    raw_body = await request.body()

    # 2) Get HMAC header (FastAPI lowercases headers internally, but access is case-insensitive)
    hmac_header = request.headers.get("x-shopify-hmac-sha256")
    if not hmac_header or not verify_shopify_hmac(raw_body, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    # 3) Parse JSON safely
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    product_id = data.get("id")
    title = data.get("title") or ""
    body_html = data.get("body_html") or ""

    # crude HTML strip for now
    body_text = re.sub(r"<[^>]+>", " ", body_html)
    text = f"{title}\n{body_text}"

    metafields_payload = build_metafields_payload(product_id, text)

    # write metafields individually under the product
    await write_metafields_to_shopify(
        product_id=metafields_payload["product_id"],
        metafields=metafields_payload["metafields"],
    )

    return {"status": "processed"}
