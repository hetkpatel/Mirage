import os
import requests
from tqdm import tqdm
from argparse import ArgumentParser, ArgumentTypeError
from dotenv import load_dotenv
import csv

load_dotenv()

HOSTNAME = os.getenv("HOSTNAME")
PORT = os.getenv("PORT")


def _is_valid_path(arg):
    if not os.path.exists(arg):
        raise ArgumentTypeError(f"The path '{arg}' does not exist.")
    return arg


parser = ArgumentParser(prog="Project-Mirage")
parser.add_argument(dest="id_list", type=_is_valid_path)
parser.add_argument(dest="dir", type=_is_valid_path)
args = parser.parse_args()


def download_file(unique_id):
    url = f"http://{HOSTNAME}:{PORT}/download/{unique_id}?downloadable=true"

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        # Extract the original filename from the Content-Disposition header
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
        else:
            print(f"Could not retrieve filename for {unique_id}")
            return

        file_path = os.path.join(args.dir, filename)

        total_size = int(response.headers.get("content-length", 0))

        with open(file_path, "wb") as file, tqdm(
            desc=file_path,
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                file.write(data)
                bar.update(len(data))
    else:
        print(
            f"Failed to download file with unique_id: {unique_id}. HTTP Status code: {response.status_code}"
        )


if __name__ == "__main__":
    with open(args.id_list, "r", newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=" ", quotechar="|")
        ids = []
        for id in reader:
            ids.append(id[0])

        for i in tqdm(ids, desc="Downloading", unit="files"):
            id = i.split(".")[0]
            download_file(id)
