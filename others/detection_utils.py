# detection_utils.py
import os, re, boto3

# ---------- AWS CONFIG ----------
aws_access_key_id = 'AKIA2QPBPUSJM7EIEEGR'
aws_secret_access_key = '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'
aws_default_region = "us-east-1"
bucket_name = "ttb-bucket"

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_default_region
)

rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_default_region
)

# ---------- DETECTION METHODS ----------

def detect_brand_name(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    resp = rekognition.detect_text(Image={"Bytes": data})
    lines = [t for t in resp["TextDetections"] if t["Type"] == "LINE" and t["Confidence"] > 80]
    if not lines:
        return "Not found"
    scored = [{"text": t["DetectedText"], "score": t["Geometry"]["BoundingBox"]["Height"] * t["Geometry"]["BoundingBox"]["Width"]} for t in lines]
    brand = max(scored, key=lambda x: x["score"])["text"].strip()
    return brand


def detect_product_class(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    resp = rekognition.detect_text(Image={"Bytes": data})
    text = " ".join([t["DetectedText"].lower() for t in resp["TextDetections"] if t["Type"] == "LINE"])

    beer = {"beer", "lager", "ale", "ipa", "stout", "pilsner"}
    wine = {"wine", "vineyard", "cabernet", "chardonnay", "merlot", "pinot", "sauvignon"}
    spirit = {"vodka", "rum", "whiskey", "bourbon", "gin", "tequila", "brandy"}

    counts = {"Beer": sum(k in text for k in beer), "Wine": sum(k in text for k in wine), "Distilled Spirit": sum(k in text for k in spirit)}
    product_class = max(counts, key=counts.get)
    return product_class if counts[product_class] else "Unknown"


def detect_manufacturer_name(image_path):
    with open(image_path, "rb") as f:
        img = f.read()
    resp = rekognition.detect_text(Image={"Bytes": img})
    lines = [t["DetectedText"] for t in resp["TextDetections"] if t["Type"] == "LINE"]
    full_text = " ".join(lines).upper()

    addr_pattern = r"\b([A-Z][A-Z\s]+,\s*[A-Z]{2})\b"
    addr_match = re.search(addr_pattern, full_text)
    address = addr_match.group(1).title() if addr_match else "Not found"

    manuf = next((l for l in lines if "DISTILL" in l.upper() or "BREW" in l.upper() or "BOTTL" in l.upper()), "Not found")
    manuf = re.sub(r"^(DISTILLED AND BOTTLED BY|DISTILLED BY|BOTTLED BY)[:\- ]*", "", manuf, flags=re.IGNORECASE).strip()

    manuf = manuf.strip(" ,;:-") if manuf else ""
    address = address.strip(" ,;:-") if address else ""
    if manuf and address:
        return f"{manuf}, {address}"
    return manuf or address or "Not found"


def detect_health_warning(image_path):
    with open(image_path, "rb") as f:
        img = f.read()
    resp = rekognition.detect_text(Image={"Bytes": img})
    lines = [t["DetectedText"] for t in resp["TextDetections"] if t["Type"] == "LINE"]
    if not any("warning" in l.lower() for l in lines):
        return "MISSING HEALTH WARNING STATEMENT"
    if any("GOVERNMENT WARNING" in l for l in lines):
        return "GOVERNMENT WARNING"
    return "not in all cap"


def detect_country_of_origin(image_path):
    with open(image_path, "rb") as f:
        data = f.read()
    resp = rekognition.detect_text(Image={"Bytes": data})
    all_text = " ".join([t["DetectedText"].upper() for t in resp["TextDetections"]])

    us_states = {"MD","CA","TX","NY","FL","IL","WA","VA","OH","PA","NJ","NC"}  # shortened for brevity
    if any(f", {s}" in all_text or f" {s} " in all_text for s in us_states):
        return "USA"

    match = re.search(r"(IMPORTED FROM|PRODUCT OF|MADE IN)\s+([A-Z\s]+)", all_text)
    return match.group(2).strip().title() if match else "USA"


def extract_text_from_image(uploaded_file):
    """Extract all fields into a dictionary."""
    from app import app
    local_path = os.path.join(app.config["UPLOAD_FOLDER"], uploaded_file.filename)
    uploaded_file.save(local_path)
    s3.upload_file(local_path, bucket_name, uploaded_file.filename)

    with open(local_path, "rb") as f:
        data = f.read()
    resp = rekognition.detect_text(Image={"Bytes": data})
    text = " ".join([t["DetectedText"] for t in resp["TextDetections"] if t["Type"] == "LINE"])

    alcohol_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    volume_match = re.search(r"(\d+(?:\.\d+)?\s*(?:mL|ML|Fl\s*Oz|FL\s*OZ))", text)

    return {
        "extracted_brand": detect_brand_name(local_path),
        "extracted_class": detect_product_class(local_path),
        "extracted_manufacturer": detect_manufacturer_name(local_path),
        "extracted_alcohol": alcohol_match.group(0) if alcohol_match else "Not found",
        "extracted_volume": volume_match.group(0) if volume_match else "Not found",
        "extracted_health_warning": detect_health_warning(local_path),
        "extracted_country": detect_country_of_origin(local_path),
    }


def compare_entries(user_data, extracted_data):
    """Compare extracted and user-provided entries."""
    comparison = {}

    def normalize(t):
        return re.sub(r'[\s,]+', ' ', t.strip().lower()) if isinstance(t, str) else str(t)

    fields = {
        "Brand Match": (user_data["Brand Name"], extracted_data["extracted_brand"]),
        "Product Class Match": (user_data["Product Class/Type"], extracted_data["extracted_class"]),
        "Alcohol Match": (user_data["Alcohol Content (User)"], extracted_data["extracted_alcohol"]),
        "Net Contents Match": (user_data["Net Contents (User)"], extracted_data["extracted_volume"]),
        "Manufacturer/Bottler Match": (user_data["Manufacturer/Bottler"], extracted_data["extracted_manufacturer"]),
        "Health Warning Match": (user_data["Health Warning"], extracted_data["extracted_health_warning"]),
        "Country of Origin Match": (user_data["Country of Origin"], extracted_data["extracted_country"]),
    }

    matches = 0
    for field, (u, e) in fields.items():
        u_norm, e_norm = normalize(u), normalize(e)
        if field == "Manufacturer/Bottler Match":
            ok = u_norm in e_norm or e_norm in u_norm
        elif field == "Health Warning Match":
            ok = (u.strip() == e.strip()) and u.isupper()
        else:
            ok = u_norm == e_norm
        comparison[field] = "Matched" if ok else "Unmatched"
        matches += ok

    total = len(fields)
    comparison["Overall Match Score"] = f"{matches}/{total}"
    comparison["Match Percentage"] = int(matches / total * 100)
    return comparison

