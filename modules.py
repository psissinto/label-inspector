import os, re, boto3
from brand_utils import detect_brand_name

aws_access_key_id = "AKIA2QPBPUSJM7EIEEGR"
aws_secret_access_key = "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"
aws_default_region = "us-east-1"
bucket_name = "ttb-bucket"

s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_default_region,
)
rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_default_region,
)

# ---------------- Utility Methods ----------------
def get_user_input(req):
    return {
        "Brand Name": req.form.get("brand_name", ""),
        "Product Class/Type": req.form.get("product_class", ""),
        "Alcohol Content (User)": req.form.get("alcohol_content", ""),
        "Net Contents (User)": req.form.get("net_contents", ""),
        "Manufacturer/Bottler": req.form.get("manufacturer", ""),
        "Health Warning": req.form.get("health_warning", ""),
        "Country of Origin": req.form.get("country", ""),
    }


def detect_product_class(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    resp = rekognition.detect_text(Image={"Bytes": image_bytes})
    text_detections = resp.get("TextDetections", [])
    all_text = " ".join(
        [t["DetectedText"].lower() for t in text_detections if t["Type"] == "LINE"]
    )

    beer_keywords = {"beer", "lager", "ale", "ipa", "stout", "pilsner"}
    wine_keywords = {"wine", "vineyard", "cabernet", "chardonnay", "merlot", "pinot"}
    spirit_keywords = {"vodka", "rum", "whiskey", "bourbon", "gin", "tequila", "brandy"}

    beer_score = sum(k in all_text for k in beer_keywords)
    wine_score = sum(k in all_text for k in wine_keywords)
    spirit_score = sum(k in all_text for k in spirit_keywords)

    if max(beer_score, wine_score, spirit_score) == 0:
        return "Unknown"
    elif beer_score >= wine_score and beer_score >= spirit_score:
        return "Beer"
    elif wine_score >= beer_score and wine_score >= spirit_score:
        return "Wine"
    return "Distilled Spirit"


def detect_manufacturer_name(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    resp = rekognition.detect_text(Image={"Bytes": image_bytes})
    text_detections = resp.get("TextDetections", [])
    lines = [
        {"text": t["DetectedText"].strip(), "y": t["Geometry"]["BoundingBox"]["Top"]}
        for t in text_detections
        if t["Type"] == "LINE"
    ]

    if not lines:
        return "Not found, Not found"
    lines.sort(key=lambda x: x["y"])
    full_text = " ".join([l["text"].upper() for l in lines])

    manufacturer_keywords = [
        "DISTILLERY",
        "DISTILLED",
        "BOTTLED",
        "BREWERY",
        "WINERY",
        "IMPORT",
        "INC",
        "LTD",
    ]

    manufacturer_line = next(
        (l["text"] for l in lines if any(k in l["text"].upper() for k in manufacturer_keywords)),
        None,
    )

    address_pattern = r"\b([A-Z][A-Z\s]+,\s*[A-Z]{2})\b"
    address_match = re.search(address_pattern, full_text)
    address = address_match.group(1).title() if address_match else "Not found"
    manufacturer = manufacturer_line.title() if manufacturer_line else "Not found"
    return f"{manufacturer}, {address}"


def detect_health_warning(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    resp = rekognition.detect_text(Image={"Bytes": image_bytes})
    text_detections = [t["DetectedText"].strip() for t in resp["TextDetections"] if t["Type"] == "LINE"]

    if any("GOVERNMENT WARNING" in t for t in text_detections):
        return "GOVERNMENT WARNING"
    elif any("warning" in t.lower() for t in text_detections):
        return "not in all cap"
    return "MISSING HEALTH WARNING STATEMENT"


def detect_country_of_origin(image_path):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    resp = rekognition.detect_text(Image={"Bytes": image_bytes})
    all_text = " ".join([t["DetectedText"].upper() for t in resp["TextDetections"]])
    us_states = {"CA", "TX", "NY", "MD", "FL", "WA", "IL"}
    if any(f", {st}" in all_text for st in us_states):
        return "USA"
    m = re.search(r"(?:IMPORTED FROM|PRODUCT OF|MADE IN)\s+([A-Z][A-Z\s]+)", all_text)
    return m.group(1).title() if m else "USA"


def extract_text_from_image(uploaded_file):
    local_path = os.path.join("/home/sena/Labeling/uploads", uploaded_file.filename)
    uploaded_file.save(local_path)
    s3.upload_file(local_path, bucket_name, uploaded_file.filename)
    s3_url = f"https://{bucket_name}.s3.amazonaws.com/{uploaded_file.filename}"

    with open(local_path, "rb") as f:
        image_bytes = f.read()
    response = rekognition.detect_text(Image={"Bytes": image_bytes})
    all_text = " ".join([t["DetectedText"] for t in response["TextDetections"]])

    extracted_data = {
        "ocr_text": all_text,
        "s3_url": s3_url,
        "extracted_brand": detect_brand_name(local_path),
        "extracted_class": detect_product_class(local_path),
        "extracted_alcohol": re.search(r"(\d+(?:\.\d+)?)\s*%", all_text).group(0)
        if "%" in all_text
        else "Not found",
        "extracted_volume": re.search(r"(\d+(?:\.\d+)?\s*(?:ml|fl\s*oz))", all_text, re.I).group(0)
        if "ml" in all_text.lower() or "oz" in all_text.lower()
        else "Not found",
        "extracted_manufacturer": detect_manufacturer_name(local_path),
        "extracted_health_warning": detect_health_warning(local_path),
        "extracted_country": detect_country_of_origin(local_path),
    }
    return extracted_data


def compare_entries(user_data, extracted_data):
    comparison = {}
    matches = 0

    def normalize(txt):
        return re.sub(r"[\s,]+", " ", txt.strip().lower()) if isinstance(txt, str) else str(txt)

    fields = {
        "Brand Match": (user_data["Brand Name"], extracted_data["extracted_brand"]),
        "Product Class Match": (user_data["Product Class/Type"], extracted_data["extracted_class"]),
        "Alcohol Match": (user_data["Alcohol Content (User)"], extracted_data["extracted_alcohol"]),
        "Net Contents Match": (user_data["Net Contents (User)"], extracted_data["extracted_volume"]),
        "Manufacturer/Bottler Match": (user_data["Manufacturer/Bottler"], extracted_data["extracted_manufacturer"]),
        "Health Warning Match": (user_data["Health Warning"], extracted_data["extracted_health_warning"]),
        "Country of Origin Match": (user_data["Country of Origin"], extracted_data["extracted_country"]),
    }

    for field, (u, e) in fields.items():
        ok = False
        u_norm, e_norm = normalize(u), normalize(e)
        if field == "Health Warning Match":
            ok = (u.strip() == e.strip() == "GOVERNMENT WARNING")
        elif field == "Manufacturer/Bottler Match":
            ok = u_norm in e_norm or e_norm in u_norm
        else:
            ok = u_norm == e_norm

        comparison[field] = "Matched" if ok else "Unmatched"
        if ok:
            matches += 1

    total = len(fields)
    comparison["Overall Match Score"] = f"{matches}/{total}"
    comparison["Match Percentage"] = int((matches / total) * 100)
    return comparison

