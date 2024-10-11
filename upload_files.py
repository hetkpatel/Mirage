import requests
from requests.auth import HTTPBasicAuth
from requests_toolbelt.multipart.encoder import (
    MultipartEncoder,
    MultipartEncoderMonitor,
)
import os
from mimetypes import guess_type
from argparse import ArgumentParser, ArgumentTypeError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


def _is_valid_path(arg):
    if not os.path.exists(arg):
        raise ArgumentTypeError(f"The path '{arg}' does not exist.")
    return arg


parser = ArgumentParser(prog="Project-Mirage")
parser.add_argument(dest="dir", type=_is_valid_path)
args = parser.parse_args()


def _is_image_or_video(file_path):
    mime_type, _ = guess_type(file_path)
    return False if mime_type is None else "image" in mime_type or "video" in mime_type


list_of_files = [
    os.path.abspath(os.path.join(root, file))
    for root, _, files in os.walk(args.dir)
    for file in files
    if file not in [".DS_Store"]
    and _is_image_or_video(os.path.abspath(os.path.join(root, file)))
]

proceed = input(f"Uploading {len(list_of_files)} files. Proceed? (y/n) ")

if proceed.lower() != "y":
    exit()


def create_multipart_with_progress(file_path, progress_bar):
    """
    Create a MultipartEncoderMonitor to track upload progress.
    """
    # Create a MultipartEncoder object
    encoder = MultipartEncoder(
        fields={
            "file": (
                os.path.basename(file_path),
                open(file_path, "rb"),
                "application/octet-stream",
            )
        }
    )

    # Create a monitor for the encoder that updates the progress bar
    monitor = MultipartEncoderMonitor(
        encoder,
        lambda monitor: progress_bar.update(monitor.bytes_read - progress_bar.n),
    )

    return monitor


HOSTNAME = os.getenv("HOSTNAME")
PORT = os.getenv("PORT")


def upload_file(file_path):
    """
    Upload a single file to the server with a progress bar.
    """
    # Get the file size for progress tracking
    file_size = os.path.getsize(file_path)

    with tqdm(
        total=file_size,
        unit="B",
        unit_scale=True,
        desc=os.path.basename(file_path),
        leave=False,
    ) as progress_bar:
        # Create the MultipartEncoderMonitor for progress tracking
        monitor = create_multipart_with_progress(file_path, progress_bar)

        # Perform the file upload
        response = requests.post(
            f"http://{HOSTNAME}:{PORT}/upload",
            data=monitor,  # Pass the monitor as data
            headers={"Content-Type": monitor.content_type},
            auth=HTTPBasicAuth("hetpatel", os.getenv("PASSWORD")),
        )

    # Check if the upload was successful
    if response.status_code != 201:
        print(f"Failed to upload: {file_path} (Status code: {response.status_code})")


for file in tqdm(list_of_files, desc="Uploading", unit="files"):
    try:
        upload_file(file)
    except Exception as e:
        print(f"Error uploading {file}: {e}")
        continue


response = requests.request(
    "POST",
    f"http://{HOSTNAME}:{PORT}/start?pulluploads=true",
    auth=HTTPBasicAuth("hetpatel", os.getenv("PASSWORD")),
)

print(response.status_code)
print(response.text)
