from flask import Flask, request, render_template
import os, threading, webbrowser
from modules import (
    extract_text_from_image,
    compare_entries,
    get_user_input,
)
import boto3

app = Flask(__name__)

# ---------- Configuration ----------
UPLOAD_FOLDER = "/home/sena/Labeling/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------- AWS ----------
aws_access_key_id = "AKIA2QPBPUSJM7EIEEGR"
aws_secret_access_key = "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"
aws_default_region = "us-east-1"
bucket_name = "ttb-bucket"

# AWS clients
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

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        result=False,
        user_data={
            "Brand Name": "",
            "Product Class/Type": "",
            "Alcohol Content (User)": "",
            "Net Contents (User)": "",
            "Manufacturer/Bottler": "",
            "Health Warning": "",
            "Country of Origin": "",
        },
        comparison={},
        extracted_brand="",
        extracted_class="",
        extracted_alcohol="",
        extracted_volume="",
        extracted_manufacturer="",
        extracted_health_warning="",
        extracted_country="",
        match_percentage=0,
    )


@app.route("/process", methods=["POST"])
def process():
    user_data = get_user_input(request)
    uploaded_file = request.files.get("label_image")

    extracted_data = extract_text_from_image(uploaded_file)
    comparison = compare_entries(user_data, extracted_data)
    match_percentage = comparison.get("Match Percentage", 0)

    return render_template(
        "index.html",
        result=True,
        user_data=user_data,
        comparison=comparison,
        extracted_brand=extracted_data["extracted_brand"],
        extracted_class=extracted_data["extracted_class"],
        extracted_alcohol=extracted_data["extracted_alcohol"],
        extracted_volume=extracted_data["extracted_volume"],
        extracted_manufacturer=extracted_data["extracted_manufacturer"],
        extracted_health_warning=extracted_data["extracted_health_warning"],
        extracted_country=extracted_data["extracted_country"],
        match_percentage=match_percentage,
    )


# ---------- Auto-launch ----------
def open_browser(port):
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

    # port = 5000
    # threading.Timer(0.5, open_browser, args=(port,)).start()
    # app.run(host="127.0.0.1", port=port, debug=False)

