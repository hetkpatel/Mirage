import io
import os
import shutil
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import uuid
import json
from flask import Flask, request, abort, url_for, jsonify
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mimetypes
from PIL import Image
from pillow_heif import register_heif_opener
import ffmpeg
import threading

# Load .env file
load_dotenv()

# Configure logging
# Create a rotating file handler
file_handler = RotatingFileHandler(
    os.path.join("./logs", "mirage.log"),
    maxBytes=10**6,
    backupCount=5,
)  # 1MB per file, 5 backups
file_handler.setLevel(logging.DEBUG)

# Define a log format
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s :: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

# Get the root logger and set the overall level
logger = logging.getLogger("Mirage")
logger.setLevel(logging.DEBUG)  # This controls the overall logging level

# Add handlers to the root logger
logger.addHandler(file_handler)

# Register HEIF opener
register_heif_opener()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Status for processing
pending = 1
total = 1
current_file_in_process = ""

# Authentication setup
auth = HTTPBasicAuth()
users = {"hetpatel": generate_password_hash(os.getenv("PASSWORD"))}


# Authentication verification
@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        logger.info(f"User {username} authenticated successfully.")
        return username
    logger.warning(f"Authentication failed for user {username}.")
    return None


app.config["DRIVE_LOCATION"] = "/app/DRIVE"
os.makedirs(os.path.join(app.config["DRIVE_LOCATION"], "uploads"), exist_ok=True)
os.makedirs(os.path.join(app.config["DRIVE_LOCATION"], "media", "media"), exist_ok=True)

# Encryption setup
# if not os.path.isfile("./key.pem"):
#     key = Fernet.generate_key()
#     with open("./key.pem", "wb") as f:
#         f.write(key)
# else:
#     with open("./key.pem", "rb") as f:
#         key = f.read()
# cipher_suite = Fernet(key)

# JSON file path for storing filename mappings and metadata
MAPPING_FILE = os.path.join(
    app.config["DRIVE_LOCATION"], "media", "filename_mapping.json"
)
if not os.path.isfile(MAPPING_FILE):
    with open(MAPPING_FILE, "w") as f:
        json.dump({}, f)
    logger.info("Created new filename_mapping.json file.")


# Save mappings to the JSON file
def save_dictionary(json_file, dictionary):
    with open(json_file, "w") as f:
        json.dump(dictionary, f)


# Initialize the dictionaries
with open(MAPPING_FILE, "r") as f:
    filename_mapping = json.load(f)
logger.info("Loaded filename mappings from JSON file.")

# Import photo and video processing tools
from tools.embedder import *
from tools.extract_metadata import *
from tools.find_similar import *


# Route to check if the server is running
@app.route("/")
def index():
    logger.info("Health check - Server is running.")
    return "Server is running!", 200


# Route to upload files
@app.route("/upload", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        logger.warning("No file part in the request.")
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        logger.warning("No file selected for upload.")
        return "No selected file", 400
    if file:
        original_filename = secure_filename(file.filename)
        uid = uuid.uuid4().hex
        unique_filename = f'{uid}.{original_filename.split(".")[-1]}'
        # encrypted_data = cipher_suite.encrypt(file.read())
        file_path = os.path.join(
            app.config["DRIVE_LOCATION"], "uploads", unique_filename
        )

        # Save the file
        with open(file_path, "wb") as f:
            f.write(file.read())
        logger.info(
            f"File {original_filename} uploaded and saved as {unique_filename}."
        )

        # Update the mapping and save it to the JSON file
        filename_mapping[unique_filename] = original_filename
        save_dictionary(MAPPING_FILE, filename_mapping)
        logger.info(f"Filename mapping for {unique_filename} saved.")

        return {
            "status": "Resource uploaded",
            "url": url_for("download_file", unique_id=uid, _external=True),
        }, 201


# Route to process media files
def process_media(pull_uploads: bool):
    global pending, total, current_file_in_process
    logger.info("Started processing media.")

    if pull_uploads:
        files = [
            os.path.join(app.config["DRIVE_LOCATION"], "uploads", f)
            for f in os.listdir(os.path.join(app.config["DRIVE_LOCATION"], "uploads"))
        ]
        pending = 0
        total = len(files)
        logger.info(f"Found {total} files to process.")

        for f in files:
            current_file_in_process = os.path.basename(f)
            logger.info(f"Processing file {current_file_in_process}.")
            # Create embedding
            create_vector(f, os.path.join(app.config["DRIVE_LOCATION"], "media", "VE"))
            # TODO: Extract metadata and save to json
            # Move file to media folder
            shutil.move(f, os.path.join(app.config["DRIVE_LOCATION"], "media", "media"))
            pending += 1
            logger.info(
                f"File {current_file_in_process} processed and moved to media folder."
            )

    current_file_in_process = "SIMILAR"
    pending = 9
    total = 10
    logger.info("Finding similar photos and videos.")
    find_similar(
        vector_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "VE"),
        filename_mapping_json=filename_mapping,
        media_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "media"),
        output=os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json"),
    )
    logger.info("Similar photos and videos process completed.")
    current_file_in_process = ""
    pending = 1
    total = 1

    # Create copy of 'media' folder stored elsewhere
    shutil.make_archive(
        "./backup/Mirage-Backup",
        "zip",
        os.path.join(app.config["DRIVE_LOCATION"], "media"),
    )
    logger.info("Created backup archive of the media folder.")


# Route to start importing, tagging, and categorizing files
@app.route("/start", methods=["POST"])
@auth.login_required
def start_process():
    pull_uploads = request.args.get("pulluploads", "false").lower() == "true"
    logger.info(f"Received request to start process. pull_uploads={pull_uploads}")

    thread = threading.Thread(target=process_media, args=(pull_uploads,))
    thread.start()
    logger.info("Background processing thread started.")

    return {
        "status": url_for("process_status", _external=True),
    }, 202


# Route to get the status of the processing
@app.route("/status", methods=["GET"])
@auth.login_required
def process_status():
    global pending, total
    progress = ((pending / total) if total != 0 else 1) * 100
    logger.info(f"Processing status requested. Progress: {progress}%")

    return jsonify(
        {
            "progress": progress,
            "current": (
                "Finding similar photos and videos"
                if current_file_in_process == "SIMILAR"
                else filename_mapping.get(current_file_in_process)
            ),
        }
    ), (425 if progress < 100 else 200)


# Generate a thumbnail for an image file
def generate_image_thumbnail(file_bytes) -> bytes:
    with Image.open(io.BytesIO(file_bytes)) as img:
        img.thumbnail((640, 640))
        img.convert("RGB")
        img_io = io.BytesIO()
        img.save(img_io, format="JPEG")
        img_io.seek(0)
    logger.info("Generated image thumbnail.")
    return img_io.getvalue()


# Extract a thumbnail from a video file and return it as bytes
def generate_video_thumbnail(video_path: str) -> bytes:
    try:
        out, _ = (
            ffmpeg.input(video_path, ss=0.1)
            .output("pipe:", vframes=1, format="image2", vcodec="png")
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info("Generated video thumbnail.")
    except ffmpeg.Error as e:
        logger.error(f"Error generating video thumbnail: {e.stderr}")
        return abort(500)

    return generate_image_thumbnail(out)


# Route to download or get thumbnail of image or video
@app.route("/download/<unique_id>", methods=["GET"])
# TODO: @auth.login_required
def download_file(unique_id):
    logger.info(f"Download request for file with unique_id: {unique_id}")

    if len(unique_id) != 32:
        logger.warning("Invalid media ID received.")
        return {"status": "Invalid media ID"}, 400

    thumbnail = request.args.get("thumbnail", "false").lower() == "true"
    downloadable = request.args.get("downloadable", "false").lower() == "true"

    for file_path in os.listdir(
        os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    ):
        if file_path.startswith(unique_id):
            if os.path.exists(
                os.path.join(app.config["DRIVE_LOCATION"], "media", "media", file_path)
            ):
                original_filename = filename_mapping.get(file_path)
                if not original_filename:
                    logger.error(f"Original filename not found for file: {file_path}")
                    return abort(404)

                file_path = os.path.join(
                    app.config["DRIVE_LOCATION"], "media", "media", file_path
                )
                content_type = (
                    mimetypes.guess_type(original_filename, strict=True)[0]
                    or "application/octet-stream"
                )

                with open(file_path, "rb") as f:
                    file_data = f.read()

                    if thumbnail:
                        if content_type.startswith("image/"):
                            logger.info("Generating thumbnail for image file.")
                            file_data = generate_image_thumbnail(file_data)
                            content_type = "image/jpeg"
                        elif content_type.startswith("video/"):
                            logger.info("Generating thumbnail for video file.")
                            file_data = generate_video_thumbnail(file_path)
                            content_type = "image/jpeg"
                        else:
                            logger.warning(
                                f"Unsupported content type for thumbnail: {content_type}"
                            )
                            return abort(415)
                    elif not downloadable:
                        logger.info("Serving JPEG version of full res file")
                        if content_type.startswith("image/"):
                            with Image.open(io.BytesIO(file_data)) as img:
                                img.convert("RGB")
                                img_io = io.BytesIO()
                                img.save(img_io, format="JPEG")
                                img_io.seek(0)
                            file_data = img_io.getvalue()
                            content_type = "image/jpeg"
                        elif content_type.startswith("video/"):
                            pass
                        else:
                            logger.warning(f"Unsupported content type: {content_type}")
                            return abort(415)

                logger.info(f"File {original_filename} served for download.")
                return (
                    file_data,
                    200,
                    {
                        "Content-Type": content_type,
                        "Content-Disposition": f"attachment; filename={os.path.basename(original_filename)}",
                    },
                )
            else:
                logger.error(f"File not found: {file_path}")
                return abort(404)


# Route to delete files
@app.route("/delete/<unique_id>", methods=["DELETE"])
@auth.login_required
def delete_file(unique_id):
    logger.info(f"Delete request for file with unique_id: {unique_id}")

    if len(unique_id) != 32:
        logger.warning("Invalid media ID received.")
        return {"status": "Invalid media ID"}, 400

    for file_path in os.listdir(
        os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    ):
        if file_path.startswith(unique_id):
            file_path = os.path.join(
                app.config["DRIVE_LOCATION"], "media", "media", file_path
            )

            os.remove(file_path)
            filename_mapping.pop(os.path.basename(file_path), None)
            save_dictionary(MAPPING_FILE, filename_mapping)
            os.remove(
                os.path.join(
                    app.config["DRIVE_LOCATION"], "media", "VE", unique_id + ".pt"
                )
            )

            logger.info(f"File {file_path} and its associated data deleted.")
            return {"status": "Resource deleted"}, 202

    logger.info("Resource not found. No action taken.")
    return {"status": "Resource not found. No action taken."}, 204


# Route to list files and folders with metadata
@app.route("/list", methods=["GET"])
@auth.login_required
def list_files():
    logger.info("List request received.")

    items = []
    dir_path = os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    for item in os.listdir(dir_path):
        item_info = {
            "id": item,
            "name": filename_mapping.get(item),
            "url": url_for(
                "download_file", unique_id=item.split(".")[0], _external=True
            ),
            "mime_type": mimetypes.guess_type(filename_mapping.get(item))[0],
        }
        items.append(item_info)

    logger.info(f"{len(items)} items listed.")
    return jsonify(items), 200


# Route get similar.json file
@app.route("/similar", methods=["GET"])
@auth.login_required
def get_similar_json():
    try:
        with open(
            os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json")
        ) as f:
            logger.info("Returning similar.json file.")
            return jsonify(json.load(f)), 200
    except FileNotFoundError:
        logger.error("similar.json file not found.")
        return {"status": "File not found"}, 404
    except Exception as e:
        logger.error(f"Error retrieving similar.json: {str(e)}")
        return {"status": str(e)}, 500


# Run app with HTTP
if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000, debug=True)
