from flask import Flask, request, render_template_string
import threading, webbrowser, os
from detection_utils import extract_text_from_image, compare_entries

app = Flask(__name__)
UPLOAD_FOLDER = "/home/sena/Labeling/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


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


@app.route("/", methods=["GET"])
def index():
    return render_template_string("<h2>Beverage Label Checker</h2><p>Upload form goes here...</p>")


@app.route("/process", methods=["POST"])
def process():
    user_data = get_user_input(request)
    uploaded_file = request.files.get("label_image")
    extracted_data = extract_text_from_image(uploaded_file)
    comparison = compare_entries(user_data, extracted_data)
    return comparison  # Simplify JSON return for now


def open_browser(port):
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    port = 5000
    threading.Timer(1.0, open_browser, args=(port,)).start()
    app.run(host="0.0.0.0", port=port)

