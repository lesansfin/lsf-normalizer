# bulk_processor.py - Deploy this to Render as a Web Service

import os
import asyncio
import httpx
import re
import json
from typing import List, Dict
from fastapi import FastAPI

app = FastAPI()

# Environment variables (set in Render dashboard)
SHOPIFY_API_TOKEN = os.environ.get("SHOPIFY_API_TOKEN", "")
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")

# Copy all your extraction data from the webhook here...
DESIGNERS = [
    "Yves Saint Laurent", "Christian Dior", "Cartier", "Louis Vuitton", "Bottega Veneta",
    # ... add all 200+ designers from your webhook
]

DESIGNER_SYNONYMS = {
    "cartier": "Cartier",
    "lv": "Louis Vuitton",
    # ... add all synonyms from your webhook
}

CONDITION_MAP = {
    "very good pre-owned condition": "VERY GOOD",
    # ... add all conditions from your webhook
}

COLORS = ["Black", "White", "Platinum", "Gold", "Eggplant"]  # Add all 170+ colors
PRODUCT_TYPES = {"ring": "Ring", "diamond ring": "Ring"}  # Add all types
MATERIALS = ["Platinum", "Gold", "Diamond", "Leather"]  # Add all materials

def extract_designer(text: str) -> str:
    text_l = text.lower()
    for syn, canonical in DESIGNER_SYNONYMS.items():
        if syn in text_l:
            return canonical
    for designer in sorted(DESIGNERS, key=len, reverse=True):
        if designer.lower() in text_l:
            return designer
    return "unbranded"

def extract_condition(text: str) -> str | None:
    t = text.lower()
    for phrase in sorted(CONDITION_MAP.keys(), key=len, reverse=True):
        if phrase in t:
            return CONDITION_MAP[phrase]
    return None

def extract_colors(text: str) -> list[str]:
    t = text.lower()
    found = []
    for c in sorted(COLORS, key=len, reverse=True):
        if c.lower() in t:
            found.append(c)
    return list(dict.fromkeys(found))

def extract_type(text: str) -> str | None:
    t = text.lower()
    for phrase in sorted(PRODUCT_TYPES.keys(), key=len, reverse=True):
        escaped_phrase = re.escape(phrase)
        if ' ' in phrase:
            pattern = r'\b' + escaped_phrase.replace(r'\ ', r'\s+') + r'\b'
        else:
            pattern = r'\b' + escaped_phrase + r'\b'
        if re.search(pattern, t):
            return PRODUCT_TYPES[phrase]
    return None

def extract_materials(text: str) -> list[str]:
    t = text.lower()
    found = []
    for m in sorted(MATERIALS, key=len, reverse=True):
        if m.lower() in t:
            found.append(m)
    return list(dict.fromkeys(found))

async def fetch_all_products() -> List[Dict]:
    """Fetch all products from Shopify."""
    products = []
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2025-10/products.json?limit=250"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                break
            
            data = resp.json()
            batch = data.get("products", [])
            products.extend(batch)
            
            # Check for next page
            link_header = resp.headers.get("Link", "")
            if 'rel="next"' in link_header:
                next_link = [l.strip() for l in link_header.split(",") if 'rel="next"' in l]
                if next_link:
                    url = next_link[0].split(";")[0].strip("<>")
                else:
                    url = None
            else:
                url = None
            
            await asyncio.sleep(0.5)
    
    return products

async def process_product(product: Dict, client: httpx.AsyncClient):
    """Process a single product."""
    product_id = product.get("id")
    title = product.get("title", "")
    body_html = product.get("body_html", "")
    
    body_text = re.sub(r"<[^>]+>", " ", body_html or "")
    text = f"{title}\n{body_text}"
    
    # Extract metadata
    designer = extract_designer(text)
    condition = extract_condition(text)
    colors = extract_colors(text)
    ptype = extract_type(text)
    materials = extract_materials(text)
    
    # Build metafields
    metafields = []
    
    def add_field(key: str, value):
        if value is None:
            return
        metafields.append({
            "namespace": "custom",
            "key": key,
            "type": "single_line_text_field",
            "value": str(value),
        })
    
    add_field("designer", designer)
    add_field("condition_rating", condition)
    if colors:
        add_field("color", colors[0])
    add_field("product_type", ptype)
    if materials:
        add_field("material", ", ".join(materials))
    
    # Write metafields
    base_url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2025-10/products/{product_id}/metafields.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json",
    }
    
    success_count = 0
    for mf in metafields:
        payload = {"metafield": mf}
        resp = await client.post(base_url, headers=headers, json=payload)
        
        if resp.status_code < 300:
            success_count += 1
        
        await asyncio.sleep(2.0)  # Extra safe rate limiting
    
    return {
        "product": title,
        "success_count": success_count,
        "total_fields": len(metafields)
    }

@app.get("/")
async def root():
    return {"message": "Bulk processor ready. Visit /process to start processing."}

@app.get("/process")
async def process_all_products():
    """Endpoint to trigger bulk processing."""
    print("🚀 Starting bulk processing...")
    
    # Fetch products
    products = await fetch_all_products()
    print(f"📦 Found {len(products)} products")
    
    if not products:
        return {"error": "No products found"}
    
    # Process all products
    results = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, product in enumerate(products, 1):
            print(f"🔄 Processing {i}/{len(products)}: {product.get('title', '')}")
            result = await process_product(product, client)
            results.append(result)
    
    print("✅ Processing complete!")
    
    return {
        "status": "complete",
        "total_products": len(products),
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
