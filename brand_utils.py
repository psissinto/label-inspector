import boto3
import re
import os

# ---------- Configuration ----------
aws_access_key_id = 'AKIA2QPBPUSJM7EIEEGR'
aws_secret_access_key = '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'
aws_default_region = 'us-east-1'
bucket_name = "ttb-bucket"

# ---------- AWS Configuration ----------
rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_default_region
)

# ---------- Helper Functions ----------
def center_x(b): return b["Left"] + b["Width"]/2
def center_y(b): return b["Top"] + b["Height"]/2
def bottom_y(b): return b["Top"] + b["Height"]

STOP_WORDS = {"with", "and", "of", "by", "for", "from"}

def clean_text(t):
    return re.sub(r"[^A-Za-z0-9' ]+", "", t).strip()

def is_generic(text):
    GENERIC = {
        "beer","lager","ale","vodka","wine","whiskey","proof","alcohol","ml",
        "litre","distilled","bottled","brewery","warning","government","contains",
        "place","brand","store","cool","dry","imported","amsterdam","paris",
        "london","company","medaille","prize","original","gravity","volume"
    }
    words = text.lower().split()
    return sum(w in GENERIC for w in words) >= len(words)/2


# ---------- Brand Detection Function ----------
def detect_brand_name(image_path):
    with open(image_path, "rb") as f:
        data = f.read()

    resp = rekognition.detect_text(Image={"Bytes": data})
    lines = [t for t in resp["TextDetections"] if t["Type"] == "LINE" and t["Confidence"] > 80]
    if not lines:
        print("❌ No text found.")
        return None

    scored = []
    for l in lines:
        b = l["Geometry"]["BoundingBox"]
        score = b["Width"] * b["Height"] * l["Confidence"]
        text = clean_text(l["DetectedText"])
        if 2 <= len(text) <= 60 and not is_generic(text):
            scored.append({"text": text, "box": b, "score": score})
    if not scored:
        print("⚠️ Nothing usable.")
        return None

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[0]
    brand = top["text"]
    b0 = top["box"]
    h0 = b0["Height"]
    bottom0 = bottom_y(b0)

    # Merge similarly sized and aligned lines
    for s in scored[1:]:
        b = s["box"]
        if b["Height"] >= 0.9 * h0 and abs(center_x(b) - center_x(b0)) < 0.22:
            if bottom_y(b) <= 1.18 * bottom0:
                lower_text = s["text"].strip()
                if lower_text and lower_text.split()[0].lower() not in STOP_WORDS:
                    if not (len(lower_text) <= 4 and lower_text.isupper()):
                        brand += " " + lower_text

    # print(f"🏷️ Detected Brand Name: {brand}")
    return brand

# -----------------Product Class/Type ---------------
def detect_product_class(image_path):
    """
    Detect the product class (Beer, Wine, or Distilled Spirit)
    using text from AWS Rekognition OCR.
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    resp = rekognition.detect_text(Image={"Bytes": image_bytes})
    text_detections = resp.get("TextDetections", [])
    all_text = " ".join([t["DetectedText"].lower() for t in text_detections if t["Type"] == "LINE"])

    # --- Keyword sets ---
    beer_keywords = {"beer", "lager", "ale", "ipa", "stout", "pilsner"}
    wine_keywords = {"wine", "vineyard", "cabernet", "chardonnay", "merlot", "pinot", "sauvignon"}
    spirit_keywords = {"vodka", "rum", "whiskey", "bourbon", "gin", "tequila", "brandy"}

    # --- Count keyword occurrences ---
    beer_score = sum(k in all_text for k in beer_keywords)
    wine_score = sum(k in all_text for k in wine_keywords)
    spirit_score = sum(k in all_text for k in spirit_keywords)

    # --- Decision logic ---
    if max(beer_score, wine_score, spirit_score) == 0:
        product_class = "Unknown"
    elif beer_score >= wine_score and beer_score >= spirit_score:
        product_class = "Beer"
    elif wine_score >= beer_score and wine_score >= spirit_score:
        product_class = "Wine"
    else:
        product_class = "Distilled Spirit"

    print(f"🍾 Detected Product Class: {product_class}")
    return product_class

