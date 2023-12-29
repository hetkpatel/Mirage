from os import walk, path
import pandas as pd
import pyiqa
from mimetypes import guess_type
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()


def process(session):
    topiq_iaa = pyiqa.create_metric("topiq_iaa")
    image_quality_df = pd.DataFrame(columns=["group", "image_name", "image_quality"])

    def _is_valid_type(f):
        try:
            return guess_type(f)[0].startswith("image/")
        except:
            return False

    try:
        images_to_check = [
            path.join(root, f)
            for root, _, files in walk(f"./output/{session}/images")
            for f in files
            if _is_valid_type(path.join(root, f))
        ]

        for f in tqdm(images_to_check):
            try:
                image_quality_df.loc[len(image_quality_df.index)] = [
                    f.split("/")[-2],
                    f.split("/")[-1],
                    topiq_iaa(f).item(),
                ]
            except AssertionError:
                image_quality_df.loc[len(image_quality_df.index)] = [
                    f.split("/")[-2],
                    f.split("/")[-1],
                    pd.NA,
                ]
                continue

    except Exception as e:
        raise e

    # save dataframe to excel
    image_quality_df.to_excel(
        f"./output/{session}/images/image_quality.xlsx", index=False
    )
