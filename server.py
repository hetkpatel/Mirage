# app.py
import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

# Load .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Authentication setup
auth = HTTPBasicAuth()
users = {"hetpatel": generate_password_hash(os.getenv("PASSWORD"))}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username


# Encryption setup
if not os.path.isfile("./key.pem"):
    key = Fernet.generate_key()
    with open("./key.pem", "wb") as f:
        f.write(key)
else:
    with open("./key.pem", "rb") as f:
        key = f.read()
cipher_suite = Fernet(key)

# External SSD path
app.config["UPLOAD_FOLDER"] = os.getenv("DRIVE_LOCATION")


# Route to upload files
@app.route("/upload", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400
    if file:
        encrypted_data = cipher_suite.encrypt(file.read())
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        with open(file_path, "wb") as f:
            f.write(encrypted_data)
        return "File successfully uploaded", 200


# Route to download files
@app.route("/download/<filename>", methods=["GET"])
@auth.login_required
def download_file(filename):
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        return (
            decrypted_data,
            200,
            {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
    else:
        return abort(404)


# Run app with HTTPS
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
