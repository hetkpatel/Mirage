import torch
import imageio.v3 as iio
from PIL import Image
from os import path, makedirs
from pillow_heif import register_heif_opener

import embedding_models.ResNet50_Embedding as ResNet50

register_heif_opener()

transform = ResNet50.get_transforms()
model = ResNet50.ResNet50_ImageEmbedder()
model.eval()


def create_embedding(file: str, embedding_folder: str, mimetype: str):
    if mimetype.startswith("image/"):
        return _create_embedding_for_image(file, embedding_folder)
    elif mimetype.startswith("video/"):
        return _create_embedding_for_video(file, embedding_folder)
    else:
        return False


def _create_embedding_for_video(video_file: str, embedding_folder: str):
    if not path.exists(embedding_folder):
        makedirs(embedding_folder)

    try:
        embeddings = []
        for frame in iio.imiter(video_file, plugin="pyav"):
            with torch.no_grad():
                # Transform images into tensors
                img = Image.fromarray(frame)
                t = transform(img)
                # Create embedding vector
                embedding = torch.squeeze(model(t.unsqueeze(0)))
                # Append embedding to list
                embeddings.append(embedding)

        # Save embeddings to folder
        torch.save(
            torch.mean(torch.stack(embeddings), dim=0),
            path.join(
                embedding_folder, f"{path.basename(video_file).split('.')[0]}.pt"
            ),
        )
    except Exception as e:
        print(e)
        return False

    return True


def _create_embedding_for_image(image_file: str, embedding_folder: str) -> bool:
    if not path.exists(embedding_folder):
        makedirs(embedding_folder)

    try:
        with torch.no_grad():
            # Transform images into tensors
            img = Image.open(image_file)
            t = transform(img)
            # Create embedding vector
            embedding = torch.squeeze(model(t.unsqueeze(0)))
            # Save embedding to folder
            torch.save(
                embedding,
                path.join(
                    embedding_folder, f"{path.basename(image_file).split('.')[0]}.pt"
                ),
            )
            return True
    except Exception as e:
        print(e)
        return False
