from os import walk, path
import pandas as pd
import pyiqa
from mimetypes import guess_type
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()


def process(session):
    try:
        images_to_check = []
        for root, _, files in walk(f"./output/{session}/images"):
            for file in files:
                if guess_type(path.join(root, file))[0].startswith("image/"):
                    images_to_check.append(path.join(root, file))

        topiq_iaa = pyiqa.create_metric("topiq_iaa")
        image_quality_df = pd.DataFrame(
            columns=["group", "image_name", "image_quality"]
        )

        for file in tqdm(images_to_check):
            image_quality_df.loc[len(image_quality_df.index)] = [
                file.split("/")[-2],
                file.split("/")[-1],
                topiq_iaa(file).item(),
            ]

        # save dataframe to excel
        image_quality_df.to_excel(
            f"./output/{session}/images/image_quality.xlsx", index=False
        )
    except AssertionError as e:
        pass
    except Exception as e:
        raise e
