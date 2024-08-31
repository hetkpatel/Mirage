import torch
import imageio.v3 as iio
from PIL import Image
from os import path, makedirs
from mimetypes import guess_type
from pillow_heif import register_heif_opener

import embedding_models.ResNet50_Embedding as ResNet50

register_heif_opener()


def create_vector(file: str, embedding_folder: str):
    if guess_type(file)[0].startswith("image/"):
        return create_vector_for_image(file, embedding_folder)
    elif guess_type(file)[0].startswith("video/"):
        return create_vector_for_video(file, embedding_folder)
    else:
        return False


def create_vector_for_video(video_file: str, embedding_folder: str):
    # Check if image_file is actually an image file using mime
    if not guess_type(video_file)[0].startswith("video/"):
        print("Invalid video file")
        return False

    if not path.exists(
        path.join(
            embedding_folder,
            f"{path.basename(video_file).split('.')[0]}",
        )
    ):
        makedirs(
            path.join(
                embedding_folder,
                f"{path.basename(video_file).split('.')[0]}",
            )
        )

    try:
        embeddings = []
        for frame in iio.imiter(video_file, plugin="pyav"):
            model = ResNet50.ResNet50_ImageEmbedder()
            model.eval()
            with torch.no_grad():
                # Transform images into tensors
                img = Image.fromarray(frame)
                t = ResNet50.get_transforms()(img)
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


def create_vector_for_image(image_file: str, embedding_folder: str) -> bool:
    # Check if image_file is actually an image file using mime
    if not guess_type(image_file)[0].startswith("image/"):
        print("Invalid image file")
        return False

    if not path.exists(embedding_folder):
        makedirs(embedding_folder)

    try:
        model = ResNet50.ResNet50_ImageEmbedder()
        model.eval()
        with torch.no_grad():
            # Transform images into tensors
            img = Image.open(image_file)
            t = ResNet50.get_transforms()(img)
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
