"""
wsgi.py
Author: Het Patel
Version: 2025.05.28
Description: This file contains the WSGI application for the Mirage server.
It initializes the Flask app, sets up routes for file upload, download, and processing,
and handles authentication. It also includes functionality for processing media files,
generating thumbnails, and managing metadata. The application is designed to run in a Docker container.
"""

import io
import json
import os
import shutil
import threading
import uuid
import requests as r
import time
from mirage_logger import HostingLoggerSingleton, ProcessingLoggerSingleton
from datetime import datetime, timedelta
import blurhash
import ffmpeg
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, url_for
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from PIL import Image
from pillow_heif import register_heif_opener
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Load .env file
load_dotenv()

# Configure logging
os.makedirs("/mirage/logs", exist_ok=True)
hosting = HostingLoggerSingleton().get_logger()
processing = ProcessingLoggerSingleton().get_logger()

# Register HEIF opener
register_heif_opener()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Status for processing
pending = 1
total = 1
processing_similar_bool = False

# Authentication setup
auth = HTTPBasicAuth()
users = {os.getenv("USERNAME"): generate_password_hash(os.getenv("PASSWORD"))}


# Authentication verification
@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


app.config["DRIVE_LOCATION"] = "/mirage/DRIVE"
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
    processing.info("Created new filename_mapping.json file.")
METADATA_FILE = os.path.join(app.config["DRIVE_LOCATION"], "media", "metadata.json")
if not os.path.isfile(METADATA_FILE):
    with open(METADATA_FILE, "w") as f:
        json.dump({}, f)
    processing.info("Created new metadata.json file.")
TRASH_FILE = os.path.join(app.config["DRIVE_LOCATION"], "media", "trash.json")
if not os.path.isfile(TRASH_FILE):
    with open(TRASH_FILE, "w") as f:
        json.dump({}, f)
    processing.info("Created new trash.json file.")


# Save mappings to the JSON file
def save_dictionary(json_file, dictionary):
    with open(json_file, "w") as f:
        json.dump(dictionary, f)


# Initialize the dictionaries
with open(MAPPING_FILE, "r") as f:
    filename_mapping = json.load(f)
processing.info("Loaded filename mappings from JSON file.")
with open(METADATA_FILE, "r") as f:
    metadata = json.load(f)
processing.info("Loaded metadata from JSON file.")
with open(TRASH_FILE, "r") as f:
    trash = json.load(f)
processing.info("Loaded trash from JSON file.")

# Wait for the Ollama server to be ready
while True:
    try:
        res = r.get("http://ollama:11434")
        if res.status_code == 200:
            processing.info("Ollama server is ready.")
            break
    except r.exceptions.ConnectionError:
        pass
    processing.info("Waiting for Ollama server to start... (15s)")
    time.sleep(15)

# Build model
processing.info("Building mirage-date-extractor model...")
res = r.post(
    f"http://ollama:11434/api/create",
    json={
        "name": "mirage-date-extractor",
        "from": "gemma2:2b",
        "system": 'Given a file name, extract the date in the format of "YYYY:MM:DD". Only return the date and no other information or data. If the date cannot be extracted, return "null".',
    },
)
if res.ok:
    processing.info("Model built")
else:
    print(f"Failed to create model: {res.status_code}")
    print(res.text)

# Clean up
processing.info("Cleaning up...")
r.delete(
    f"http://ollama:11434/api/delete",
    json={"model": "gemma2:2b"},
)

# Import processing tools
from tools.embedder import *
from tools.extract_metadata import *
from tools.find_similar import *

processing.info("READY")


# Route to check if the server is running
@app.route("/")
def index():
    processing.info("Health check - Server is running.")
    return "Server is running!", 200


# Route to upload files
@app.route("/upload", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        hosting.warning("No file part in the request.")
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        hosting.warning("No file selected for upload.")
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
        hosting.info(
            f"File {original_filename} uploaded and saved as {unique_filename}."
        )

        # Update the mapping and save it to the JSON file
        filename_mapping[unique_filename] = original_filename
        save_dictionary(MAPPING_FILE, filename_mapping)
        processing.info(f"Filename mapping for {unique_filename} saved.")

        return {
            "status": "Resource uploaded",
            "url": url_for("download_file", unique_id=uid, _external=True),
        }, 201


# Function to process media files
def process_media(pull_uploads: bool):
    global pending, total, processing_similar_bool
    processing.info("STARTED PROCESSING MEDIA")
    processing.info(f"Pull uploads: {pull_uploads}")

    if pull_uploads:
        files = [
            os.path.join(app.config["DRIVE_LOCATION"], "uploads", f)
            for f in os.listdir(os.path.join(app.config["DRIVE_LOCATION"], "uploads"))
        ]
        pending = 0
        total = len(files)
        processing.info(f"Found {total} files to process.")

        for f in files:
            current_file_in_process = os.path.basename(f)
            processing.info(f"Processing file {current_file_in_process}.")
            # Create metadata
            metadata[os.path.basename(f)] = get_metadata(
                id_file_path=f,
                org_filename=filename_mapping[os.path.basename(f)],
            )

            content_type = metadata[os.path.basename(f)]["MIMEType"]
            if content_type.startswith("image/"):
                metadata[os.path.basename(f)]["BlurHash"] = blurhash.encode(
                    f, x_components=4, y_components=3
                )
            elif content_type.startswith("video/"):
                try:
                    out, _ = (
                        ffmpeg.input(f, ss=0.1)
                        .output("pipe:", vframes=1, format="image2", vcodec="png")
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    with Image.open(io.BytesIO(out)) as img:
                        img.thumbnail((640, 640))
                        rgb_v = img.convert("RGB")
                        metadata[os.path.basename(f)]["BlurHash"] = blurhash.encode(
                            rgb_v, x_components=4, y_components=3
                        )
                except ffmpeg.Error as e:
                    print(e)
                except Exception as e:
                    print(e)
            else:
                print(f"Unsupported content type: {content_type}")
            save_dictionary(METADATA_FILE, metadata)
            # Create embedding
            create_embedding(
                file=f,
                embedding_folder=os.path.join(
                    app.config["DRIVE_LOCATION"], "media", "embeddings"
                ),
                mimetype=metadata[os.path.basename(f)]["MIMEType"],
            )
            # Move file to media folder
            shutil.move(f, os.path.join(app.config["DRIVE_LOCATION"], "media", "media"))
            pending += 1
            processing.info(
                f"File {current_file_in_process} processed and moved to media folder."
            )

    # Unload mirage-date-extractor model
    processing.info(f"Unload mirage-date-extractor model")
    r.post(
        f"http://ollama:11434/api/generate",
        json={"model": "mirage-date-extractor", "keep_alive": 0},
    )

    processing_similar_bool = True
    pending = 99
    total = 100
    processing.info("Finding similar photos and videos.")
    find_similar(
        vector_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "embeddings"),
        filename_mapping_json=filename_mapping,
        media_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "media"),
        output=os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json"),
    )
    processing.info("Similar photos and videos process completed.")
    processing_similar_bool = False
    pending = 1
    total = 1

    # Create copy of 'media' folder stored elsewhere
    shutil.make_archive(
        os.path.join("/mirage/backup", "Mirage-Backup"),
        "zip",
        os.path.join(app.config["DRIVE_LOCATION"], "media"),
    )
    processing.info("Created backup archive of the media folder.")
    processing.info("FINISHED PROCESSING MEDIA")


# Route to start importing, tagging, and categorizing files
@app.route("/start", methods=["POST"])
@auth.login_required
def start_process():
    pull_uploads = request.args.get("pull_uploads", "false").lower() == "true"
    processing.info(f"Received request to start process. pull_uploads={pull_uploads}")

    thread = threading.Thread(target=process_media, args=(pull_uploads,))
    thread.start()
    processing.info("Background processing thread started.")

    return {
        "status": url_for("process_status", _external=True),
    }, 202


# Route to get the status of the processing
@app.route("/status", methods=["GET"])
@auth.login_required
def process_status():
    global pending, total
    progress = (pending / total) if total != 0 else 1
    hosting.info(f"Status requested. Progress: {progress}%")

    return jsonify(
        {
            "progress": progress,
            "processing_similar": processing_similar_bool,
        }
    ), (425 if progress < 1 else 200)


# Generate a thumbnail for an image file
def generate_image_thumbnail(image_bytes, image_name="NULL") -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.thumbnail((640, 640))
            rgb_v = img.convert("RGB")
            img_io = io.BytesIO()
            rgb_v.save(img_io, format="JPEG")
            img_io.seek(0)
        hosting.info("Generated image thumbnail.")
        return img_io.getvalue()
    except Exception as e:
        hosting.error(f"Unexpected error generating image thumbnail: {image_name}: {e}")
        return abort(500)


# Extract a thumbnail from a video file and return it as bytes
def generate_video_thumbnail(video_path: str) -> bytes:
    try:
        out, _ = (
            ffmpeg.input(video_path, ss=0.1)
            .output("pipe:", vframes=1, format="image2", vcodec="png")
            .run(capture_stdout=True, capture_stderr=True)
        )
        hosting.info("Generated video thumbnail.")
        return generate_image_thumbnail(out)
    except ffmpeg.Error as e:
        hosting.error(f"Error generating video thumbnail: {video_path}: {e.stderr}")
        return abort(500)
    except Exception as e:
        hosting.error(f"Unexpected error generating video thumbnail: {video_path}: {e}")
        return abort(500)


# Route to download or get thumbnail of image or video
@app.route("/download/<unique_id>", methods=["GET"])
# TODO: @auth.login_required
def download_file(unique_id):
    hosting.info(f"Download request for file with unique_id: {unique_id}")

    if len(unique_id) != 32:
        hosting.warning("Invalid media ID received.")
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
                    hosting.error(f"Original filename not found for file: {file_path}")
                    return abort(404)

                file_path = os.path.join(
                    app.config["DRIVE_LOCATION"], "media", "media", file_path
                )
                content_type = metadata[os.path.basename(file_path)]["MIMEType"]

                with open(file_path, "rb") as f:
                    file_data = f.read()

                    if thumbnail:
                        if content_type.startswith("image/"):
                            hosting.info("Generating thumbnail for image file.")
                            file_data = generate_image_thumbnail(
                                file_data, os.path.basename(file_path)
                            )
                            content_type = "image/jpeg"
                        elif content_type.startswith("video/"):
                            hosting.info("Generating thumbnail for video file.")
                            file_data = generate_video_thumbnail(file_path)
                            content_type = "image/jpeg"
                        else:
                            hosting.warning(
                                f"Unsupported content type for thumbnail: {content_type}"
                            )
                            return abort(415)
                    elif not downloadable:
                        hosting.info("Serving JPEG version of full res file")
                        if content_type.startswith("image/"):
                            with Image.open(io.BytesIO(file_data)) as img:
                                rgb_v = img.convert("RGB")
                                img_io = io.BytesIO()
                                rgb_v.save(img_io, format="JPEG")
                                img_io.seek(0)
                            file_data = img_io.getvalue()
                            content_type = "image/jpeg"
                        elif content_type.startswith("video/"):
                            pass
                        else:
                            hosting.warning(f"Unsupported content type: {content_type}")
                            return abort(415)

                hosting.info(f"File {original_filename} served for download.")
                return (
                    file_data,
                    200,
                    {
                        "Content-Type": content_type,
                        "Content-Disposition": f"attachment; filename={os.path.basename(original_filename)}",
                    },
                )
            else:
                hosting.error(f"File not found: {file_path}")
                return abort(404)

    hosting.warning(f"File ID not found: {unique_id}")
    return abort(404)


# Route to list files and folders with metadata
@app.route("/list", methods=["GET"])
@auth.login_required
def list_files():
    hosting.info("List request received.")
    hosting.info(f"{len(filename_mapping) - len(trash)} items listed.")
    return (
        jsonify(
            [
                {
                    "id": item[:32],
                    "name": filename_mapping.get(item),
                    "url": url_for(
                        "download_file", unique_id=item[:32], _external=True
                    ),
                    "width": metadata.get(item)["Width"],
                    "height": metadata.get(item)["Height"],
                    "metadata": metadata.get(item),
                }
                for item in filename_mapping
                if os.path.exists(
                    os.path.join(app.config["DRIVE_LOCATION"], "media", "media", item)
                )
                and item not in trash
            ]
        ),
        200,
    )


# Route get similar.json file
@app.route("/similar", methods=["GET"])
@auth.login_required
def get_similar_json():
    try:
        with open(
            os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json")
        ) as f:
            hosting.info("Returning similar.json file.")
            return jsonify(json.load(f)), 200
    except FileNotFoundError:
        hosting.warning("similar.json file not found.")
        return {"status": "File not found"}, 404
    except Exception as e:
        hosting.error(f"Error retrieving similar.json: {str(e)}")
        return {"status": str(e)}, 500


# Route get trash.json file
@app.route("/trash", methods=["GET"])
@auth.login_required
def get_trash():
    hosting.info("Trash request received.")
    hosting.info(f"Return {len(trash)} items.")
    return (
        jsonify(
            [
                {
                    "id": id[:32],
                    "name": filename_mapping.get(id),
                    "url": url_for("download_file", unique_id=id[:32], _external=True),
                    "width": metadata.get(id)["Width"],
                    "height": metadata.get(id)["Height"],
                    "metadata": metadata.get(id),
                    "expiry": expiry,
                }
                for id, expiry in trash.items()
                if os.path.exists(
                    os.path.join(app.config["DRIVE_LOCATION"], "media", "media", id)
                )
            ]
        ),
        200,
    )


# Route trash a file
@app.route("/trash/<unique_id>", methods=["POST"])
@auth.login_required
def trash_file(unique_id):
    hosting.info(f"Trash request for file with unique_id: {unique_id}")

    if len(unique_id) != 32:
        hosting.warning("Invalid media ID received.")
        return {"status": "Invalid media ID"}, 400

    for file_path in os.listdir(
        os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    ):
        if file_path.startswith(unique_id):
            if file_path in trash:
                hosting.info("Removing file from trash")
                trash.pop(file_path)
            else:
                hosting.info("Adding file to trash")
                trash[file_path] = (
                    datetime.now().replace(hour=23, minute=59) + timedelta(days=30)
                ).strftime("%Y-%m-%d %H:%M:00")
            save_dictionary(TRASH_FILE, trash)

            return {"status": "Complete"}, 200

    hosting.info("Resource not found. No action taken.")
    return {"status": "Resource not found. No action taken."}, 204


@app.route("/usage", methods=["GET"])
@auth.login_required
def storage_usage():
    try:
        # Get total, used, and free space on the filesystem where the directory is located
        disk_usage = shutil.disk_usage(app.config["DRIVE_LOCATION"])

        return (
            jsonify(
                {
                    "used": disk_usage.used,
                    "total": disk_usage.total,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
