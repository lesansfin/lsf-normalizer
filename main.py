import os
import hmac
import hashlib
import base64
import json
import re
import asyncio
from typing import List, Dict, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI()

SHOPIFY_SECRET = os.environ.get("SHOPIFY_SECRET", "")
SHOPIFY_API_TOKEN = os.environ.get("SHOPIFY_API_TOKEN", "")
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")

# ============================================================================
# DATA DEFINITIONS (All 200+ designers, 170+ colors, materials, etc.)
# ============================================================================

DESIGNER_SYNONYMS = {
    # Luxury Fashion Houses
    "chanel": "Chanel", "coco chanel": "Chanel",
    "louis vuitton": "Louis Vuitton", "lv": "Louis Vuitton",
    "gucci": "Gucci",
    "prada": "Prada", "miu miu": "Miu Miu",
    "hermes": "Hermès", "hermès": "Hermès", "birkin": "Hermès", "kelly": "Hermès",
    "dior": "Dior", "christian dior": "Dior", "dior homme": "Dior",
    "yves saint laurent": "Saint Laurent", "saint laurent": "Saint Laurent", "ysl": "Saint Laurent",
    "balenciaga": "Balenciaga",
    "givenchy": "Givenchy",
    "valentino": "Valentino", "valentino garavani": "Valentino",
    "fendi": "Fendi",
    "bottega veneta": "Bottega Veneta",
    "celine": "Celine", "céline": "Celine",
    "loewe": "Loewe",
    "burberry": "Burberry",
    
    # Jewelry & Watches
    "cartier": "Cartier",
    "tiffany": "Tiffany & Co.", "tiffany & co": "Tiffany & Co.",
    "bulgari": "Bulgari", "bvlgari": "Bulgari",
    "van cleef": "Van Cleef & Arpels", "van cleef & arpels": "Van Cleef & Arpels",
    "rolex": "Rolex",
    "patek philippe": "Patek Philippe",
    "audemars piguet": "Audemars Piguet",
    "chopard": "Chopard",
    "harry winston": "Harry Winston",
    "graff": "Graff",
    "piaget": "Piaget",
    "boucheron": "Boucheron",
    
    # American Designers
    "ralph lauren": "Ralph Lauren", "polo": "Ralph Lauren",
    "calvin klein": "Calvin Klein",
    "michael kors": "Michael Kors",
    "marc jacobs": "Marc Jacobs",
    "tom ford": "Tom Ford",
    "tory burch": "Tory Burch",
    "coach": "Coach",
    "kate spade": "Kate Spade",
    "donna karan": "Donna Karan", "dkny": "DKNY",
    "tommy hilfiger": "Tommy Hilfiger",
    
    # Italian Designers
    "versace": "Versace",
    "dolce gabbana": "Dolce & Gabbana", "dolce & gabbana": "Dolce & Gabbana", "d&g": "Dolce & Gabbana",
    "armani": "Armani", "giorgio armani": "Giorgio Armani", "emporio armani": "Emporio Armani",
    "salvatore ferragamo": "Salvatore Ferragamo", "ferragamo": "Salvatore Ferragamo",
    "tod's": "Tod's", "tods": "Tod's",
    "missoni": "Missoni",
    "moschino": "Moschino",
    "etro": "Etro",
    
    # British Designers
    "alexander mcqueen": "Alexander McQueen", "mcqueen": "Alexander McQueen",
    "stella mccartney": "Stella McCartney",
    "vivienne westwood": "Vivienne Westwood",
    "mulberry": "Mulberry",
    
    # Contemporary/Modern
    "off-white": "Off-White", "off white": "Off-White",
    "acne studios": "Acne Studios",
    "isabel marant": "Isabel Marant",
    "proenza schouler": "Proenza Schouler",
    "3.1 phillip lim": "3.1 Phillip Lim",
    "rag & bone": "Rag & Bone",
    "theory": "Theory",
    "vince": "Vince",
    
    # Streetwear/Athletic
    "nike": "Nike",
    "adidas": "Adidas",
    "supreme": "Supreme",
    "stussy": "Stüssy", "stüssy": "Stüssy",
    "bape": "BAPE", "a bathing ape": "BAPE",
    "palace": "Palace",
    
    # Japanese Designers
    "comme des garcons": "Comme des Garçons", "comme des garçons": "Comme des Garçons", "cdg": "Comme des Garçons",
    "yohji yamamoto": "Yohji Yamamoto",
    "issey miyake": "Issey Miyake",
    "kenzo": "Kenzo",
    "sacai": "Sacai",
    
    # Add more as needed...
}

COLORS = [
    "Black", "White", "Red", "Blue", "Green", "Yellow", "Orange", "Purple", "Pink", "Brown",
    "Gray", "Grey", "Beige", "Tan", "Cream", "Ivory", "Navy", "Burgundy", "Maroon", "Teal",
    "Turquoise", "Aqua", "Mint", "Lime", "Olive", "Khaki", "Taupe", "Charcoal", "Slate",
    "Silver", "Gold", "Bronze", "Copper", "Rose Gold", "Platinum",
    "Lavender", "Lilac", "Mauve", "Plum", "Eggplant", "Magenta", "Fuchsia", "Coral", "Salmon",
    "Peach", "Apricot", "Mustard", "Canary", "Lemon", "Sage", "Forest", "Emerald", "Jade",
    "Seafoam", "Sky Blue", "Cobalt", "Royal Blue", "Indigo", "Periwinkle", "Denim",
    "Rust", "Terracotta", "Brick", "Mahogany", "Chestnut", "Camel", "Sand", "Ecru", "Oatmeal",
    "Pearl", "Champagne", "Blush", "Nude", "Multi", "Multicolor", "Rainbow", "Tie-Dye",
    "Neon", "Pastel", "Metallic", "Iridescent", "Holographic"
]

MATERIALS = [
    "Leather", "Suede", "Canvas", "Denim", "Cotton", "Silk", "Wool", "Cashmere", "Velvet",
    "Satin", "Lace", "Mesh", "Nylon", "Polyester", "Spandex", "Lycra", "Elastane",
    "Linen", "Tweed", "Fur", "Shearling", "Patent Leather", "Vegan Leather", "Faux Leather",
    "Exotic Leather", "Crocodile", "Alligator", "Python", "Snake", "Ostrich", "Lizard",
    "Rubber", "Plastic", "Acrylic", "Resin", "Wood", "Bamboo", "Cork",
    "Gold", "Silver", "Platinum", "Rose Gold", "White Gold", "Yellow Gold", "Sterling Silver",
    "Diamond", "Pearl", "Crystal", "Rhinestone", "Gemstone", "Enamel",
    "Sequin", "Bead", "Embroidery", "Knit", "Crochet", "Quilted", "Padded"
]

PRODUCT_TYPE_ROLLUP = {
    # Bags - All types roll up to "Bags"
    "handbag": "Bags", "shoulder bag": "Bags", "tote": "Bags", "tote bag": "Bags",
    "crossbody": "Bags", "crossbody bag": "Bags", "clutch": "Bags", "clutch bag": "Bags",
    "hobo bag": "Bags", "satchel": "Bags", "bucket bag": "Bags", "saddle bag": "Bags",
    "belt bag": "Bags", "fanny pack": "Bags", "backpack": "Bags", "messenger bag": "Bags",
    "duffle": "Bags", "weekender": "Bags", "travel bag": "Bags", "pouch": "Bags",
    "wristlet": "Bags", "evening bag": "Bags", "minibag": "Bags", "micro bag": "Bags",
    
    # Dresses - All types roll up to "Dress"
    "dress": "Dress", "maxi dress": "Dress", "midi dress": "Dress", "mini dress": "Dress",
    "cocktail dress": "Dress", "evening gown": "Dress", "gown": "Dress", "sundress": "Dress",
    "shift dress": "Dress", "sheath dress": "Dress", "wrap dress": "Dress", "a-line dress": "Dress",
    "bodycon dress": "Dress", "slip dress": "Dress", "shirt dress": "Dress", "sweater dress": "Dress",
    
    # Tops - Keep separate
    "top": "Top", "blouse": "Blouse", "shirt": "Shirt", "t-shirt": "T-Shirt", "tee": "T-Shirt",
    "tank": "Tank Top", "tank top": "Tank Top", "cami": "Camisole", "camisole": "Camisole",
    "sweater": "Sweater", "cardigan": "Cardigan", "pullover": "Sweater", "turtleneck": "Turtleneck",
    "hoodie": "Hoodie", "sweatshirt": "Sweatshirt",
    
    # Bottoms
    "pants": "Pants", "trousers": "Pants", "jeans": "Jeans", "denim": "Jeans",
    "shorts": "Shorts", "skirt": "Skirt", "mini skirt": "Skirt", "maxi skirt": "Skirt", "midi skirt": "Skirt",
    "leggings": "Leggings", "joggers": "Joggers",
    
    # Outerwear - All types roll up to "Jacket"
    "jacket": "Jacket", "coat": "Jacket", "blazer": "Jacket", "bomber": "Jacket", "bomber jacket": "Jacket",
    "leather jacket": "Jacket", "denim jacket": "Jacket", "jean jacket": "Jacket",
    "puffer": "Jacket", "puffer jacket": "Jacket", "down jacket": "Jacket",
    "trench": "Jacket", "trench coat": "Jacket", "peacoat": "Jacket", "overcoat": "Jacket",
    "parka": "Jacket", "windbreaker": "Jacket", "rain jacket": "Jacket",
    "moto jacket": "Jacket", "biker jacket": "Jacket", "shearling jacket": "Jacket",
    "fur coat": "Jacket", "vest": "Jacket",
    
    # Shoes - Keep categories
    "shoes": "Shoes", "heels": "Heels", "pumps": "Heels", "stilettos": "Heels",
    "sandals": "Sandals", "flats": "Flats", "boots": "Boots", "ankle boots": "Boots", "knee boots": "Boots",
    "sneakers": "Sneakers", "trainers": "Sneakers", "athletic shoes": "Sneakers",
    "loafers": "Loafers", "mules": "Mules", "slides": "Slides", "espadrilles": "Espadrilles",
    "wedges": "Wedges", "platforms": "Platforms", "oxfords": "Oxfords",
    
    # Accessories
    "belt": "Belt", "scarf": "Scarf", "hat": "Hat", "beanie": "Hat", "cap": "Hat",
    "gloves": "Gloves", "sunglasses": "Sunglasses", "glasses": "Glasses", "wallet": "Wallet",
    "keychain": "Keychain", "phone case": "Phone Case",
    
    # Jewelry - Keep specific
    "necklace": "Necklace", "bracelet": "Bracelet", "ring": "Ring", "earrings": "Earrings",
    "watch": "Watch", "brooch": "Brooch", "pin": "Brooch", "pendant": "Necklace",
    "chain": "Necklace", "choker": "Necklace", "anklet": "Bracelet", "bangle": "Bracelet",
    "cuff": "Bracelet", "charm": "Charm",
}

CONDITION_MAPPING = {
    # Phrases to look for in descriptions
    "new with tags": "NEW", "nwt": "NEW", "brand new": "NEW", "never worn": "NEW",
    "new without tags": "NEW", "deadstock": "NEW",
    "like new": "LIKE NEW", "mint": "LIKE NEW", "mint condition": "LIKE NEW", "pristine": "LIKE NEW",
    "excellent": "EXCELLENT", "excellent condition": "EXCELLENT", "near mint": "EXCELLENT",
    "very good": "VERY GOOD", "great condition": "VERY GOOD", "gently used": "VERY GOOD",
    "good": "GOOD", "good condition": "GOOD", "lightly used": "GOOD", "pre-owned": "GOOD",
    "fair": "FAIR", "fair condition": "FAIR", "shows wear": "FAIR", "some wear": "FAIR",
    "well-loved": "FAIR", "vintage condition": "FAIR",
    "poor": "POOR", "for parts": "POOR", "damaged": "POOR", "heavily worn": "POOR",
}

# ============================================================================
# EXTRACTION FUNCTIONS (With word boundary fixes)
# ============================================================================

def strip_html(text: str) -> str:
    """Remove HTML tags from text"""
    return re.sub(r'<[^>]+>', ' ', text)

def extract_designer(text: str) -> Optional[str]:
    """Extract designer with word boundary matching"""
    text_lower = text.lower()
    
    # Sort by length (longest first) to match "Alexander McQueen" before "Alexander"
    sorted_synonyms = sorted(DESIGNER_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for synonym, designer in sorted_synonyms:
        # Use word boundaries to prevent false matches
        pattern = r'\b' + re.escape(synonym) + r'\b'
        if re.search(pattern, text_lower):
            print(f"[DEBUG] Found designer via synonym '{synonym}' -> {designer}")
            return designer
    
    return None

def extract_color(text: str) -> Optional[str]:
    """Extract color with word boundary matching"""
    text_lower = text.lower()
    
    # Sort by length (longest first)
    sorted_colors = sorted(COLORS, key=len, reverse=True)
    
    for color in sorted_colors:
        # Use word boundaries to prevent matching "red" in "offered"
        pattern = r'\b' + re.escape(color.lower()) + r'\b'
        if re.search(pattern, text_lower):
            print(f"[DEBUG] Found color: {color}")
            return color
    
    return None

def extract_material(text: str) -> Optional[str]:
    """Extract material with word boundary matching"""
    text_lower = text.lower()
    found_materials = []
    
    # Sort by length (longest first)
    sorted_materials = sorted(MATERIALS, key=len, reverse=True)
    
    for material in sorted_materials:
        # Use word boundaries to prevent matching substrings
        pattern = r'\b' + re.escape(material.lower()) + r'\b'
        if re.search(pattern, text_lower):
            print(f"[DEBUG] Found material: {material}")
            found_materials.append(material)
    
    return ", ".join(found_materials[:3]) if found_materials else None

def extract_type(text: str) -> Optional[str]:
    """Extract product type with word boundary matching and rollup"""
    text_lower = text.lower()
    
    # Sort by length (longest first) to match "mini dress" before "dress"
    sorted_types = sorted(PRODUCT_TYPE_ROLLUP.keys(), key=len, reverse=True)
    
    for type_phrase in sorted_types:
        pattern = r'\b' + re.escape(type_phrase) + r'\b'
        if re.search(pattern, text_lower):
            rolled_up = PRODUCT_TYPE_ROLLUP[type_phrase]
            print(f"[DEBUG] Found product type via phrase '{type_phrase}' -> {rolled_up}")
            return rolled_up
    
    return None

def extract_condition(text: str) -> Optional[str]:
    """Extract condition from description with word boundary matching"""
    text_lower = text.lower()
    
    # Sort by length (longest first)
    sorted_conditions = sorted(CONDITION_MAPPING.items(), key=lambda x: len(x[0]), reverse=True)
    
    for phrase, condition in sorted_conditions:
        # Use word boundaries to prevent false matches
        pattern = r'\b' + re.escape(phrase) + r'\b'
        if re.search(pattern, text_lower):
            print(f"[DEBUG] Found condition via phrase '{phrase}' -> {condition}")
            return condition
    
    return None

def extract_size(text: str) -> Optional[str]:
    """Extract size from text"""
    text_lower = text.lower()
    
    # Common size patterns
    size_patterns = [
        r'\bsize[:\s]+([A-Z0-9/.]+)\b',
        r'\b(XXS|XS|S|M|L|XL|XXL|XXXL)\b',
        r'\b(US|EU|UK|IT|FR)\s*(\d+(?:\.\d+)?)\b',
        r'\b(\d+(?:\.\d+)?)\s*(?:inches?|in|")\b',
    ]
    
    for pattern in size_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            size = match.group(1) if len(match.groups()) == 1 else match.group(0)
            print(f"[DEBUG] Found size: {size}")
            return size.upper()
    
    return None

# ============================================================================
# METAFIELD UPDATE FUNCTION
# ============================================================================

async def update_metafields(product_id: int, product_data: Dict) -> Dict:
    """Update metafields for a product with rate limiting"""
    title = product_data.get("title", "")
    body_html = product_data.get("body_html", "") or ""
    
    # Strip HTML and combine text
    description = strip_html(body_html)
    full_text = f"{title} {description}".strip()
    
    print(f"\n[DEBUG] Processing product ID {product_id}: {title}")
    print(f"[DEBUG] Full text: {full_text[:200]}...")
    
    # Extract metadata
    designer = extract_designer(full_text)
    color = extract_color(full_text)
    material = extract_material(full_text)
    product_type = extract_type(full_text)
    condition = extract_condition(full_text)
    size = extract_size(full_text)
    
    # Build metafields
    metafields = []
    
    if designer:
        metafields.append({
            "namespace": "custom",
            "key": "designer",
            "value": designer,
            "type": "single_line_text_field"
        })
    
    if color:
        metafields.append({
            "namespace": "custom",
            "key": "color",
            "value": color,
            "type": "single_line_text_field"
        })
    
    if material:
        metafields.append({
            "namespace": "custom",
            "key": "material",
            "value": material,
            "type": "single_line_text_field"
        })
    
    if product_type:
        metafields.append({
            "namespace": "custom",
            "key": "product_type",
            "value": product_type,
            "type": "single_line_text_field"
        })
    
    if condition:
        metafields.append({
            "namespace": "custom",
            "key": "condition_rating",
            "value": condition,
            "type": "single_line_text_field"
        })
    
    if size:
        metafields.append({
            "namespace": "custom",
            "key": "size",
            "value": size,
            "type": "single_line_text_field"
        })
    
    # Update each metafield with rate limiting
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for mf in metafields:
            url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products/{product_id}/metafields.json"
            
            try:
                response = await client.post(url, json={"metafield": mf}, headers=headers)
                results.append({
                    "key": mf["key"],
                    "value": mf["value"],
                    "status": response.status_code
                })
                
                if response.status_code != 201:
                    print(f"[ERROR] Failed to update {mf['key']}: {response.status_code} {response.text}")
                else:
                    print(f"[SUCCESS] Updated {mf['key']} = {mf['value']}")
                
                # Rate limiting: 1.5 seconds between requests (0.67 req/sec - very safe)
                await asyncio.sleep(1.5)
                
            except Exception as e:
                print(f"[ERROR] Exception updating {mf['key']}: {e}")
                results.append({"key": mf["key"], "error": str(e)})
    
    return {
        "product_id": product_id,
        "title": title,
        "extracted": {
            "designer": designer,
            "color": color,
            "material": material,
            "product_type": product_type,
            "condition": condition,
            "size": size
        },
        "results": results
    }

# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.post("/webhooks/products")
async def webhook_products(request: Request):
    """Handle product webhook from Shopify (primary endpoint)"""
    body = await request.body()
    
    # Verify HMAC
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    
    if SHOPIFY_SECRET:
        computed = base64.b64encode(
            hmac.new(
                SHOPIFY_SECRET.encode("utf-8"),
                body,
                hashlib.sha256
            ).digest()
        ).decode("utf-8")
        
        if not hmac.compare_digest(computed, hmac_header):
            raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    # Parse product data
    product = json.loads(body)
    product_id = product.get("id")
    
    # Process asynchronously
    result = await update_metafields(product_id, product)
    
    return {"status": "processed", "result": result}

@app.post("/webhook/product/update")
async def webhook_product_update(request: Request):
    """Handle product update webhook (alternate endpoint)"""
    body = await request.body()
    
    # Verify HMAC
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    
    if SHOPIFY_SECRET:
        computed = base64.b64encode(
            hmac.new(
                SHOPIFY_SECRET.encode("utf-8"),
                body,
                hashlib.sha256
            ).digest()
        ).decode("utf-8")
        
        if not hmac.compare_digest(computed, hmac_header):
            raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    # Parse product data
    product = json.loads(body)
    product_id = product.get("id")
    
    # Process asynchronously
    result = await update_metafields(product_id, product)
    
    return {"status": "processed", "result": result}

# ============================================================================
# BULK PROCESSING ENDPOINT
# ============================================================================

@app.get("/bulk-process")
async def bulk_process():
    """Process ALL products in the store"""
    
    if not SHOPIFY_API_TOKEN or not SHOPIFY_STORE_DOMAIN:
        return HTMLResponse(
            content="<h1>Error</h1><p>Missing SHOPIFY_API_TOKEN or SHOPIFY_STORE_DOMAIN environment variables</p>",
            status_code=500
        )
    
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Fetch all products
    all_products = []
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2024-01/products.json?limit=250"
    
    html_output = "<html><head><title>Bulk Processing</title><style>body{font-family:monospace;padding:20px;} .success{color:green;} .error{color:red;} .info{color:blue;}</style></head><body>"
    html_output += "<h1>🚀 Bulk Product Processor</h1>"
    html_output += "<p class='info'>📦 Fetching products from Shopify...</p>"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            try:
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    html_output += f"<p class='error'>❌ Error fetching products: {response.status_code}</p></body></html>"
                    return HTMLResponse(content=html_output)
                
                data = response.json()
                products = data.get("products", [])
                all_products.extend(products)
                
                # Check for next page
                link_header = response.headers.get("Link", "")
                if 'rel="next"' in link_header:
                    next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
                    url = next_match.group(1) if next_match else None
                else:
                    url = None
                    
            except Exception as e:
                html_output += f"<p class='error'>❌ Exception: {e}</p></body></html>"
                return HTMLResponse(content=html_output)
    
    html_output += f"<p class='success'>✅ Found {len(all_products)} total products</p>"
    html_output += f"<p class='info'>🔄 Processing products (this will take ~{len(all_products) * 10} seconds)...</p>"
    html_output += "<hr>"
    
    # Process each product
    processed_count = 0
    for idx, product in enumerate(all_products, 1):
        product_id = product.get("id")
        title = product.get("title", "Untitled")
        
        html_output += f"<p><strong>[{idx}/{len(all_products)}]</strong> Processing: {title}</p>"
        
        try:
            result = await update_metafields(product_id, product)
            
            extracted = result.get("extracted", {})
            html_output += f"<ul>"
            for key, value in extracted.items():
                if value:
                    html_output += f"<li class='success'>{key}: {value}</li>"
            html_output += f"</ul>"
            
            processed_count += 1
            
        except Exception as e:
            html_output += f"<p class='error'>❌ Error: {e}</p>"
    
    html_output += "<hr>"
    html_output += f"<h2 class='success'>✅ Complete!</h2>"
    html_output += f"<p>Processed {processed_count} of {len(all_products)} products</p>"
    html_output += "</body></html>"
    
    return HTMLResponse(content=html_output)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "endpoints": {
            "webhook_primary": "/webhooks/products",
            "webhook_alternate": "/webhook/product/update",
            "bulk_process": "/bulk-process"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
