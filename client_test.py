import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

# Load .env file
load_dotenv()

# Server URL
base_url = "http://pico:5000"

# Authentication
auth = HTTPBasicAuth("hetpatel", os.getenv("PASSWORD"))


# Function to upload a file
def upload_file(filepath, target_path):
    url = f"{base_url}/upload"
    with open(filepath, "rb") as file:
        files = {"file": (target_path, file)}
        response = requests.post(url, files=files, auth=auth)
    return response


# Function to download a file
def download_file(target_path, save_as):
    url = f"{base_url}/download/{target_path}"
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        os.makedirs(os.path.dirname(save_as), exist_ok=True)
        with open(save_as, "wb") as file:
            file.write(response.content)
    return response


# Function to delete a file
def delete_file(target_path):
    url = f"{base_url}/delete/{target_path}"
    response = requests.delete(url, auth=auth, verify=False)
    return response


# Test uploading a simple file
response = upload_file("./LICENSE", "LICENSE")
print(f"Upload LICENSE: {response.status_code} - {response.text}")

# Test uploading a file with directories
response = upload_file(
    "./dataset/test-images-only/1-1_IMG_0.HEIC",
    "dataset/test-images-only/1-1_IMG_0.HEIC",
)
print(
    f"Upload dataset/test-images-only/1-1_IMG_0.HEIC: {response.status_code} - {response.text}"
)

# Test downloading the simple file
response = download_file(target_path="LICENSE", save_as="./server-output/LICENSE")
print(
    f"Download LICENSE: {response.status_code} - {'File downloaded' if response.status_code == 200 else response.text}"
)

# Test downloading the file with directories
response = download_file(
    "dataset/test-images-only/1-1_IMG_0.HEIC",
    "./server-output/dataset/test-images-only/1-1_IMG_0.HEIC",
)
print(
    f"Download dataset/test-images-only/1-1_IMG_0.HEIC: {response.status_code} - {'File downloaded' if response.status_code == 200 else response.text}"
)

# Test deleting the simple file
response = delete_file("LICENSE")
print(f"Delete LICENSE: {response.status_code} - {response.text}")

# Test deleting the file with directories
response = delete_file("dataset/test-images-only/1-1_IMG_0.HEIC")
print(
    f"Delete dataset/test-images-only/1-1_IMG_0.HEIC: {response.status_code} - {response.text}"
)
