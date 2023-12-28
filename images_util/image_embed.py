import torch
from PIL import Image
from os import path, makedirs
from mimetypes import guess_type
from tqdm import tqdm
from uuid import uuid4
from json import load, dump
from pillow_heif import register_heif_opener

import ResNet50_Embedding as ie

register_heif_opener()


def process(session, input):
    try:
        model = ie.ResNet50_ImageEmbedder()

        file_list = []
        for i in input:
            file_list += _validate_source(i)

        if not path.exists(f"./.tmp/{session}/vectors"):
            makedirs(f"./.tmp/{session}/vectors")

        model.eval()
        with torch.no_grad():
            for file in tqdm(desc="Indexing vector database", iterable=file_list):
                # Transform images into tensors
                img = Image.open(file)
                t = ie.get_transforms()(img)
                # Create embedding vector
                vector = torch.squeeze(model(t.unsqueeze(0)))
                # save vector in tmp session folder (TODO: use vector database)
                id = uuid4().hex
                torch.save(vector, f"./.tmp/{session}/vectors/{id}.pt")
                # save id and file path in tmp session folder in json file
                _save_id_to_file(session, id, path.abspath(file))

    except Exception as e:
        raise e


def _validate_source(source):
    try:
        if guess_type(source)[0].startswith("image/"):
            return [source]
    except:
        pass

    return []


def _save_id_to_file(session, id, filename):
    # check if embedding map file exists, if not create it
    if not path.exists(f"./.tmp/{session}/embedding_map.json"):
        with open(f"./.tmp/{session}/embedding_map.json", "w") as f:
            dump({}, f)

    with open(f"./.tmp/{session}/embedding_map.json", "r") as j:
        data = load(j)
        data[id] = filename
        with open(f"./.tmp/{session}/embedding_map.json", "w") as f:
            dump(data, f)
