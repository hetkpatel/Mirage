import io
import json
import os
import shutil
import threading
import uuid
import requests as r
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, url_for
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import blurhash
import ffmpeg
from mirage_logger import HostingLoggerSingleton, ProcessingLoggerSingleton
from pillow_heif import register_heif_opener

# Load environment
load_dotenv()

# Setup loggers
os.makedirs("/mirage/logs", exist_ok=True)
hosting = HostingLoggerSingleton().get_logger()
processing = ProcessingLoggerSingleton().get_logger()

# Register HEIF
register_heif_opener()

# Flask app
app = Flask(__name__)
CORS(app)

# Authentication
auth = HTTPBasicAuth()
users = {os.getenv("USERNAME"): generate_password_hash(os.getenv("PASSWORD"))}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    hosting.warning(f"Authentication failed for user: {username}")
    return None


# Drive paths
app.config["DRIVE_LOCATION"] = "/mirage/DRIVE"
uploads_dir = os.path.join(app.config["DRIVE_LOCATION"], "uploads")
media_dir = os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
embeddings_dir = os.path.join(app.config["DRIVE_LOCATION"], "media", "embeddings")
backup_dir = "/mirage/backup"
for d in (uploads_dir, media_dir, embeddings_dir, backup_dir, "/mirage/logs"):
    os.makedirs(d, exist_ok=True)

# JSON files
MAPPING_FILE = os.path.join(
    app.config["DRIVE_LOCATION"], "media", "filename_mapping.json"
)
METADATA_FILE = os.path.join(app.config["DRIVE_LOCATION"], "media", "metadata.json")
TRASH_FILE = os.path.join(app.config["DRIVE_LOCATION"], "media", "trash.json")


# Ensure JSON files exist
def ensure_file(path, desc):
    if not os.path.isfile(path):
        with open(path, "w") as f:
            json.dump({}, f)
        processing.info(f"Created {desc} at {path}")


try:
    ensure_file(MAPPING_FILE, "filename mapping file")
    ensure_file(METADATA_FILE, "metadata file")
    ensure_file(TRASH_FILE, "trash file")
except Exception as e:
    hosting.error(f"Error ensuring JSON files: {e}")
    raise


# Load dict
def load_dict(path, desc):
    try:
        with open(path) as f:
            data = json.load(f)
        processing.info(f"Loaded {desc}")
        return data
    except Exception as e:
        hosting.error(f"Failed to load {desc}: {e}")
        return {}


filename_mapping = load_dict(MAPPING_FILE, "filename mappings")
metadata = load_dict(METADATA_FILE, "metadata")
trash = load_dict(TRASH_FILE, "trash list")


# Save dict
def save_dict(path, data, desc):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
        processing.info(f"Saved {desc}")
    except Exception as e:
        hosting.error(f"Failed to save {desc}: {e}")
        abort(500, description=f"Unable to save {desc}")


# Wait for Ollama
def wait_for_ollama(host="http://ollama:11434", interval=15):
    while True:
        try:
            res = r.get(host)
            if res.status_code == 200:
                processing.info("Ollama server is ready")
                break
        except r.exceptions.RequestException:
            processing.warning("Waiting for Ollama server...")
        time.sleep(interval)


# Build and cleanup model
def build_model():
    try:
        processing.info("Building mirage-date-extractor model")
        res = r.post(
            "http://ollama:11434/api/create",
            json={
                "name": "mirage-date-extractor",
                "from": "gemma2:2b",
                "system": 'Extract date in "YYYY:MM:DD"; return null if unknown.',
            },
        )
        res.raise_for_status()
        processing.info("Model built successfully")
    except Exception as e:
        hosting.error(f"Model build failed: {e}")


def cleanup_model():
    try:
        processing.info("Cleaning up base model")
        r.delete("http://ollama:11434/api/delete", json={"model": "gemma2:2b"})
    except Exception as e:
        processing.warning(f"Model cleanup warning: {e}")


# Initialize external model
wait_for_ollama()
build_model()
cleanup_model()

# Import internal tools
try:
    from tools.extract_metadata import get_metadata
    from tools.embedder import create_embedding
    from tools.find_similar import find_similar

    processing.info("Imported processing tools")
except Exception as e:
    hosting.error(f"Tool import failed: {e}")
    raise

# Global processing status
pending = 1
total = 1
processing_similar = False

processing.info("READY")


# Unified error handler
@app.errorhandler(Exception)
def handle_exception(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
        message = e.description
    else:
        message = str(e)
    hosting.error(f"Error: {message}")
    return jsonify({"error": message}), code


# Health check
@app.route("/", methods=["GET"])
def index():
    processing.info("Health check OK")
    return jsonify({"status": "running"}), 200


# Upload endpoint
@app.route("/upload", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        hosting.warning("Missing file in request")
        abort(400, description="No file part")
    file = request.files["file"]
    if file.filename == "":
        hosting.warning("Empty filename provided")
        abort(400, description="No selected file")
    original = secure_filename(file.filename)
    uid = uuid.uuid4().hex
    ext = original.rsplit(".", 1)[-1]
    unique = f"{uid}.{ext}"
    dest = os.path.join(uploads_dir, unique)
    try:
        file.save(dest)
        hosting.info(f"Saved upload {original} as {unique}")
        filename_mapping[unique] = original
        save_dict(MAPPING_FILE, filename_mapping, "filename mappings")
        return (
            jsonify(
                {
                    "status": "uploaded",
                    "url": url_for("download_file", unique_id=uid, _external=True),
                }
            ),
            201,
        )
    except Exception as e:
        hosting.error(f"Upload failed: {e}")
        abort(500, description="Upload failed")


# Media processing thread
def process_media(pull_uploads: bool):
    global pending, total, processing_similar
    processing.info(f"Started processing media (pull_uploads={pull_uploads})")
    try:
        if pull_uploads:
            upload_files = os.listdir(uploads_dir)
            total = len(upload_files)
            pending = 0
            processing.info(f"Found {total} files to process")
            for filename in upload_files:
                path = os.path.join(uploads_dir, filename)
                try:
                    processing.info(f"Processing {filename}")
                    meta = get_metadata(
                        id_file_path=path,
                        org_filename=filename_mapping.get(filename, filename),
                    )
                    metadata[filename] = meta
                    mime = meta.get("MIMEType", "")
                    # BlurHash
                    if mime.startswith("image/"):
                        metadata[filename]["BlurHash"] = blurhash.encode(
                            path, x_components=4, y_components=3
                        )
                    elif mime.startswith("video/"):
                        thumb, _ = (
                            ffmpeg.input(path, ss=0.1)
                            .output("pipe:", vframes=1, format="image2", vcodec="png")
                            .run(capture_stdout=True, capture_stderr=True)
                        )
                        metadata[filename]["BlurHash"] = blurhash.encode(
                            Image.open(io.BytesIO(thumb)).convert("RGB"),
                            x_components=4,
                            y_components=3,
                        )
                    save_dict(METADATA_FILE, metadata, "metadata")
                    create_embedding(
                        file=path, embedding_folder=embeddings_dir, mimetype=mime
                    )
                    shutil.move(path, media_dir)
                    processing.info(f"Moved {filename} to media folder")
                except Exception as err:
                    hosting.error(f"Error processing {filename}: {err}")
                finally:
                    pending += 1
        # Similar processing\schedule
        processing.info("Finding similar media...")
        processing_similar = True
        find_similar(
            vector_folder=embeddings_dir,
            filename_mapping_json=filename_mapping,
            media_folder=media_dir,
            output=os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json"),
        )
        processing.info("Similar media completed")
        processing_similar = False
        # Backup
        shutil.make_archive(
            os.path.join(backup_dir, "Mirage-Backup"),
            "zip",
            os.path.join(app.config["DRIVE_LOCATION"], "media"),
        )
        processing.info("Backup created")
    except Exception as e:
        hosting.error(f"Processing thread encountered error: {e}")
    finally:
        pending = total = 1


# Start processing endpoint
@app.route("/start", methods=["POST"])
@auth.login_required
def start_process():
    pull = request.args.get("pulluploads", "false").lower() == "true"
    processing.info(f"Start request: pulluploads={pull}")
    thread = threading.Thread(target=process_media, args=(pull,))
    thread.start()
    return jsonify({"status": url_for("process_status", _external=True)}), 202


# Status endpoint
@app.route("/status", methods=["GET"])
@auth.login_required
def process_status():
    progress = (pending / total) if total else 1
    hosting.info(f"Status: {progress*100:.2f}%")
    status_code = 200 if progress == 1 else 425
    return (
        jsonify({"progress": progress, "processing_similar": processing_similar}),
        status_code,
    )


# Thumbnail generators
def generate_image_thumbnail(image_bytes, name="unknown") -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((640, 640))
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG")
        hosting.info(f"Generated image thumbnail for {name}")
        return out.getvalue()
    except Exception as e:
        hosting.error(f"Thumbnail error ({name}): {e}")
        abort(500, description="Thumbnail generation failed")


def generate_video_thumbnail(path: str) -> bytes:
    try:
        out, _ = (
            ffmpeg.input(path, ss=0.1)
            .output("pipe:", vframes=1, format="image2", vcodec="png")
            .run(capture_stdout=True, capture_stderr=True)
        )
        hosting.info(f"Generated video thumbnail from {path}")
        return generate_image_thumbnail(out, os.path.basename(path))
    except ffmpeg.Error as e:
        hosting.error(f"FFmpeg error for {path}: {e.stderr}")
        abort(500, description="Video thumbnail failed")
    except Exception as e:
        hosting.error(f"Unexpected video thumbnail error for {path}: {e}")
        abort(500, description="Video thumbnail failed")


# Download endpoint
@app.route("/download/<unique_id>", methods=["GET"])
# TODO: @auth.login_required
def download_file(unique_id):
    try:
        if len(unique_id) != 32:
            hosting.warning(f"Invalid ID: {unique_id}")
            abort(400, description="Invalid media ID")
        thumbnail = request.args.get("thumbnail", "false").lower() == "true"
        downloadable = request.args.get("downloadable", "false").lower() == "true"
        # find file
        for fname in os.listdir(media_dir):
            if fname.startswith(unique_id):
                original = filename_mapping.get(fname)
                if not original:
                    hosting.error(f"Missing mapping for {fname}")
                    abort(404, description="File mapping not found")
                path = os.path.join(media_dir, fname)
                if not os.path.isfile(path):
                    abort(404, description="File not found")
                mime = metadata.get(fname, {}).get("MIMEType", "")
                with open(path, "rb") as f:
                    data = f.read()
                if thumbnail:
                    if mime.startswith("image/"):
                        data = generate_image_thumbnail(data, fname)
                        mime = "image/jpeg"
                    elif mime.startswith("video/"):
                        data = generate_video_thumbnail(path)
                        mime = "image/jpeg"
                    else:
                        hosting.warning(f"Unsupported thumbnail type: {mime}")
                        abort(415)
                elif not downloadable and mime.startswith("image/"):
                    data = generate_image_thumbnail(data, fname)
                    mime = "image/jpeg"
                headers = {
                    "Content-Type": mime,
                    "Content-Disposition": f'attachment; filename="{original}"',
                }
                hosting.info(f"Serving file {original}")
                return data, 200, headers
        hosting.warning(f"ID {unique_id} not found")
        abort(404, description="Media ID not found")
    except HTTPException:
        raise
    except Exception as e:
        hosting.error(f"Download error: {e}")
        abort(500, description="Download failed")


# List files
@app.route("/list", methods=["GET"])
@auth.login_required
def list_files():
    items = []
    for fname in filename_mapping:
        if fname in trash:
            continue
        path = os.path.join(media_dir, fname)
        if not os.path.isfile(path):
            continue
        data = metadata.get(fname, {})
        items.append(
            {
                "id": fname[:32],
                "name": filename_mapping[fname],
                "url": url_for("download_file", unique_id=fname[:32], _external=True),
                "width": data.get("Width"),
                "height": data.get("Height"),
                "metadata": data,
            }
        )
    hosting.info(f"Listed {len(items)} items")
    return jsonify(items), 200


# Similar JSON
@app.route("/similar", methods=["GET"])
@auth.login_required
def get_similar():
    try:
        path = os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json")
        with open(path) as f:
            hosting.info("Returning similar.json")
            return jsonify(json.load(f)), 200
    except FileNotFoundError:
        hosting.warning("similar.json not found")
        abort(404, description="File not found")
    except Exception as e:
        hosting.error(f"Error reading similar.json: {e}")
        abort(500, description="Error retrieving similar data")


# Trash list
@app.route("/trash", methods=["GET"])
@auth.login_required
def get_trash():
    items = []
    for fname, expiry in trash.items():
        path = os.path.join(media_dir, fname)
        if not os.path.isfile(path):
            continue
        data = metadata.get(fname, {})
        items.append(
            {
                "id": fname[:32],
                "name": filename_mapping.get(fname),
                "url": url_for("download_file", unique_id=fname[:32], _external=True),
                "width": data.get("Width"),
                "height": data.get("Height"),
                "metadata": data,
                "expiry": expiry,
            }
        )
    hosting.info(f"Retrieved {len(items)} trashed items")
    return jsonify(items), 200


# Trash/restore endpoint
@app.route("/trash/<unique_id>", methods=["POST"])
@auth.login_required
def toggle_trash(unique_id):
    if len(unique_id) != 32:
        abort(400, description="Invalid media ID")
    for fname in os.listdir(media_dir):
        if fname.startswith(unique_id):
            if fname in trash:
                trash.pop(fname)
                action = "restored"
                hosting.info(f"Restored {fname} from trash")
            else:
                expiry = (
                    datetime.now().replace(hour=23, minute=59) + timedelta(days=30)
                ).strftime("%Y-%m-%d %H:%M:00")
                trash[fname] = expiry
                action = "trashed"
                hosting.info(f"Trashed {fname} until {expiry}")
            save_dict(TRASH_FILE, trash, "trash list")
            return jsonify({"status": action}), 200
    abort(404, description="Media ID not found")


# Storage usage
@app.route("/usage", methods=["GET"])
@auth.login_required
def storage_usage():
    try:
        usage = shutil.disk_usage(app.config["DRIVE_LOCATION"])
        return jsonify({"used": usage.used, "total": usage.total}), 200

    except Exception as e:
        hosting.error(f"Usage endpoint error: {e}")
        abort(500, description="Could not retrieve storage usage")
