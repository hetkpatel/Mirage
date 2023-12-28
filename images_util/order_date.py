from os import listdir, path, walk, makedirs
from shutil import move
from mimetypes import guess_type
from PIL import Image
from PIL.ExifTags import TAGS
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()


def process(session):
    for batch in tqdm(
        [
            (path.join(f"./output/{session}/images", d), d)
            for d in listdir(f"./output/{session}/images")
            if path.isdir(f"./output/{session}/images/{d}")
        ]
    ):
        for root, _, files in walk(batch[0]):
            for f in files:
                f = path.join(root, f)
                if guess_type(f)[0].startswith("image/"):
                    img = Image.open(f)
                    exif = img.getexif().get_ifd(0x8769)
                    for tag, value in exif.items():
                        if TAGS.get(tag) == "DateTimeOriginal":
                            year = value[:4]
                            if not path.exists(
                                f"./output/{session}/images/{batch[1]}/{year}"
                            ):
                                makedirs(f"./output/{session}/images/{batch[1]}/{year}")
                            move(
                                f,
                                f"./output/{session}/images/{batch[1]}/{year}/{path.basename(f)}",
                            )
                            break
