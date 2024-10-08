import exiftool
import requests
from datetime import datetime


def get_metadata(id_file_path: str, org_filename: str) -> dict:
    def is_valid_date_format(date_string):
        try:
            datetime.strptime(date_string, "%Y:%m:%d")
            return True
        except ValueError:
            return False

    with exiftool.ExifToolHelper() as et:
        metadata = et.get_tags(
            [id_file_path],
            tags=[
                "File:FileSize",
                "File:MIMEType",
                "File:ImageWidth",
                "File:ImageHeight",
                "PNG:ImageWidth",
                "PNG:ImageHeight",
                "QuickTime:ImageWidth",
                "QuickTime:ImageHeight",
                "EXIF:DateTimeOriginal",
                "EXIF:DateTime",
                "EXIF:DateTimeDigitized",
                "EXIF:CreateDate",
                "QuickTime:CreateDate",
                "QuickTime:ModifyDate",
                "QuickTime:TrackCreateDate",
                "QuickTime:TrackModifyDate",
                "QuickTime:MediaCreateDate",
                "QuickTime:MediaModifyDate",
                "GPSPosition",
            ],
        )[0]

        del metadata["SourceFile"]

        metadata["FileSize"] = metadata.pop("File:FileSize")
        metadata["MIMEType"] = metadata.pop("File:MIMEType")

        if "File:ImageWidth" in metadata:
            metadata["Width"] = metadata.pop("File:ImageWidth")
        elif "PNG:ImageWidth" in metadata:
            metadata["Width"] = metadata.pop("PNG:ImageWidth")
        elif "QuickTime:ImageWidth" in metadata:
            metadata["Width"] = metadata.pop("QuickTime:ImageWidth")

        metadata.pop("File:ImageWidth", None)
        metadata.pop("PNG:ImageWidth", None)
        metadata.pop("QuickTime:ImageWidth", None)

        if "File:ImageHeight" in metadata:
            metadata["Height"] = metadata.pop("File:ImageHeight")
        elif "PNG:ImageHeight" in metadata:
            metadata["Height"] = metadata.pop("PNG:ImageHeight")
        elif "QuickTime:ImageHeight" in metadata:
            metadata["Height"] = metadata.pop("QuickTime:ImageHeight")

        metadata.pop("File:ImageHeight", None)
        metadata.pop("PNG:ImageHeight", None)
        metadata.pop("QuickTime:ImageHeight", None)

        if "EXIF:DateTimeOriginal" in metadata:
            metadata["CreateDate"] = metadata.pop("EXIF:DateTimeOriginal")
        elif "EXIF:DateTime" in metadata:
            metadata["CreateDate"] = metadata.pop("EXIF:DateTime")
        elif "EXIF:DateTimeDigitized" in metadata:
            metadata["CreateDate"] = metadata.pop("EXIF:DateTimeDigitized")
        elif "EXIF:CreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("EXIF:CreateDate")
        elif "QuickTime:CreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:CreateDate")
        elif "QuickTime:ModifyDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:ModifyDate")
        elif "QuickTime:TrackCreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:TrackCreateDate")
        elif "QuickTime:TrackModifyDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:TrackModifyDate")
        elif "QuickTime:MediaCreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:MediaCreateDate")
        elif "QuickTime:MediaModifyDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:MediaModifyDate")

        metadata.pop("EXIF:DateTimeOriginal", None)
        metadata.pop("EXIF:DateTime", None)
        metadata.pop("EXIF:DateTimeDigitized", None)
        metadata.pop("EXIF:CreateDate", None)
        metadata.pop("QuickTime:CreateDate", None)
        metadata.pop("QuickTime:ModifyDate", None)
        metadata.pop("QuickTime:TrackCreateDate", None)
        metadata.pop("QuickTime:TrackModifyDate", None)
        metadata.pop("QuickTime:MediaCreateDate", None)
        metadata.pop("QuickTime:MediaModifyDate", None)

        if "CreateDate" not in metadata:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "Gemma2-MDE",
                    "stream": False,
                    "prompt": org_filename,
                },
            )
            if (
                response.json()["done"]
                and str(response.json()["done_reason"]).strip().lower() == "stop"
                and str(response.json()["response"]).strip() != "null"
                and is_valid_date_format(str(response.json()["response"]).strip())
            ):
                metadata["CreateDate"] = datetime.strptime(
                    str(response.json()["response"]).strip(), "%Y:%m:%d"
                ).strftime("%Y:%m:%d 00:00:00")
            else:
                metadata["CreateDate"] = datetime.now().strftime("%Y:%m:%d 00:00:00")

        if "Composite:GPSPosition" in metadata:
            metadata["GPSPosition"] = metadata.pop("Composite:GPSPosition")

        return metadata
