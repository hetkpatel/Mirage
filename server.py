import io
import os
import shutil
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


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username


# External SSD path
if not os.path.isdir(os.getenv("DRIVE_LOCATION")):
    exit("DRIVE_LOCATION does not exists. It may not be mounted properly.")
app.config["DRIVE_LOCATION"] = os.getenv("DRIVE_LOCATION")
os.makedirs(os.path.join(os.getenv("DRIVE_LOCATION"), "uploads"), exist_ok=True)
os.makedirs(os.path.join(os.getenv("DRIVE_LOCATION"), "media", "media"), exist_ok=True)

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
    os.getenv("DRIVE_LOCATION"), "media", "filename_mapping.json"
)
# METADATA_FILE = os.path.join(os.getenv("DRIVE_LOCATION"), "media", "metadata.json")

if not os.path.isfile(MAPPING_FILE):
    with open(MAPPING_FILE, "w") as f:
        json.dump({}, f)
# if not os.path.isfile(METADATA_FILE):
#     with open(METADATA_FILE, "w") as f:
#         json.dump({}, f)


# Save mappings to the JSON file
def save_dictionary(json_file, dictionary):
    with open(json_file, "w") as f:
        json.dump(dictionary, f)


# Initialize the dictionairies
with open(MAPPING_FILE, "r") as f:
    filename_mapping = json.load(f)

from tools.embedder import *
from tools.extract_metadata import *
from tools.find_similar import *


# Route to check if the server is running
@app.route("/")
def index():
    return "Server is running!", 200


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
        original_filename = secure_filename(file.filename)
        uid = uuid.uuid4().hex
        unique_filename = f'{uid}.{original_filename.split(".")[-1]}'
        # encrypted_data = cipher_suite.encrypt(file.read())
        file_path = os.path.join(
            app.config["DRIVE_LOCATION"], "uploads", unique_filename
        )
        with open(file_path, "wb") as f:
            f.write(file.read())
        # file.save(file_path)

        # Update the mapping and save it to the JSON file
        filename_mapping[unique_filename] = original_filename
        save_dictionary(MAPPING_FILE, filename_mapping)

        return {
            "status": "Resource uploaded",
            "url": url_for("download_file", unique_id=uid, _external=True),
        }, 201


def process_media():
    files = [
        os.path.join(app.config["DRIVE_LOCATION"], "uploads", f)
        for f in os.listdir(os.path.join(app.config["DRIVE_LOCATION"], "uploads"))
    ]
    global pending, total, current_file_in_process
    pending = 0
    total = len(files)
    for f in files:
        current_file_in_process = os.path.basename(f)
        # create embedding
        create_vector(f, os.path.join(app.config["DRIVE_LOCATION"], "media", "VE"))

        # # extract metadata
        # file_meta = get_metadata(f)
        # del file_meta["SourceFile"]

        # TODO: FUTURE FEATURE: extract image quality score

        # # Update metadata json file
        # with open(METADATA_FILE, "r") as metafile:
        #     metadata = json.load(metafile)
        #     metadata[os.path.basename(f)] = file_meta
        #     save_dictionary(METADATA_FILE, metadata)

        # move file to media folder
        shutil.move(f, os.path.join(app.config["DRIVE_LOCATION"], "media", "media"))

        pending += 1

    current_file_in_process = "Finding similar images and videos"
    pending = 9
    total = 10

    # TODO: perform duplication checks
    find_similar(
        vector_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "VE"),
        filename_mapping_json=filename_mapping,
        media_folder=os.path.join(app.config["DRIVE_LOCATION"], "media", "media"),
        output=os.path.join(app.config["DRIVE_LOCATION"], "media", "similar.json"),
    )

    current_file_in_process = ""
    pending = 1
    total = 1

    # create copy of 'media' folder stored elsewhere
    shutil.make_archive(
        "Mirage-Backup", "zip", os.path.join(app.config["DRIVE_LOCATION"], "media")
    )


@app.route("/start", methods=["POST"])
@auth.login_required
def start_process():
    # Start processing media as background task
    thread = threading.Thread(target=process_media)
    thread.start()

    return {
        "status": url_for("process_status", _external=True),
    }, 202


@app.route("/status", methods=["GET"])
@auth.login_required
def process_status():
    global pending, total
    progress = ((pending / total) if total != 0 else 1) * 100
    return jsonify(
        {
            "progress": progress,
            "current": filename_mapping.get(current_file_in_process),
        }
    ), (425 if progress < 100 else 200)


# Route to start importing, tagging, and categorizing files
@app.route("/start", methods=["POST"])
@auth.login_required
def start_processes():
    # Implement the import logic here
    return "Importing files...", 200


def generate_image_thumbnail(file_bytes) -> bytes:
    """
    Generate a thumbnail for an image file.

    :param file_bytes: Bytes of the image file.
    :return: Thumbnail image as bytes.
    """
    with Image.open(io.BytesIO(file_bytes)) as img:
        img.thumbnail((640, 640))
        img_io = io.BytesIO()
        img.save(img_io, format=img.format)
        img_io.seek(0)
    return img_io.getvalue()


def generate_video_thumbnail(video_path: str) -> bytes:
    """
    Extract a thumbnail from a video file and return it as bytes.

    :param video_path: Path to the video file.
    :return: Thumbnail image as bytes.
    """
    try:
        out, _ = (
            ffmpeg.input(video_path, ss=0.1)
            .output("pipe:", vframes=1, format="image2", vcodec="png")
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print(e.stderr)
        return abort(500)

    return generate_image_thumbnail(out)


@app.route("/download/<unique_id>", methods=["GET"])
@auth.login_required
def download_file(unique_id):
    # Check to see if unique_id is valid
    if len(unique_id) != 32:
        return {"status": "Invalid media ID"}, 400

    thumbnail = request.args.get("thumbnail", "false").lower() == "true"
    for file_path in os.listdir(
        os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    ):
        if file_path.startswith(unique_id):
            if os.path.exists(
                os.path.join(app.config["DRIVE_LOCATION"], "media", "media", file_path)
            ):
                original_filename = filename_mapping.get(file_path)
                if not original_filename:
                    return abort(404)
                file_path = os.path.join(
                    app.config["DRIVE_LOCATION"], "media", "media", file_path
                )

                # Read mimetype of file (image or video)
                content_type = (
                    mimetypes.guess_type(original_filename, strict=True)[0]
                    or "application/octet-stream"
                )

                with open(file_path, "rb") as f:
                    file_data = f.read()

                    if thumbnail:
                        # Generate the thumbnail in memory
                        if content_type.startswith("image/"):
                            # Generate thumbnail for image
                            file_data = generate_image_thumbnail(file_data)
                            content_type = "image/jpeg"
                        elif content_type.startswith("video/"):
                            # Generate thumbnail for video
                            file_data = generate_video_thumbnail(file_path)
                            content_type = "image/jpeg"
                        else:
                            return abort(415)

                return (
                    # decrypted_data,
                    file_data,
                    200,
                    {
                        "Content-Type": content_type,
                        "Content-Disposition": f"attachment; filename={os.path.basename(original_filename)}",
                        "X-Metadata": get_metadata(file_path),
                    },
                )
            else:
                return abort(404)


# Route to delete files
@app.route("/delete/<unique_id>", methods=["DELETE"])
@auth.login_required
def delete_file(unique_id):
    # Check to see if unique_id is valid
    if len(unique_id) != 32:
        return {"status": "Invalid media ID"}, 400

    for file_path in os.listdir(
        os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    ):
        if file_path.startswith(unique_id):
            file_path = os.path.join(
                app.config["DRIVE_LOCATION"], "media", "media", file_path
            )

            # Remove all references of file
            os.remove(file_path)
            filename_mapping.pop(os.path.basename(file_path), None)
            save_dictionary(MAPPING_FILE, filename_mapping)
            # TODO: Delete vectors

            return {"status": "Resource deleted"}, 202

    return {"status": "Resource not found. No action taken."}, 204


# Route to list files and folders with metadata
@app.route("/list", methods=["GET"])
@auth.login_required
def list():
    items = []
    dir_path = os.path.join(app.config["DRIVE_LOCATION"], "media", "media")
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        item_info = {
            "name": filename_mapping.get(item),
            "size": os.path.getsize(item_path),
            "url": url_for(
                "download_file", unique_id=item.split(".")[0], _external=True
            ),
            "mime_type": (mimetypes.guess_type(filename_mapping.get(item))[0]),
            "metadata": get_metadata(item_path),
        }
        items.append(item_info)
    return jsonify(items), 200


# Run app with HTTP
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
