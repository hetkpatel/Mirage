from torch import load as tload
from torch.nn.functional import cosine_similarity
from json import dump, load
from os import path, walk
import pyiqa

# .832104802131654 - resnet50
THRESHOLD = 0.832104802131654


def find_similar_images(vector_folder, filename_mapping_json, media_folder, output):
    clusters = {}
    files = [
        path.join(root, f) for root, _, files in walk(vector_folder) for f in files
    ]

    for file in files:
        similar_images = _calculate_cosine_delta(file, files)
        clusters[file] = list(similar_images.keys())

    def get_cluster(node):
        cluster = set()
        stack = [node]

        while stack:
            current_node = stack.pop()
            cluster.add(current_node)

            for neighbor in clusters[current_node]:
                if neighbor not in cluster:
                    stack.append(neighbor)

        return cluster

    groups = {}
    checked = set()
    for k, _ in clusters.items():
        if k not in checked:
            cluster = get_cluster(k)
            groups[len(groups)] = cluster
            checked.update(cluster)

    # save images to the .tmp/session folder in their respective groups
    similarity_results = {}
    topiq_iaa = pyiqa.create_metric("topiq_iaa")
    for _, similarImageEmbedIds in groups.items():
        imageList = []
        # Group similar images with real path
        for embedId in similarImageEmbedIds:
            id = path.basename(embedId).split(".")[0]
            org_path = [val for key, val in filename_mapping_json.items() if id in key]
            imageList.append(
                path.join(media_folder, f"{id}.{org_path[0].split('.')[-1]}")
            )

        # Find best quality image from group
        best_quality_image = ""
        best_quality = 0
        for image in imageList:
            quality = topiq_iaa(image).item()
            if quality > best_quality:
                best_quality_image = image
                best_quality = quality

        similarity_results[path.basename(best_quality_image)] = [
            path.basename(i) for i in imageList
        ]

    with open(output, "w") as f:
        dump(similarity_results, f)


def _calculate_cosine_delta(target, batch):
    result = {target: 1.0}
    target_tensor = tload(target).unsqueeze(dim=0)

    for k in batch:
        if k != target:
            cos_sim = cosine_similarity(target_tensor, tload(k).unsqueeze(dim=0))[
                0
            ].item()
            if cos_sim >= THRESHOLD:
                result[k] = cos_sim

    return result
