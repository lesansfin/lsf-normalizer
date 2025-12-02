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
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "")

def verify_shopify_hmac(request_body: bytes, hmac_header: str) -> bool:
    if not SHOPIFY_SECRET:
        return False
    digest = hmac.new(SHOPIFY_SECRET.encode("utf-8"), request_body, hashlib.sha256).digest()
    calculated_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(calculated_hmac, hmac_header)

# Comprehensive designer list (from your old code)
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
    "Madeleine Vionnet", "Elsa Schiaparelli", "Jean Patou", "Jeanne Lanvin",
    "Nina Ricci", "Carven", "Madame Grès", "Paul Poiret", "Mainbocher",
    "Jacques Fath", "Guy Laroche", "Courrèges",
    "Liz Claiborne", "Anne Fogarty", "Lilli Ann", "Adrienne Vittadini",
    "Stephen Sprouse", "Giorgio di Sant'Angelo", "Janice Wainwright",
    "Fendi", "Trussardi", "Krizia", "Sportmax", "Genny", "Gianni Versace",
    "Fiorucci", "Miss Deanna", "Blumarine", "Brioni", "Laura Biagiotti",
    "Emilio Pucci", "Matsuda", "Comme des Garçons", "Tsumori Chisato",
    "Dries Van Noten", "Dirk Bikkembergs", "Walter Van Beirendonck",
    "Patrick Van Ommeslaeghe", "Hardy Amies", "Bruce Oldfield", "Jasper Conran", "Bella Freud",
    "Matthew Williamson", "Ozwald Boateng", "John Richmond",
    "Margaret Howell", "A.P.C.", "Acne Studios", "Rick Owens",
    "Jean-Charles de Castelbajac", "Delvaux", "Loewe", "Mulberry", "Coach", "Bally", "Ferragamo",
    "Cartier", "Tiffany", "Tiffany & Co", "Louis Vuitton", "Bottega Veneta",
    "Filippa K", "Tiger of Sweden", "Weekday",
    "BCBG Max Azria", "Baby Phat", "Heatherette", "Anna Molinari", "DSquared2", "Morgan de Toi",
    "Dolce & Gabbana", "Dolce and Gabbana", "Levi's", "Levis", "Chanel", "Manolo Blahnik", "Timmy Woods"
]

# ENHANCED DESIGNER SYNONYMS with many more common variations
DESIGNER_SYNONYMS = {
    # Yves Saint Laurent variations
    "ysl": "Yves Saint Laurent", "saint laurent": "Yves Saint Laurent",
    "st laurent": "Yves Saint Laurent", "yves st laurent": "Yves Saint Laurent",
    "saint laurent paris": "Yves Saint Laurent", "ysl rive gauche": "Yves Saint Laurent",
    
    # Christian Dior variations
    "dior": "Christian Dior", "christian dior": "Christian Dior",
    "dior homme": "Christian Dior", "baby dior": "Christian Dior",
    "miss dior": "Christian Dior",
    
    # Balenciaga variations
    "balenciaga": "Cristóbal Balenciaga", "cristobal balenciaga": "Cristóbal Balenciaga",
    
    # Givenchy variations
    "givenchy": "Hubert de Givenchy", "givenchy sport": "Hubert de Givenchy",
    "givenchy play": "Hubert de Givenchy",
    
    # Hermès variations
    "hermes": "Hermès", "hermès": "Hermès",
    
    # Céline variations
    "celine": "Céline", "céline": "Céline",
    
    # Gucci variations
    "gucci": "Gucci", "tom ford for gucci": "Gucci",
    
    # Fendi variations
    "fendi": "Fendi", "fendissime": "Fendi",
    
    # J.Crew variations
    "jcrew": "Jcrew", "j crew": "Jcrew", "j.crew": "Jcrew",
    
    # Escada variations
    "escada couture": "Escada", "escada sport": "Escada", 
    "escada margaretha ley": "Escada", "escada": "Escada",
    
    # Armani variations
    "armani exchange": "Armani", "emporio armani": "Armani", 
    "giorgio armani": "Armani", "armani collezioni": "Armani",
    "armani jeans": "Armani", "a/x armani exchange": "Armani",
    "ax armani": "Armani", "ea7": "Armani",
    
    # Ralph Lauren variations
    "polo ralph lauren": "Ralph Lauren", "ralph lauren collection": "Ralph Lauren",
    "lauren ralph lauren": "Ralph Lauren", "polo sport": "Ralph Lauren",
    "rrl": "Ralph Lauren", "double rl": "Ralph Lauren",
    "ralph lauren purple label": "Ralph Lauren", "ralph lauren black label": "Ralph Lauren",
    "polo by ralph lauren": "Ralph Lauren", "rl": "Ralph Lauren",
    
    # Donna Karan variations
    "dkny": "Donna Karan", "donna karan new york": "Donna Karan", 
    "dkny jeans": "Donna Karan", "dkny active": "Donna Karan",
    
    # Marc Jacobs variations
    "marc by marc jacobs": "Marc Jacobs", "the marc jacobs": "Marc Jacobs",
    "marc jacobs collection": "Marc Jacobs",
    
    # Versace variations
    "versus versace": "Versace", "versace jeans": "Versace", 
    "versace collection": "Versace", "gianni versace": "Gianni Versace",
    "versace jeans couture": "Versace", "versace sport": "Versace",
    "atelier versace": "Versace",
    
    # Prada variations
    "miu miu": "Miu Miu", "prada sport": "Prada",
    "prada linea rossa": "Prada",
    
    # Alexander McQueen variations
    "mcq alexander mcqueen": "Alexander McQueen",
    "alexander mcqueen": "Alexander McQueen", "mcq": "Alexander McQueen",
    
    # Chloé variations
    "see by chloe": "Chloé", "see by chloé": "Chloé",
    "chloe": "Chloé", "chloé": "Chloé",
    
    # Valentino variations
    "red valentino": "Valentino", "valentino garavani": "Valentino",
    "valentino red": "Valentino", "valentino roma": "Valentino",
    
    # Moschino variations
    "moschino cheap and chic": "Moschino", "moschino cheap & chic": "Moschino", 
    "love moschino": "Moschino", "moschino couture": "Moschino",
    
    # Missoni variations
    "missoni sport": "Missoni", "m missoni": "Missoni",
    "missoni mare": "Missoni",
    
    # Calvin Klein variations
    "ck calvin klein": "Calvin Klein", "calvin klein jeans": "Calvin Klein",
    "calvin klein collection": "Calvin Klein", "ckj": "Calvin Klein",
    "ck": "Calvin Klein", "calvin klein underwear": "Calvin Klein",
    "calvin klein performance": "Calvin Klein",
    
    # Vivienne Westwood variations
    "vivienne westwood red label": "Vivienne Westwood", 
    "vivienne westwood gold label": "Vivienne Westwood",
    "vivienne westwood anglomania": "Vivienne Westwood",
    "vivienne westwood man": "Vivienne Westwood",
    
    # Burberry variations
    "burberry prorsum": "Burberry", "burberry brit": "Burberry", 
    "burberry london": "Burberry", "burberry sport": "Burberry",
    "burberry check": "Burberry", "burberrys": "Burberry",
    
    # London Fog variations
    "london fog": "London Fog",

     # Jimmy Choo variations
    "Jimmy Choo": "Jimmy Choo",

     # Chanel variations
    "Karl Lagerfeld": "Chanel",
    
    # Theory variations
    "theory": "Theory",
    
    # Helmut Lang variations
    "helmut lang": "Helmut Lang", "helmut lang jeans": "Helmut Lang",
    
    # Max Mara variations
    "max mara studio": "Max Mara", "sportmax": "Max Mara", 
    "weekend max mara": "Max Mara", "maxmara": "Max Mara",
    "max & co": "Max Mara", "max and co": "Max Mara",
    
    # Comme des Garçons variations
    "comme des garcons": "Comme des Garçons", "cdg": "Comme des Garçons",
    "comme des garçons homme plus": "Comme des Garçons", 
    "comme des garçons ganryu": "Comme des Garçons",
    "comme des garçons tricot": "Comme des Garçons",
    "comme des garcons play": "Comme des Garçons",
    "cdg play": "Comme des Garçons",
    
    # Issey Miyake variations
    "issey miyake pleats please": "Issey Miyake",
    "pleats please": "Issey Miyake", "pleats please issey miyake": "Issey Miyake",
    "haat issey miyake": "Issey Miyake",
    
    # Junya Watanabe variations
    "junya watanabe man": "Junya Watanabe",
    "junya watanabe cdg": "Junya Watanabe",
    
    # BCBG variations
    "bcbg": "BCBG Max Azria", "bcbg max azria": "BCBG Max Azria",
    "bcbgmaxazria": "BCBG Max Azria", "bcbgeneration": "BCBG Max Azria",
    
    # Roberto Cavalli variations
    "roberto cavalli class": "Roberto Cavalli", "just cavalli": "Roberto Cavalli", 
    "cavalli": "Roberto Cavalli", "cavalli class": "Roberto Cavalli",
    
    # Emanuel Ungaro variations
    "emanuel ungaro parallele": "Emanuel Ungaro", "ungaro": "Emanuel Ungaro",
    
    # Jil Sander variations
    "jil sander navy": "Jil Sander", "jil sander +": "Jil Sander",
    
    # Kenzo variations
    "kenzo jungle": "Kenzo Takada", "kenzo": "Kenzo Takada",
    
    # Ann Demeulemeester variations
    "ann demeulemeester menswear": "Ann Demeulemeester",
    
    # Romeo Gigli variations
    "romeo gigli menswear": "Romeo Gigli",
    
    # DSquared2 variations
    "dsquared2": "DSquared2", "dsquared": "DSquared2",
    "d squared": "DSquared2", "d2": "DSquared2",
    
    # Tiffany & Co variations
    "tiffany & co": "Tiffany & Co", "tiffany and co": "Tiffany & Co", 
    "tiffany": "Tiffany & Co", "tiffany co": "Tiffany & Co",
    
    # Cartier variations
    "cartier": "Cartier",
    
    # Louis Vuitton variations
    "lv": "Louis Vuitton", "louis vuitton": "Louis Vuitton",
    "vuitton": "Louis Vuitton",
    
    # Bottega Veneta variations
    "bottega veneta": "Bottega Veneta", "bottega": "Bottega Veneta",
    "bv": "Bottega Veneta",
    
    # Additional common variations
    "ferragamo": "Ferragamo", "salvatore ferragamo": "Ferragamo",
    "balmain": "Balmain", "pierre balmain": "Balmain",
    "lanvin": "Lanvin", "jeanne lanvin": "Jeanne Lanvin",
    "acne": "Acne Studios", "acne studios": "Acne Studios",
    "apc": "A.P.C.", "a.p.c.": "A.P.C.",
    "rag & bone": "Rag & Bone", "rag and bone": "Rag & Bone",
    
    # Dolce & Gabbana variations
    "dolce & gabbana": "Dolce & Gabbana", "dolce and gabbana": "Dolce & Gabbana",
    "d&g": "Dolce & Gabbana", "d & g": "Dolce & Gabbana",
    "dolce gabbana": "Dolce & Gabbana", "dolce": "Dolce & Gabbana",
    
    # Levi's variations
    "levi's": "Levi's", "levis": "Levi's", "levi strauss": "Levi's",
    "levis strauss": "Levi's", "levi": "Levi's",
}

def extract_designer(text: str) -> str:
    text_l = text.lower()
    print(f"[DEBUG] Searching for designer in: {text_l[:100]}...")
    
    # Check synonyms first (longest to shortest to match most specific first)
    for syn, canonical in sorted(DESIGNER_SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True):
        # Special handling for patterns with special characters
        escaped = re.escape(syn)
        # Replace escaped spaces with flexible whitespace matcher
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # For patterns with & or other special chars, use lookaround instead of \b
        if '&' in syn or any(c in syn for c in ['&', '-', '/', '.']):
            # Use word boundary at start and whitespace/punctuation/end at the end
            pattern = r'(?<!\w)' + escaped + r'(?!\w)'
        else:
            pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, text_l):
            print(f"[DEBUG] Found designer via synonym '{syn}' -> {canonical}")
            return canonical
    
    # Check main designer list
    for designer in sorted(DESIGNERS, key=len, reverse=True):
        designer_lower = designer.lower()
        escaped = re.escape(designer_lower)
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # For patterns with special chars, use lookaround instead of \b
        if '&' in designer_lower or any(c in designer_lower for c in ['&', '-', '/', '.']):
            pattern = r'(?<!\w)' + escaped + r'(?!\w)'
        else:
            pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, text_l):
            print(f"[DEBUG] Found designer in main list: {designer}")
            return designer
    
    print(f"[DEBUG] No designer found, returning 'unbranded'")
    return "unbranded"

# ENHANCED CONDITION MAP with more variations
CONDITION_MAP = {
    # NEW conditions
    "new with tags": "NEW", "nwt": "NEW", "brand new": "NEW", "never worn": "NEW",
    "new without tags": "NEW", "nwot": "NEW", "deadstock": "NEW",
    "brand new with tags": "NEW", "bnwt": "NEW", "still has tags": "NEW",
    "tags attached": "NEW", "new in bag": "NEW", "new in box": "NEW",
    "nib": "NEW", "unused": "NEW", "unworn": "NEW",
    
    # LIKE NEW conditions
    "like new": "LIKE NEW", "mint": "LIKE NEW", "mint condition": "LIKE NEW", 
    "pristine": "LIKE NEW", "perfect condition": "LIKE NEW", "as new": "LIKE NEW",
    "virtually new": "LIKE NEW", "nearly new": "LIKE NEW", "barely worn": "LIKE NEW",
    "worn once": "LIKE NEW", "worn 1x": "LIKE NEW", "like-new": "LIKE NEW",
    "pristine condition": "LIKE NEW", "flawless": "LIKE NEW", "flawless condition": "LIKE NEW",
    
    # EXCELLENT conditions
    "excellent": "EXCELLENT", "excellent condition": "EXCELLENT", 
    "near mint": "EXCELLENT", "near-mint": "EXCELLENT", "exc condition": "EXCELLENT",
    "exc": "EXCELLENT", "euc": "EXCELLENT", "excellent used condition": "EXCELLENT",
    "excellent pre-owned": "EXCELLENT", "excellent preowned": "EXCELLENT",
    
    # VERY GOOD conditions
    "very good": "VERY GOOD", "very good condition": "VERY GOOD", 
    "very good pre-owned condition": "VERY GOOD", "vgc": "VERY GOOD",
    "great condition": "VERY GOOD", "gently used": "VERY GOOD",
    "very good used condition": "VERY GOOD", "minimal wear": "VERY GOOD",
    "light wear": "VERY GOOD", "gently worn": "VERY GOOD",
    
    # GOOD conditions
    "good": "GOOD", "good condition": "GOOD", "lightly used": "GOOD", 
    "pre-owned": "GOOD", "preowned": "GOOD", "gc": "GOOD",
    "good used condition": "GOOD", "good vintage condition": "GOOD",
    "normal wear": "GOOD", "moderate wear": "GOOD", "some signs of wear": "GOOD",
    
    # FAIR conditions
    "fair": "FAIR", "fair condition": "FAIR", "shows wear": "FAIR", 
    "some wear": "FAIR", "well-loved": "FAIR", "vintage condition": "FAIR",
    "well worn": "FAIR", "visible wear": "FAIR", "noticeable wear": "FAIR",
    "fair vintage": "FAIR", "loved": "FAIR",
    
    # POOR conditions
    "poor": "POOR", "for parts": "POOR", "damaged": "POOR", 
    "heavily worn": "POOR", "poor condition": "POOR", "as is": "POOR",
    "as-is": "POOR", "needs repair": "POOR", "needs work": "POOR",
    "distressed": "POOR", "major flaws": "POOR",
}

def extract_condition(text: str) -> str | None:
    t = text.lower()
    print(f"[DEBUG] Searching for condition in: {t[:100]}...")
    
    # Sort by length (longest first) to match most specific phrases first
    for phrase in sorted(CONDITION_MAP.keys(), key=len, reverse=True):
        escaped = re.escape(phrase)
        # Replace escaped spaces with flexible whitespace
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # Use word boundaries to prevent matching within words
        pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, t):
            print(f"[DEBUG] Found condition via phrase '{phrase}' -> {CONDITION_MAP[phrase]}")
            return CONDITION_MAP[phrase]
    
    print(f"[DEBUG] No condition found")
    return None

# ENHANCED COLORS with more variations
COLORS = [
    # Black variations
    "Black", "Jet Black", "Pure Black", "True Black", "Onyx", "Ebony",
    
    # White variations
    "White", "Pure White", "Bright White", "Snow White", "Ivory", "Cream", 
    "Off-white", "Ecru", "Eggshell", "Bone", "Warm White", "Cool White",
    
    # Beige/Tan/Brown variations
    "Beige", "Tan", "Brown", "Chocolate", "Camel", "Sand", "Stone",
    "Oatmeal", "Taupe", "Mocha", "Mahogany", "Chestnut", "Cognac",
    "Saddle", "Wheat", "Flax", "Straw", "Champagne", "Biscuit",
    "Khaki", "Walnut", "Espresso", "Sienna", "Umber", "Cinnamon",
    "Ginger", "Honey", "Amber", "Bronze", "Brass", "Copper",
    "Rust", "Terracotta", "Burnt Orange",
    
    # Blue variations
    "Navy", "Blue", "Light Blue", "Sky Blue", "Baby Blue", "Cobalt",
    "Royal Blue", "Teal", "Turquoise", "Denim Blue", "Powder Blue",
    "Cerulean", "Azure", "Sapphire", "Denim", "Peacock", "Aegean",
    "Ocean", "Marine", "Aqua", "Cyan", "Pool", "Caribbean",
    "Electric Blue", "Midnight Blue", "Periwinkle", "Indigo",
    "Ice Blue", "Steel Blue",
    
    # Green variations
    "Green", "Olive", "Forest Green", "Hunter Green", "Mint", "Sage",
    "Emerald", "Lime", "Seafoam", "Pistachio", "Jade", "Kelly Green",
    "Grass", "Clover", "Moss", "Olive Drab", "Army Green", "Avocado",
    "Pear", "Spring Green", "Neon Green", "Chartreuse",
    
    # Yellow/Gold variations
    "Yellow", "Mustard", "Gold", "Butter", "Lemon", "Canary",
    "Sunflower", "Marigold", "Saffron", "Ochre",
    
    # Orange variations
    "Orange", "Coral", "Peach", "Apricot", "Tangerine", "Melon",
    "Cantaloupe", "Papaya", "Mango", "Persimmon", "Pumpkin",
    "Carrot", "Flame", "Blood Orange", "Vermillion",
    
    # Red variations
    "Red", "Burgundy", "Maroon", "Fire Red", "Wine Red", "Wine",
    "Oxblood", "Garnet", "Ruby", "Crimson", "Scarlet", "Tomato",
    "Brick", "Cherry", "Cranberry",
    
    # Pink variations
    "Pink", "Blush", "Hot Pink", "Magenta", "Fuchsia", "Rose",
    "Dusty Rose", "Shocking Pink", "Bubblegum", "Carnation",
    "Salmon", "Neon Pink",
    
    # Purple variations
    "Purple", "Lavender", "Lilac", "Plum", "Aubergine", "Eggplant",
    "Grape", "Mulberry", "Berry", "Orchid", "Mauve", "Wisteria",
    "Violet", "Iris", "Amethyst", "Raisin",
    
    # Grey variations
    "Grey", "Gray", "Charcoal", "Silver", "Graphite", "Smoke",
    "Dove Grey", "Heather Grey", "Slate", "Steel", "Gunmetal",
    "Ash", "Pewter", "Lead", "Iron", "Charcoal Grey",
    
    # Metallic variations
    "Nickel", "Titanium", "Platinum", "Chrome", "Mercury",
    "Metallic", "Gold", "Silver", "Bronze", "Copper",
    
    # Multi-color
    "Multicolor", "Multi-color", "Multi", "Print", "Patterned",
    "Floral", "Striped", "Polka Dot", "Animal Print", "Leopard",
    "Zebra", "Tie-dye", "Rainbow",
]

def extract_colors(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    
    # Sort by length (longest first) to match compound colors before simple ones
    for c in sorted(COLORS, key=len, reverse=True):
        c_lower = c.lower()
        escaped = re.escape(c_lower)
        # Replace escaped spaces with flexible whitespace
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # Use word boundaries to prevent matching within words (e.g., "Red" in "Fred")
        pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, t) and c not in found:
            found.append(c)
    
    return found

# ENHANCED PRODUCT_TYPES with more variations
PRODUCT_TYPES = {
    # Dress variations
    "babydoll dress": "Dress", "bodycon dress": "Dress", "cocktail dress": "Dress",
    "empire waist dress": "Dress", "evening gown": "Dress", "fit-and-flare dress": "Dress",
    "halter dress": "Dress", "kaftan dress": "Dress", "maxi dress": "Dress",
    "midi dress": "Dress", "mini dress": "Dress", "one-shoulder dress": "Dress",
    "shirt dress": "Dress", "sheath dress": "Dress", "shift dress": "Dress",
    "slip dress": "Dress", "sun dress": "Dress", "sweater dress": "Dress",
    "wrap dress": "Dress", "a-line dress": "Dress", "backless dress": "Dress",
    "gown": "Dress", "dress": "Dress", "cocktail gown": "Dress",
    "ball gown": "Dress", "party dress": "Dress", "summer dress": "Dress",
    "day dress": "Dress", "casual dress": "Dress", "formal dress": "Dress",
    "long dress": "Dress", "short dress": "Dress", "sleeveless dress": "Dress",
    "long sleeve dress": "Dress", "strapless dress": "Dress",
    
    # Tops variations
    "button-down shirt": "Tops", "button down": "Tops", "button up": "Tops",
    "off-the-shoulder top": "Tops", "off shoulder top": "Tops",
    "one-shoulder top": "Tops", "crop top": "Tops", "cropped top": "Tops",
    "tube top": "Tops", "wrap top": "Tops", "corset top": "Tops",
    "peplum top": "Tops", "halter top": "Tops", "shell top": "Tops", 
    "knit top": "Tops", "tank top": "Tops", "tank": "Tops",
    "t-shirt": "Tops", "tee": "Tops", "tee shirt": "Tops",
    "camisole": "Tops", "cami": "Tops", "blouse": "Tops",
    "polo shirt": "Tops", "polo": "Tops", "tunic": "Tops", 
    "sweater": "Tops", "cardigan": "Tops", "pullover": "Tops",
    "bodysuit": "Tops", "body suit": "Tops", "sweatshirt": "Tops",
    "hoodie": "Tops", "vest": "Tops", "bustier": "Tops",
    "bralette": "Tops", "top": "Tops", "shirt": "Tops",
    "long sleeve top": "Tops", "short sleeve top": "Tops",
    "sleeveless top": "Tops", "v-neck": "Tops", "crew neck": "Tops",
    
    # Jackets / Blazers variations
    "trench coat": "Jackets / Blazers", "trench": "Jackets / Blazers",
    "peacoat": "Jackets / Blazers", "pea coat": "Jackets / Blazers",
    "duster coat": "Jackets / Blazers", "duster": "Jackets / Blazers",
    "car coat": "Jackets / Blazers", "puffer jacket": "Jackets / Blazers",
    "puffer": "Jackets / Blazers", "quilted jacket": "Jackets / Blazers",
    "bomber jacket": "Jackets / Blazers", "bomber": "Jackets / Blazers",
    "leather jacket": "Jackets / Blazers", "denim jacket": "Jackets / Blazers",
    "jean jacket": "Jackets / Blazers", "moto jacket": "Jackets / Blazers",
    "motorcycle jacket": "Jackets / Blazers", "wool coat": "Jackets / Blazers",
    "fur coat": "Jackets / Blazers", "faux fur coat": "Jackets / Blazers",
    "suit jacket": "Jackets / Blazers", "blazer": "Jackets / Blazers",
    "overcoat": "Jackets / Blazers", "cape": "Jackets / Blazers",
    "poncho": "Jackets / Blazers", "raincoat": "Jackets / Blazers",
    "windbreaker": "Jackets / Blazers", "parka": "Jackets / Blazers",
    "jacket": "Jackets / Blazers", "coat": "Jackets / Blazers",
    "outerwear": "Jackets / Blazers", "winter coat": "Jackets / Blazers",
    "spring jacket": "Jackets / Blazers", "overshirt": "Jackets / Blazers",
    "shacket": "Jackets / Blazers", "shirt jacket": "Jackets / Blazers",
    
    # Pants variations
    "wide-leg pants": "Pants", "wide leg pants": "Pants",
    "straight-leg pants": "Pants", "straight leg pants": "Pants",
    "skinny pants": "Pants", "palazzo pants": "Pants",
    "harem pants": "Pants", "dress pants": "Pants",
    "cargo pants": "Pants", "cargo": "Pants",
    "bermuda shorts": "Pants", "denim shorts": "Pants",
    "jeans": "Pants", "denim": "Pants", "trousers": "Pants",
    "sweatpants": "Pants", "joggers": "Pants", "leggings": "Pants",
    "culottes": "Pants", "capris": "Pants", "capri pants": "Pants",
    "shorts": "Pants", "skort": "Pants", "trouser pant": "Pants",
    "trouser pants": "Pants", "trouser": "Pants", "pants": "Pants",
    "slacks": "Pants", "chinos": "Pants", "khakis": "Pants",
    "athletic pants": "Pants", "track pants": "Pants",
    
    # Skirts variations
    "mini skirt": "Skirts", "miniskirt": "Skirts",
    "midi skirt": "Skirts", "maxi skirt": "Skirts",
    "pencil skirt": "Skirts", "a-line skirt": "Skirts",
    "pleated skirt": "Skirts", "slip skirt": "Skirts",
    "wrap skirt": "Skirts", "circle skirt": "Skirts",
    "tiered skirt": "Skirts", "denim skirt": "Skirts",
    "leather skirt": "Skirts", "skirt": "Skirts",
    "long skirt": "Skirts", "short skirt": "Skirts",
    
    # Bags variations
    "shoulder bag": "Bags", "crossbody bag": "Bags", "cross body bag": "Bags",
    "messenger bag": "Bags", "satchel bag": "Bags", "satchel": "Bags",
    "hobo bag": "Bags", "bucket bag": "Bags", "saddle bag": "Bags",
    "bowler bag": "Bags", "doctor bag": "Bags", "frame bag": "Bags", 
    "box bag": "Bags", "top handle bag": "Bags", "top-handle": "Bags",
    "tote bag": "Bags", "shopping bag": "Bags", "beach bag": "Bags",
    "weekender bag": "Bags", "duffle bag": "Bags", "duffel bag": "Bags",
    "travel bag": "Bags", "clutch bag": "Bags", "envelope clutch": "Bags",
    "minaudiere": "Bags", "wristlet": "Bags", "evening bag": "Bags",
    "backpack": "Bags", "rucksack": "Bags", "drawstring bag": "Bags",
    "pouchette": "Bags", "pochette": "Bags", "pouch": "Bags",
    "makeup bag": "Bags", "cosmetic bag": "Bags", "coin purse": "Bags",
    "wallet": "Bags", "cardholder": "Bags", "card case": "Bags",
    "card holder": "Bags", "bag": "Bags", "purse": "Bags", 
    "handbag": "Bags", "clutch": "Bags", "tote": "Bags",
    
    # Heels variations
    "ankle-strap heels": "Heels", "ankle strap heels": "Heels",
    "slingback heels": "Heels", "peep-toe heels": "Heels",
    "peep toe heels": "Heels", "platform heels": "Heels",
    "t-strap heels": "Heels", "mary jane heels": "Heels",
    "d'orsay heels": "Heels", "dorsay heels": "Heels",
    "block heels": "Heels", "kitten heels": "Heels",
    "wedge heels": "Heels", "stilettos": "Heels", "stiletto": "Heels",
    "pumps": "Heels", "heels": "Heels", "high heels": "Heels",
    "heel": "Heels", "pump": "Heels",
    
    # Boots variations
    "over-the-knee boots": "Boots", "over the knee boots": "Boots",
    "otk boots": "Boots", "thigh-high boots": "Boots",
    "thigh high boots": "Boots", "knee-high boots": "Boots",
    "knee high boots": "Boots", "mid-calf boots": "Boots",
    "ankle boots": "Boots", "booties": "Boots", "bootie": "Boots",
    "chelsea boots": "Boots", "cowboy boots": "Boots",
    "western boots": "Boots", "combat boots": "Boots",
    "moto boots": "Boots", "motorcycle boots": "Boots",
    "sock boots": "Boots", "platform boots": "Boots",
    "wedge boots": "Boots", "rain boots": "Boots",
    "snow boots": "Boots", "hiking boots": "Boots", "boots": "Boots",
    "winter boots": "Boots", "boot": "Boots",
    
    # Flats variations
    "mary jane flats": "Flats", "mary janes": "Flats",
    "pointed-toe flats": "Flats", "pointed toe flats": "Flats",
    "oxford flats": "Flats", "oxfords": "Flats",
    "derby flats": "Flats", "espadrille flats": "Flats",
    "smoking slippers": "Flats", "ballet flats": "Flats",
    "loafers": "Flats", "moccasins": "Flats", "flats": "Flats",
    "slip-ons": "Flats", "slip ons": "Flats", "flat": "Flats",
    
    # Sandals variations
    "gladiator sandals": "Sandals", "strappy sandals": "Sandals",
    "t-strap sandals": "Sandals", "fisherman sandals": "Sandals",
    "espadrille sandals": "Sandals", "platform sandals": "Sandals",
    "wedge sandals": "Sandals", "flat sandals": "Sandals",
    "thong sandals": "Sandals", "flip-flops": "Sandals",
    "flip flops": "Sandals", "slides": "Sandals", "slide sandals": "Sandals",
    "sandals": "Sandals", "sandal": "Sandals",
    
    # Sneakers variations
    "high-top sneakers": "Sneakers", "high top sneakers": "Sneakers",
    "low-top sneakers": "Sneakers", "low top sneakers": "Sneakers",
    "platform sneakers": "Sneakers", "slip-on sneakers": "Sneakers",
    "slip on sneakers": "Sneakers", "dad sneakers": "Sneakers",
    "chunky sneakers": "Sneakers", "running sneakers": "Sneakers",
    "fashion sneakers": "Sneakers", "court sneakers": "Sneakers",
    "canvas sneakers": "Sneakers", "sneakers": "Sneakers",
    "trainers": "Sneakers", "tennis shoes": "Sneakers",
    "athletic shoes": "Sneakers", "sneaker": "Sneakers",
    "trainer": "Sneakers",
    
    # Mules variations
    "platform clogs": "Mules", "mule heels": "Mules",
    "mule flats": "Mules", "clogs": "Mules", "mules": "Mules",
    "shearling slippers": "Mules", "house slippers": "Mules",
    "slippers": "Mules", "mule": "Mules", "clog": "Mules",
    "slipper": "Mules",
    
    # Jewelry - Necklaces
    "statement necklace": "Necklace", "pendant necklace": "Necklace",
    "chain necklace": "Necklace", "choker necklace": "Necklace",
    "choker": "Necklace", "collar necklace": "Necklace",
    "collar": "Necklace", "bib necklace": "Necklace",
    "lariat necklace": "Necklace", "pearl necklace": "Necklace",
    "rope necklace": "Necklace", "necklace": "Necklace",
    "pendant": "Necklace", "chain": "Necklace",
    
    # Jewelry - Earrings
    "statement earrings": "Earrings", "drop earrings": "Earrings",
    "dangle earrings": "Earrings", "chandelier earrings": "Earrings",
    "hoop earrings": "Earrings", "hoops": "Earrings",
    "stud earrings": "Earrings", "studs": "Earrings",
    "clip-on earrings": "Earrings", "clip on earrings": "Earrings",
    "ear cuffs": "Earrings", "ear cuff": "Earrings",
    "earrings": "Earrings",
    
    # Jewelry - Bracelets
    "charm bracelet": "Bracelet", "bangle bracelet": "Bracelet",
    "bangle": "Bracelet", "cuff bracelet": "Bracelet",
    "cuff": "Bracelet", "chain bracelet": "Bracelet",
    "tennis bracelet": "Bracelet", "beaded bracelet": "Bracelet",
    "friendship bracelet": "Bracelet", "bracelet": "Bracelet",
    
    # Jewelry - Rings
    "statement ring": "Ring", "cocktail ring": "Ring",
    "signet ring": "Ring", "band ring": "Ring",
    "stackable ring": "Ring", "midi ring": "Ring",
    "knuckle ring": "Ring", "ring": "Ring",
    
    # Jewelry - Brooches/Pins
    "vintage brooch": "Brooch", "cameo brooch": "Brooch",
    "crystal brooch": "Brooch", "floral brooch": "Brooch",
    "animal brooch": "Brooch", "brooch": "Brooch",
    "enamel pin": "Brooch", "lapel pin": "Brooch",
    "hat pin": "Brooch", "pin": "Brooch",
    
    # Accessories - Belts
    "statement belt": "Belt", "chain belt": "Belt",
    "leather belt": "Belt", "wide belt": "Belt", 
    "skinny belt": "Belt", "obi belt": "Belt", 
    "corset belt": "Belt", "belt": "Belt",
    "waist belt": "Belt",

    # Accessories - Sunglasses
    "sunglasses": "Sunglasses", "Sunglasses": "Sunglasses", 
    "Sunglass": "Sunglasses", "Shades": "Sunglasses", 
    "Eyewear": "Sunglasses",
    
    # Accessories - Scarves
    "silk scarf": "Scarf", "cashmere scarf": "Scarf",
    "wool scarf": "Scarf", "pashmina": "Scarf", 
    "infinity scarf": "Scarf", "square scarf": "Scarf", 
    "oblong scarf": "Scarf", "scarf": "Scarf",
    "shawl": "Scarf", "wrap": "Scarf",
    
    # Accessories - Gloves
    "leather gloves": "Gloves", "driving gloves": "Gloves",
    "evening gloves": "Gloves", "opera gloves": "Gloves",
    "fingerless gloves": "Gloves", "gloves": "Gloves",
}

def extract_type(text: str) -> str | None:
    t = text.lower()
    print(f"[DEBUG] Searching for product type in: {t[:100]}...")
    
    # Sort by length (longest first) to match most specific types first
    for phrase in sorted(PRODUCT_TYPES.keys(), key=len, reverse=True):
        escaped = re.escape(phrase)
        # Replace escaped spaces with flexible whitespace matcher
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # Use word boundaries to prevent matching within words
        pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, t):
            print(f"[DEBUG] Found product type via phrase '{phrase}' -> {PRODUCT_TYPES[phrase]}")
            return PRODUCT_TYPES[phrase]
    
    print(f"[DEBUG] No product type found")
    return None

def extract_era(text: str) -> str | None:
    t = text.lower()
    # 1960s variations
    if any(x in t for x in ["1960s", "60s", "sixties", "'60s", "1960's", "60's",
                             "mod era", "youthquake", "space age", "vintage 60s", 
                             "twiggy", "mod style", "swinging sixties"]):
        return "1960s"
    # 1970s variations
    if any(x in t for x in ["1970s", "70s", "seventies", "'70s", "1970's", "70's",
                             "disco era", "boho era", "hippie era", "studio 54", 
                             "vintage 70s", "disco", "bohemian 70s"]):
        return "1970s"
    # 1980s variations
    if any(x in t for x in ["1980s", "80s", "eighties", "'80s", "1980's", "80's",
                             "power dressing", "shoulder pad era", "vintage 80s", 
                             "new wave", "power suit", "80s glam"]):
        return "1980s"
    # 1990s variations
    if any(x in t for x in ["1990s", "90s", "nineties", "'90s", "1990's", "90's",
                             "grunge", "minimalist era", "supermodel era", 
                             "vintage 90s", "90s minimalism"]):
        return "1990s"
    # 2000s variations
    if any(x in t for x in ["y2k", "2000s", "00s", "'00s", "early 2000s", "aughts",
                             "mcbling", "millennium fashion", "paris hilton era",
                             "2000's", "00's", "y2k aesthetic"]):
        return "2000s / Y2K"
    # 2010s variations
    if any(x in t for x in ["2010s", "10s", "'10s", "early 2010s", "2010's",
                             "normcore", "athleisure", "streetwear era"]):
        return "2010s"
    # Spring/Summer variations
    if any(x in t for x in ["spring/summer", "spring summer", "s/s", "ss", 
                             "resort", "cruise", "ss20", "ss21", "ss22", "ss23", "ss24"]):
        return "Spring/Summer"
    # Fall/Winter variations
    if any(x in t for x in ["fall/winter", "fall winter", "f/w", "fw", 
                             "autumn/winter", "aw", "fw20", "fw21", "fw22", "fw23", "fw24"]):
        return "Fall/Winter"
    return None

# ENHANCED MATERIALS with more variations
MATERIALS = [
    # Cotton variations
    "Organic cotton", "Pima cotton", "Supima cotton", "Egyptian cotton",
    "Cotton", "Cotton blend",
    
    # Linen variations
    "Flax", "Linen", "Hemp", "Linen blend",
    
    # Silk variations
    "Mulberry silk", "Charmeuse", "Chiffon", "Organza", "Crepe de chine",
    "Twill silk", "Silk", "Crushed velvet", "Silk velvet", "Velvet", 
    "Satin", "Silk satin", "Satin silk",
    
    # Rayon/Modal variations
    "Modal", "Lyocell", "Tencel", "Cupro", "Viscose", "Rayon", 
    "Bamboo", "Acetate", "Rayon blend",
    
    # Polyester variations
    "Recycled polyester", "Polyester", "Recycled nylon", "Nylon",
    "Spandex", "Elastane", "Lycra", "Acrylic", "Polyamide", 
    "Polyurethane", "Poly blend",
    
    # Leather variations
    "Vegan leather", "Faux leather", "PU leather", "Bonded leather",
    "Cowhide", "Sheepskin", "Lambskin", "Goatskin", "Pigskin",
    "Leather", "Suede", "Nubuck", "Patent leather", "Shearling",
    "Genuine leather", "Full grain leather", "Top grain leather",
    
    # Wool variations
    "Merino wool", "Cashmere", "Mongolian cashmere", "Alpaca",
    "Mohair", "Angora", "Camel hair", "Yak wool", "Wool", 
    "Tweed", "Bouclé", "Boucle", "Felted wool", "Virgin wool",
    "Wool blend",
    
    # Jersey/Knit variations
    "Cotton jersey", "Wool jersey", "Silk jersey", "Jersey",
    "Rib knit", "Chunky knit", "Cable knit", "Pointelle", "Knit",
    "Interlock", "Double knit",
    
    # Other fabrics
    "Sherpa", "Fleece", "French terry", "Terry cloth",
    "Neoprene", "Power mesh", "Mesh", "Tulle", 
    "Guipure lace", "Embroidered lace", "Lace",
    "Broderie anglaise", "Eyelet", "Brocade", "Jacquard",
    
    # Denim variations
    "Raw denim", "Stretch denim", "Denim", "Corduroy", 
    "Canvas", "Poplin", "Twill", "Gabardine",
    
    # Other materials
    "Crepe", "Georgette", "Scuba", "Sequins", "Beaded", 
    "Embellished", "Metallic fabric", "Lamé", "Lame", "Foil fabric",
    
    # Synthetic variations
    "Leatherette", "Rubber", "PVC", "Vinyl", "Plastic",
    
    # Natural materials
    "Raffia", "Jute", "Straw", "Wicker", "Patent synthetic", 
    "Microfiber",
    
    # Technical fabrics
    "Gore-Tex", "Softshell", "Down", "Feathers", "Down fill",
    
    # Fur variations
    "Fox fur", "Mink fur", "Rabbit fur", "Raccoon fur", "Faux fur",
    "Fur trim", "Faux fur trim",
]

def extract_materials(text: str) -> list[str]:
    t = text.lower()
    found: list[str] = []
    
    # Sort by length (longest first) to match compound materials before simple ones
    for m in sorted(MATERIALS, key=len, reverse=True):
        m_lower = m.lower()
        escaped = re.escape(m_lower)
        # Replace escaped spaces with flexible whitespace
        escaped = escaped.replace(r'\ ', r'\s+')
        
        # Use word boundaries to prevent matching within words
        pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, t) and m not in found:
            found.append(m)
    
    return found

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
        metafields.append({
            "namespace": "custom",
            "key": key,
            "type": type_,
            "value": str(value),
        })

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhooks/products")
async def handle_product_webhook(request: Request):
    raw_body = await request.body()
    hmac_header = request.headers.get("x-shopify-hmac-sha256")
    
    if not hmac_header or not verify_shopify_hmac(raw_body, hmac_header):
        print("HMAC verification failed!")
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    product_id = data.get("id")
    title = data.get("title") or ""
    body_html = data.get("body_html") or ""

    body_text = re.sub(r"<[^>]+>", " ", body_html)
    text = f"{title}\n{body_text}"

    metafields_payload = build_metafields_payload(product_id, text)
    await write_metafields_to_shopify(
        product_id=metafields_payload["product_id"],
        metafields=metafields_payload["metafields"],
    )

    return {"status": "processed"}
