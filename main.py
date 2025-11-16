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

# Comprehensive designer list
DESIGNERS = [
    "Yves Saint Laurent", "Christian Dior", "Cristóbal Balenciaga", "Pierre Cardin",
    "André Courrèges", "Hubert de Givenchy", "Emanuel Ungaro", "Balmain", "Lanvin",
    "Mary Quant", "Ossie Clark", "Biba", "Barbara Hulanicki", "Rudi Gernreich",
    "Paco Rabanne", "Bonnie Cashin", "Geoffrey Beene", "Bill Blass", "Norman Norell",
    "Anne Klein", "Pauline Trigère", "Halston", "Donald Brooks", "Diane von Fürstenberg",
    "Calvin Klein", "Ralph Lauren", "Perry Ellis", "Stephen Burrows", "Karl Lagerfeld",
    "Missoni", "Jean Muir", "Sonia Rykiel", "Kenzo Takada", "Issey Miyake",
    "Kansai Yamamoto", "Zandra Rhodes", "Thierry Mugler", "Azzedine Alaïa", "Gucci",
    "Hermès", "Céline", "Christian Lacroix", "Valentino", "Gianfranco Ferré",
    "Versace", "Donatella Versace", "Armani", "Moschino", "Claude Montana",
    "Jean Paul Gaultier", "Yohji Yamamoto", "Helmut Lang", "Jil Sander", "Miuccia Prada",
    "Prada", "Miu Miu", "Narciso Rodriguez", "Ann Demeulemeester", "Jean Colonna",
    "Tom Ford", "John Galliano", "Alexander McQueen", "Hussein Chalayan", "Martin Margiela",
    "Romeo Gigli", "Marc Jacobs", "Kate Spade", "Anna Sui", "Isaac Mizrahi",
    "Todd Oldham", "Betsey Johnson", "Vivienne Westwood", "Katharine Hamnett",
    "Nicolas Ghesquière", "Phoebe Philo", "Stefano Pilati", "Alber Elbaz",
    "Riccardo Tisci", "Stella McCartney", "Proenza Schouler", "Zac Posen",
    "Jason Wu", "Phillip Lim", "Rodarte", "Tory Burch", "Derek Lam", "Vera Wang",
    "Isabel Marant", "Junya Watanabe", "Roberto Cavalli", "Etro", "Raf Simons",
    "Hedi Slimane", "Alessandro Michele", "Sarah Burton", "Maria Grazia Chiuri",
    "Demna", "Jonathan Anderson", "Clare Waight Keller", "Virginie Viard",
    "Simone Rocha", "Cecilie Bahnsen", "The Row", "Christopher Kane", "Jacquemus",
    "Rosie Assoulin", "Ulla Johnson", "Mother of Pearl", "Ganni", "Sies Marjan",
    "Virgil Abloh", "Yoon Ahn", "Marine Serre", "Heron Preston", "Shayne Oliver",
    "Peter Do", "Khaite", "Catherine Holstein", "Tove", "Bode", "Emily Adams Bode",
    "Wales Bonner", "Lemaire", "Nensi Dojaka", "Area", "LaQuan Smith",
    "Christopher John Rogers", "KNWLS", "Dilara Fındıkoğlu", "Mugler",
    "Casey Cadwallader", "Schiaparelli", "Daniel Roseberry", "Jcrew", "Donna Karan",
    "Escada", "Burberry", "Chloé", "Max Mara", "Theory",
    # Foundational / Couture (30s–70s)
    "Madeleine Vionnet", "Elsa Schiaparelli", "Jean Patou", "Jeanne Lanvin",
    "Nina Ricci", "Carven", "Madame Grès", "Paul Poiret", "Mainbocher",
    "Jacques Fath", "Guy Laroche", "Courrèges",
    # American Sportswear Legends
    "Liz Claiborne", "Anne Fogarty", "Lilli Ann", "Adrienne Vittadini",
    "Stephen Sprouse", "Giorgio di Sant'Angelo", "Janice Wainwright",
    # Italian 70s–90s Powerhouses
    "Fendi", "Trussardi", "Krizia", "Sportmax", "Genny", "Gianni Versace",
    "Fiorucci", "Miss Deanna", "Blumarine", "Brioni", "Laura Biagiotti",
    "Emilio Pucci",
    # Japanese Avant-Garde
    "Matsuda", "Comme des Garçons", "Tsumori Chisato",
    # Antwerp / European 80s–90s Designers
    "Dries Van Noten", "Dirk Bikkembergs", "Walter Van Beirendonck",
    "Patrick Van Ommeslaeghe",
    # London Designers (70s–90s)
    "Hardy Amies", "Bruce Oldfield", "Jasper Conran", "Bella Freud",
    "Matthew Williamson", "Ozwald Boateng", "John Richmond",
    # Indie / Cult Vintage Labels
    "Margaret Howell", "A.P.C.", "Acne Studios", "Rick Owens",
    "Jean-Charles de Castelbajac",
    # Accessories & Leather Houses
    "Delvaux", "Loewe", "Mulberry", "Coach", "Bally", "Ferragamo",
    "Cartier", "Tiffany", "Tiffany & Co", "Louis Vuitton", "Bottega Veneta",
    # Scandi & Minimalist
    "Filippa K", "Tiger of Sweden", "Weekday",
    # Y2K / 2000s Designers
    "BCBG Max Azria", "Baby Phat", "Heatherette", "Anna Molinari", "DSquared2",
    "Morgan de Toi",
]

# Common abbreviations and alternatives
DESIGNER_SYNONYMS = {
    "ysl": "Yves Saint Laurent",
    "saint laurent": "Yves Saint Laurent",
    "dior": "Christian Dior",
    "christian dior": "Christian Dior",
    "balenciaga": "Cristóbal Balenciaga",
    "cristobal balenciaga": "Cristóbal Balenciaga",
    "givenchy": "Hubert de Givenchy",
    "hermes": "Hermès",
    "celine": "Céline",
    "céline": "Céline",
    "gucci": "Gucci",
    "fendi": "Fendi",
    "jcrew": "Jcrew",
    "j crew": "Jcrew",
    # Sub-brands and diffusion lines
    "escada couture": "Escada",
    "escada sport": "Escada",
    "escada margaretha ley": "Escada",
    "armani exchange": "Armani",
    "emporio armani": "Armani",
    "giorgio armani": "Armani",
    "armani collezioni": "Armani",
    "polo ralph lauren": "Ralph Lauren",
    "ralph lauren collection": "Ralph Lauren",
    "lauren ralph lauren": "Ralph Lauren",
    "polo sport": "Ralph Lauren",
    "dkny": "Donna Karan",
    "donna karan new york": "Donna Karan",
    "dkny jeans": "Donna Karan",
    "marc by marc jacobs": "Marc Jacobs",
    "the marc jacobs": "Marc Jacobs",
    "versus versace": "Versace",
    "versace jeans": "Versace",
    "versace collection": "Versace",
    "gianni versace": "Gianni Versace",
    "miu miu": "Miu Miu",
    "prada sport": "Prada",
    "gucci": "Gucci",
    "tom ford for gucci": "Gucci",
    "mcq alexander mcqueen": "Alexander McQueen",
    "alexander mcqueen": "Alexander McQueen",
    "see by chloe": "Chloé",
    "see by chloé": "Chloé",
    "chloe": "Chloé",
    "red valentino": "Valentino",
    "valentino garavani": "Valentino",
    "moschino cheap and chic": "Moschino",
    "moschino cheap & chic": "Moschino",
    "love moschino": "Moschino",
    "missoni sport": "Missoni",
    "m missoni": "Missoni",
    "ck calvin klein": "Calvin Klein",
    "calvin klein jeans": "Calvin Klein",
    "calvin klein collection": "Calvin Klein",
    "ckj": "Calvin Klein",
    "vivienne westwood red label": "Vivienne Westwood",
    "vivienne westwood gold label": "Vivienne Westwood",
    "vivienne westwood anglomania": "Vivienne Westwood",
    "burberry prorsum": "Burberry",
    "burberry brit": "Burberry",
    "burberry london": "Burberry",
    "theory": "Theory",
    "helmut lang": "Helmut Lang",
    "max mara studio": "Max Mara",
    "sportmax": "Max Mara",
    "weekend max mara": "Max Mara",
    # Japanese lines
    "comme des garcons": "Comme des Garçons",
    "cdg": "Comme des Garçons",
    "comme des garçons homme plus": "Comme des Garçons",
    "comme des garçons ganryu": "Comme des Garçons",
    "comme des garçons tricot": "Comme des Garçons",
    "issey miyake pleats please": "Issey Miyake",
    "pleats please": "Issey Miyake",
    "junya watanabe man": "Junya Watanabe",
    # Y2K / Diffusion lines
    "bcbg": "BCBG Max Azria",
    "bcbg max azria": "BCBG Max Azria",
    "roberto cavalli class": "Roberto Cavalli",
    "just cavalli": "Roberto Cavalli",
    "cavalli": "Roberto Cavalli",
    "emanuel ungaro parallele": "Emanuel Ungaro",
    "jil sander navy": "Jil Sander",
    "kenzo jungle": "Kenzo Takada",
    "ann demeulemeester menswear": "Ann Demeulemeester",
    "romeo gigli menswear": "Romeo Gigli",
    "dsquared2": "DSquared2",
    "dsquared": "DSquared2",
    # Jewelry houses
    "tiffany & co": "Tiffany & Co",
    "tiffany and co": "Tiffany & Co",
    "tiffany": "Tiffany & Co",
    # Luxury houses
    "lv": "Louis Vuitton",
    "louis vuitton": "Louis Vuitton",
    "bottega veneta": "Bottega Veneta",
    "bottega": "Bottega Veneta",
}

def extract_designer(text: str) -> str:
    text_l = text.lower()
    
    # Debug logging
    print(f"[DEBUG] Searching for designer in: {text_l[:100]}...")
    
    # Check synonyms first (most specific)
    for syn, canonical in DESIGNER_SYNONYMS.items():
        if syn in text_l:
            print(f"[DEBUG] Found designer via synonym '{syn}' -> {canonical}")
            return canonical
    
    # Check full designer names (case-insensitive)
    # Sort by length (longest first) to match "Yves Saint Laurent" before "Saint Laurent"
    for designer in sorted(DESIGNERS, key=len, reverse=True):
        designer_lower = designer.lower()
        # Check if designer name appears as a whole word or part of a phrase
        # This catches "Escada Couture", "Polo Ralph Lauren", etc.
        if designer_lower in text_l:
            print(f"[DEBUG] Found designer in main list: {designer}")
            return designer
    
    print(f"[DEBUG] No designer found, returning 'unbranded'")
    return "unbranded"


CONDITION_MAP = {
    # PRISTINE
    "new with tags": "PRISTINE",
    "nwt": "PRISTINE",
    "new without tags": "PRISTINE",
    "nwot": "PRISTINE",
    "never worn": "PRISTINE",
    "perfect condition": "PRISTINE",
    "like new": "PRISTINE",
    "no visible signs of wear": "PRISTINE",
    "mint condition": "PRISTINE",
    "deadstock": "PRISTINE",
    "unused": "PRISTINE",
    "store-fresh": "PRISTINE",
    "pristine condition": "PRISTINE",
    "immaculate": "PRISTINE",
    "comes with original packaging": "PRISTINE",
    "comes with dust bag": "PRISTINE",
    "tried on only": "PRISTINE",
    "worn once": "PRISTINE",
    
    # VERY GOOD
    "excellent condition": "VERY GOOD",
    "gently used": "VERY GOOD",
    "gently worn": "VERY GOOD",
    "light wear": "VERY GOOD",
    "minor signs of wear": "VERY GOOD",
    "very minimal scuffing": "VERY GOOD",
    "small hairline scratches": "VERY GOOD",
    "slight fading": "VERY GOOD",
    "light creasing": "VERY GOOD",
    "minor surface wear": "VERY GOOD",
    "clean overall": "VERY GOOD",
    "great pre-owned condition": "VERY GOOD",
    "well-maintained": "VERY GOOD",
    "hardly worn": "VERY GOOD",
    "looks almost new": "VERY GOOD",
    
    # GOOD
    "good used condition": "GOOD",
    "moderate wear": "GOOD",
    "some signs of wear": "GOOD",
    "visible wear but still in good shape": "GOOD",
    "wear consistent with age": "GOOD",
    "wear consistent with use": "GOOD",
    "noticeable scuffs": "GOOD",
    "moderate fading": "GOOD",
    "moderate creasing": "GOOD",
    "some scratching": "GOOD",
    "used but well-kept": "GOOD",
    "light pilling": "GOOD",
    "slight stretching": "GOOD",
    "small marks or stains": "GOOD",
    "normal vintage wear": "GOOD",
    "still has lots of life left": "GOOD",
    
    # FAIR
    "fair condition": "FAIR",
    "heavily used": "FAIR",
    "well-loved": "FAIR",
    "significant wear": "FAIR",
    "visible flaws": "FAIR",
    "noticeable damage": "FAIR",
    "has imperfections": "FAIR",
    "repairs needed": "FAIR",
    "heavy scuffing": "FAIR",
    "significant fading": "FAIR",
    "marked or stained": "FAIR",
    "loose threads": "FAIR",
    "missing embellishments": "FAIR",
    "worn edges": "FAIR",
    "cracked leather": "FAIR",
    "sold as-is": "FAIR",
    "for restoration": "FAIR",
    "still wearable but shows wear": "FAIR",
}


def extract_condition(text: str) -> str | None:
    t = text.lower()
    print(f"[DEBUG] Searching for condition in: {t[:100]}...")
    # Sort by length (longest first) to catch specific phrases before generic ones
    for phrase in sorted(CONDITION_MAP.keys(), key=len, reverse=True):
        if phrase in t:
            print(f"[DEBUG] Found condition via phrase '{phrase}' -> {CONDITION_MAP[phrase]}")
            return CONDITION_MAP[phrase]
    print(f"[DEBUG] No condition found")
    return None


COLORS = [
    "Black", "White", "Ivory", "Cream", "Beige", "Tan", "Brown", "Chocolate",
    "Camel", "Navy", "Blue", "Light Blue", "Sky Blue", "Baby Blue", "Cobalt",
    "Royal Blue", "Teal", "Turquoise", "Green", "Olive", "Forest Green",
    "Hunter Green", "Mint", "Sage", "Yellow", "Mustard", "Gold", "Orange",
    "Coral", "Red", "Burgundy", "Maroon", "Pink", "Blush", "Hot Pink",
    "Magenta", "Purple", "Lavender", "Lilac", "Plum", "Grey", "Charcoal",
    "Silver", "Off-white", "Ecru", "Oatmeal", "Stone", "Sand", "Mocha",
    "Taupe", "Mahogany", "Chestnut", "Copper", "Rust", "Terracotta",
    "Peach", "Apricot", "Tangerine", "Rose", "Dusty Rose", "Fuchsia",
    "Aubergine", "Wine", "Emerald", "Lime", "Seafoam", "Pistachio",
    "Khaki", "Chartreuse", "Midnight Blue", "Denim Blue", "Periwinkle",
    "Indigo", "Slate", "Steel", "Gunmetal", "Ice Blue", "Butter",
    "Lemon", "Canary", "Sunflower", "Burnt Orange", "Bone", "Warm White",
    "Cool White", "Graphite", "Smoke", "Dove Grey", "Heather Grey",
    # Additional color variations
    "Eggplant", "Grape", "Mulberry", "Berry", "Cranberry", "Cherry",
    "Crimson", "Scarlet", "Tomato", "Brick", "Cinnamon", "Ginger",
    "Honey", "Amber", "Bronze", "Brass", "Marigold", "Saffron",
    "Ochre", "Sienna", "Umber", "Espresso", "Walnut", "Cognac",
    "Saddle", "Wheat", "Flax", "Straw", "Champagne", "Biscuit",
    "Vanilla", "Oyster", "Pearl", "Porcelain", "Chalk", "Frost",
    "Powder Blue", "Cerulean", "Azure", "Sapphire", "Denim",
    "Peacock", "Aegean", "Ocean", "Marine", "Aqua", "Cyan",
    "Pool", "Caribbean", "Jade", "Kelly Green", "Grass", "Clover",
    "Moss", "Olive Drab", "Army Green", "Avocado", "Pear",
    "Spring Green", "Neon Green", "Electric Blue", "Neon Pink",
    "Shocking Pink", "Bubblegum", "Carnation", "Salmon", "Melon",
    "Cantaloupe", "Papaya", "Mango", "Persimmon", "Pumpkin",
    "Carrot", "Flame", "Blood Orange", "Vermillion", "Fire Red",
    "Wine Red", "Oxblood", "Garnet", "Ruby", "Magenta",
    "Orchid", "Mauve", "Wisteria", "Periwinkle", "Violet",
    "Iris", "Amethyst", "Grape", "Eggplant", "Raisin",
    "Charcoal Grey", "Ash", "Pewter", "Lead", "Iron",
    "Nickel", "Titanium", "Platinum", "Chrome", "Mercury"
]


def extract_colors(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    # Sort by length (longest first) to match "Light Blue" before "Blue"
    for c in sorted(COLORS, key=len, reverse=True):
        if c.lower() in t:
            found.append(c)
    # dedupe while preserving order
    return list(dict.fromkeys(found))


# Product types - sorted longest first for matching
PRODUCT_TYPES = {
    # Dresses (all map to "Dress")
    "babydoll dress": "Dress",
    "bodycon dress": "Dress",
    "cocktail dress": "Dress",
    "empire waist dress": "Dress",
    "evening gown": "Dress",
    "fit-and-flare dress": "Dress",
    "halter dress": "Dress",
    "kaftan dress": "Dress",
    "maxi dress": "Dress",
    "midi dress": "Dress",
    "mini dress": "Dress",
    "one-shoulder dress": "Dress",
    "shirt dress": "Dress",
    "sheath dress": "Dress",
    "shift dress": "Dress",
    "slip dress": "Dress",
    "sun dress": "Dress",
    "sweater dress": "Dress",
    "wrap dress": "Dress",
    "a-line dress": "Dress",
    "backless dress": "Dress",
    "gown": "Dress",
    "dress": "Dress",
    
    # Tops (all map to "Tops")
    "button-down shirt": "Tops",
    "off-the-shoulder top": "Tops",
    "one-shoulder top": "Tops",
    "crop top": "Tops",
    "tube top": "Tops",
    "wrap top": "Tops",
    "corset top": "Tops",
    "peplum top": "Tops",
    "halter top": "Tops",
    "shell top": "Tops",
    "knit top": "Tops",
    "tank top": "Tops",
    "t-shirt": "Tops",
    "camisole": "Tops",
    "blouse": "Tops",
    "polo shirt": "Tops",
    "tunic": "Tops",
    "sweater": "Tops",
    "cardigan": "Tops",
    "bodysuit": "Tops",
    "sweatshirt": "Tops",
    "hoodie": "Tops",
    "vest": "Tops",
    "bustier": "Tops",
    "bralette": "Tops",
    "top": "Tops",
    
    # Outerwear (all map to "Jackets / Blazers")
    "trench coat": "Jackets / Blazers",
    "peacoat": "Jackets / Blazers",
    "duster coat": "Jackets / Blazers",
    "car coat": "Jackets / Blazers",
    "puffer jacket": "Jackets / Blazers",
    "quilted jacket": "Jackets / Blazers",
    "bomber jacket": "Jackets / Blazers",
    "leather jacket": "Jackets / Blazers",
    "denim jacket": "Jackets / Blazers",
    "moto jacket": "Jackets / Blazers",
    "wool coat": "Jackets / Blazers",
    "fur coat": "Jackets / Blazers",
    "suit jacket": "Jackets / Blazers",
    "blazer": "Jackets / Blazers",
    "overcoat": "Jackets / Blazers",
    "cape": "Jackets / Blazers",
    "poncho": "Jackets / Blazers",
    "raincoat": "Jackets / Blazers",
    "windbreaker": "Jackets / Blazers",
    "parka": "Jackets / Blazers",
    "jacket": "Jackets / Blazers",
    "coat": "Jackets / Blazers",
    
    # Bottoms (all map to "Pants")
    "wide-leg pants": "Pants",
    "straight-leg pants": "Pants",
    "skinny pants": "Pants",
    "palazzo pants": "Pants",
    "harem pants": "Pants",
    "dress pants": "Pants",
    "cargo pants": "Pants",
    "bermuda shorts": "Pants",
    "denim shorts": "Pants",
    "jeans": "Pants",
    "trousers": "Pants",
    "sweatpants": "Pants",
    "joggers": "Pants",
    "leggings": "Pants",
    "culottes": "Pants",
    "capris": "Pants",
    "shorts": "Pants",
    "skort": "Pants",
    
    # Skirts (all map to "Skirts")
    "mini skirt": "Skirts",
    "midi skirt": "Skirts",
    "maxi skirt": "Skirts",
    "pencil skirt": "Skirts",
    "a-line skirt": "Skirts",
    "pleated skirt": "Skirts",
    "slip skirt": "Skirts",
    "wrap skirt": "Skirts",
    "circle skirt": "Skirts",
    "tiered skirt": "Skirts",
    "denim skirt": "Skirts",
    "leather skirt": "Skirts",
    "skirt": "Skirts",
    
    # Bags (all map to "Bags")
    "shoulder bag": "Bags",
    "crossbody bag": "Bags",
    "messenger bag": "Bags",
    "satchel bag": "Bags",
    "hobo bag": "Bags",
    "bucket bag": "Bags",
    "saddle bag": "Bags",
    "bowler bag": "Bags",
    "doctor bag": "Bags",
    "frame bag": "Bags",
    "box bag": "Bags",
    "top handle bag": "Bags",
    "tote bag": "Bags",
    "shopping bag": "Bags",
    "beach bag": "Bags",
    "weekender bag": "Bags",
    "duffle bag": "Bags",
    "travel bag": "Bags",
    "clutch bag": "Bags",
    "envelope clutch": "Bags",
    "minaudiere": "Bags",
    "wristlet": "Bags",
    "evening bag": "Bags",
    "backpack": "Bags",
    "rucksack": "Bags",
    "drawstring bag": "Bags",
    "pouchette": "Bags",
    "pochette": "Bags",
    "pouch": "Bags",
    "makeup bag": "Bags",
    "cosmetic bag": "Bags",
    "coin purse": "Bags",
    "wallet": "Bags",
    "cardholder": "Bags",
    "card case": "Bags",
    "bag": "Bags",
    "purse": "Bags",
    "handbag": "Bags",
    "clutch": "Bags",
    "tote": "Bags",
    
    # Shoes - Heels (all map to "Heels")
    "ankle-strap heels": "Heels",
    "slingback heels": "Heels",
    "peep-toe heels": "Heels",
    "platform heels": "Heels",
    "t-strap heels": "Heels",
    "mary jane heels": "Heels",
    "d'orsay heels": "Heels",
    "block heels": "Heels",
    "kitten heels": "Heels",
    "wedge heels": "Heels",
    "stilettos": "Heels",
    "pumps": "Heels",
    "heels": "Heels",
    
    # Shoes - Boots (all map to "Boots")
    "over-the-knee boots": "Boots",
    "thigh-high boots": "Boots",
    "knee-high boots": "Boots",
    "mid-calf boots": "Boots",
    "ankle boots": "Boots",
    "chelsea boots": "Boots",
    "cowboy boots": "Boots",
    "combat boots": "Boots",
    "moto boots": "Boots",
    "sock boots": "Boots",
    "platform boots": "Boots",
    "wedge boots": "Boots",
    "rain boots": "Boots",
    "snow boots": "Boots",
    "hiking boots": "Boots",
    "boots": "Boots",
    
    # Shoes - Flats (all map to "Flats")
    "mary jane flats": "Flats",
    "pointed-toe flats": "Flats",
    "oxford flats": "Flats",
    "derby flats": "Flats",
    "espadrille flats": "Flats",
    "smoking slippers": "Flats",
    "ballet flats": "Flats",
    "loafers": "Flats",
    "moccasins": "Flats",
    "flats": "Flats",
    
    # Shoes - Sandals (all map to "Sandals")
    "gladiator sandals": "Sandals",
    "strappy sandals": "Sandals",
    "t-strap sandals": "Sandals",
    "fisherman sandals": "Sandals",
    "espadrille sandals": "Sandals",
    "platform sandals": "Sandals",
    "wedge sandals": "Sandals",
    "flat sandals": "Sandals",
    "thong sandals": "Sandals",
    "flip-flops": "Sandals",
    "slides": "Sandals",
    "sandals": "Sandals",
    
    # Shoes - Sneakers (all map to "Sneakers")
    "high-top sneakers": "Sneakers",
    "low-top sneakers": "Sneakers",
    "platform sneakers": "Sneakers",
    "slip-on sneakers": "Sneakers",
    "dad sneakers": "Sneakers",
    "chunky sneakers": "Sneakers",
    "running sneakers": "Sneakers",
    "fashion sneakers": "Sneakers",
    "court sneakers": "Sneakers",
    "canvas sneakers": "Sneakers",
    "sneakers": "Sneakers",
    
    # Shoes - Mules (all map to "Mules")
    "platform clogs": "Mules",
    "mule heels": "Mules",
    "mule flats": "Mules",
    "clogs": "Mules",
    "mules": "Mules",
    
    # Shoes - Slippers (all map to "Slippers")
    "shearling slippers": "Slippers",
    "house slippers": "Slippers",
    "slippers": "Slippers",
    
    # Jewelry
    "statement necklace": "Statement necklace",
    "pendant necklace": "Pendant necklace",
    "chain necklace": "Chain necklace",
    "choker necklace": "Choker necklace",
    "collar necklace": "Collar necklace",
    "bib necklace": "Bib necklace",
    "lariat necklace": "Lariat necklace",
    "pearl necklace": "Pearl necklace",
    "rope necklace": "Rope necklace",
    "necklace": "Necklace",
    "statement earrings": "Statement earrings",
    "drop earrings": "Drop earrings",
    "dangle earrings": "Dangle earrings",
    "chandelier earrings": "Chandelier earrings",
    "hoop earrings": "Hoop earrings",
    "stud earrings": "Stud earrings",
    "clip-on earrings": "Clip-on earrings",
    "ear cuffs": "Ear cuffs",
    "earrings": "Earrings",
    "charm bracelet": "Charm bracelet",
    "bangle bracelet": "Bangle bracelet",
    "cuff bracelet": "Cuff bracelet",
    "chain bracelet": "Chain bracelet",
    "tennis bracelet": "Tennis bracelet",
    "beaded bracelet": "Beaded bracelet",
    "friendship bracelet": "Friendship bracelet",
    "bracelet": "Bracelet",
    "statement ring": "Statement ring",
    "cocktail ring": "Cocktail ring",
    "signet ring": "Signet ring",
    "band ring": "Band ring",
    "stackable ring": "Stackable ring",
    "midi ring": "Midi ring",
    "knuckle ring": "Knuckle ring",
    "ring": "Ring",
    "vintage brooch": "Vintage brooch",
    "cameo brooch": "Cameo brooch",
    "crystal brooch": "Crystal brooch",
    "floral brooch": "Floral brooch",
    "animal brooch": "Animal brooch",
    "brooch": "Brooch",
    "enamel pin": "Enamel pin",
    "lapel pin": "Lapel pin",
    "hat pin": "Hat pin",
    "pin": "Pin",
    
    # Accessories
    "statement belt": "Statement belt",
    "chain belt": "Chain belt",
    "leather belt": "Leather belt",
    "wide belt": "Wide belt",
    "skinny belt": "Skinny belt",
    "obi belt": "Obi belt",
    "corset belt": "Corset belt",
    "belt": "Belt",
    "silk scarf": "Silk scarf",
    "cashmere scarf": "Cashmere scarf",
    "wool scarf": "Wool scarf",
    "pashmina": "Pashmina",
    "infinity scarf": "Infinity scarf",
    "square scarf": "Square scarf",
    "oblong scarf": "Oblong scarf",
    "scarf": "Scarf",
    "leather gloves": "Leather gloves",
    "driving gloves": "Driving gloves",
    "evening gloves": "Evening gloves",
    "opera gloves": "Opera gloves",
    "fingerless gloves": "Fingerless gloves",
    "gloves": "Gloves",
}


def extract_type(text: str) -> str | None:
    t = text.lower()
    print(f"[DEBUG] Searching for product type in: {t[:100]}...")
    
    # Sorted by length to match specific types before generic
    for phrase in sorted(PRODUCT_TYPES.keys(), key=len, reverse=True):
        # Use word boundaries to avoid matching "ring" in "offering"
        # For multi-word phrases like "shoulder bag", check exact phrase
        # For single words, check with word boundaries
        import re
        
        # Escape special regex characters in phrase
        escaped_phrase = re.escape(phrase)
        
        # Check for whole word/phrase matches
        # Use word boundaries (\b) for single words
        if ' ' in phrase:
            # Multi-word phrase: just check if full phrase exists
            pattern = r'\b' + escaped_phrase.replace(r'\ ', r'\s+') + r'\b'
        else:
            # Single word: use word boundaries
            pattern = r'\b' + escaped_phrase + r'\b'
        
        if re.search(pattern, t):
            print(f"[DEBUG] Found product type via phrase '{phrase}' -> {PRODUCT_TYPES[phrase]}")
            return PRODUCT_TYPES[phrase]
    
    print(f"[DEBUG] No product type found")
    return None


def extract_era(text: str) -> str | None:
    t = text.lower()
    
    # Check for specific eras
    if any(x in t for x in ["1960s", "60s", "sixties", "mod era", "youthquake", "space age", "vintage 60s", "twiggy"]):
        return "1960s"
    if any(x in t for x in ["1970s", "70s", "seventies", "disco era", "boho era", "hippie era", "studio 54", "vintage 70s"]):
        return "1970s"
    if any(x in t for x in ["1980s", "80s", "eighties", "power dressing", "shoulder pad era", "vintage 80s", "new wave"]):
        return "1980s"
    if any(x in t for x in ["1990s", "90s", "nineties", "grunge", "minimalist era", "supermodel era", "vintage 90s"]):
        return "1990s"
    if any(x in t for x in ["y2k", "2000s", "00s", "early 2000s", "mcbling", "millennium fashion", "paris hilton era"]):
        return "2000s / Y2K"
    if any(x in t for x in ["2010s", "10s", "early 2010s", "normcore", "athleisure"]):
        return "2010s"
    
    # Check for seasons
    if any(x in t for x in ["spring/summer", "spring summer", "s/s", "ss", "resort", "cruise"]):
        return "Spring/Summer"
    if any(x in t for x in ["fall/winter", "fall winter", "f/w", "fw", "autumn/winter"]):
        return "Fall/Winter"
    
    return None


MATERIALS = [
    "Organic cotton", "Pima cotton", "Supima cotton", "Cotton",
    "Flax", "Linen", "Hemp",
    "Mulberry silk", "Charmeuse", "Chiffon", "Organza", "Crepe de chine",
    "Twill silk", "Silk",
    "Crushed velvet", "Silk velvet", "Velvet",
    "Satin",
    "Modal", "Lyocell", "Tencel", "Cupro", "Viscose", "Rayon",
    "Bamboo", "Acetate",
    "Recycled polyester", "Polyester",
    "Recycled nylon", "Nylon",
    "Spandex", "Elastane", "Lycra",
    "Acrylic", "Polyamide", "Polyurethane",
    "Vegan leather", "Faux leather", "PU leather", "Bonded leather",
    "Cowhide", "Sheepskin", "Lambskin", "Goatskin", "Pigskin",
    "Leather", "Suede", "Nubuck", "Patent leather",
    "Shearling",
    "Merino wool", "Cashmere", "Mongolian cashmere", "Alpaca",
    "Mohair", "Angora", "Camel hair", "Yak wool", "Wool",
    "Tweed", "Bouclé", "Felted wool",
    "Cotton jersey", "Wool jersey", "Silk jersey", "Jersey",
    "Rib knit", "Chunky knit", "Cable knit", "Pointelle", "Knit",
    "Sherpa", "Fleece",
    "French terry", "Terry cloth",
    "Neoprene", "Power mesh", "Mesh",
    "Tulle", "Guipure lace", "Embroidered lace", "Lace",
    "Broderie anglaise", "Eyelet",
    "Brocade", "Jacquard",
    "Raw denim", "Stretch denim", "Denim",
    "Corduroy", "Canvas", "Poplin", "Twill", "Gabardine",
    "Crepe", "Georgette", "Scuba",
    "Sequins", "Beaded", "Embellished",
    "Metallic fabric", "Lamé", "Foil fabric",
    "Leatherette", "Rubber", "PVC", "Vinyl", "Plastic",
    "Raffia", "Jute", "Straw", "Wicker",
    "Patent synthetic", "Microfiber",
    "Gore-Tex", "Softshell",
    "Down", "Feathers",
    "Fox fur", "Mink fur", "Rabbit fur", "Raccoon fur", "Faux fur",
]


def extract_materials(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    # Sort by length to match specific materials before generic
    for m in sorted(MATERIALS, key=len, reverse=True):
        if m.lower() in t:
            found.append(m)
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
    POST /admin/api/2025-10/products/{product_id}/metafields.json
    one metafield at a time, not as a bulk list.
    """
    if not SHOPIFY_API_TOKEN or not SHOPIFY_STORE_DOMAIN:
        print("Shopify credentials missing; skipping metafield write.")
        return

    base_url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/2025-10/products/{product_id}/metafields.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_API_TOKEN,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for mf in metafields:
            payload = {"metafield": mf}
            print(f"Attempting to create metafield: {mf['key']} = {mf['value']}")
            resp = await client.post(base_url, headers=headers, json=payload)
            if resp.status_code >= 300:
                print(f"Error from Shopify metafields: {resp.status_code} {resp.text}")
            else:
                print(f"Successfully created metafield: {mf['key']}")


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
    
    # Verify HMAC
    if not hmac_header or not verify_shopify_hmac(raw_body, hmac_header):
        print("HMAC verification failed!")
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
