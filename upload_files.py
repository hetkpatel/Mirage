import requests
import os
from mimetypes import guess_type
from argparse import ArgumentParser, ArgumentTypeError
from dotenv import load_dotenv
import base64

load_dotenv()


def _is_valid_path(arg):
    if not os.path.exists(arg):
        raise ArgumentTypeError(f"The path '{arg}' does not exist.")
    return arg


parser = ArgumentParser(prog="Project-Mirage")
parser.add_argument(dest="dir", type=_is_valid_path, nargs="+")
args = parser.parse_args()

cred = f"hetpatel:{os.getenv('PASSWORD')}"


def _is_image_or_video(file_path):
    mime_type, _ = guess_type(file_path)
    return "image" in mime_type or "video" in mime_type


list_of_files = [
    os.path.abspath(os.path.join(root, file))
    for d in args.dir
    for root, _, files in os.walk(d)
    for file in files
    if file not in [".DS_Store"]
    and _is_image_or_video(os.path.abspath(os.path.join(root, file)))
]

for file in list_of_files:
    post_files = {
        "file": open(
            file,
            "rb",
        ),
    }
    response = requests.request(
        "POST",
        "http://pico.local:5000/upload",
        files=post_files,
        headers={"Authorization": f"Basic: {base64.b64encode(cred.encode()).decode()}"},
    )

    print(response.status_code)
    print(response.text)


response = requests.request(
    "POST",
    "http://pico.local:5000/start",
    headers={"Authorization": f"Basic: {base64.b64encode(cred.encode()).decode()}"},
)

print(response.status_code)
print(response.text)
