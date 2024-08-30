import exiftool


def get_metadata(file_path: str) -> dict:
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_tags(
            [file_path],
            tags=["EXIF:CreateDate", "QuickTime:CreateDate", "GPSPosition"],
        )[0]

        # Clean metadata fields
        del metadata["SourceFile"]

        if "EXIF:CreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("EXIF:CreateDate")
        elif "QuickTime:CreateDate" in metadata:
            metadata["CreateDate"] = metadata.pop("QuickTime:CreateDate")

        if "Composite:GPSPosition" in metadata:
            metadata["GPSPosition"] = metadata.pop("Composite:GPSPosition")

        return metadata
