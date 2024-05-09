from torch import load as tload
from torch.nn.functional import cosine_similarity as cos
from tqdm import tqdm
from json import dump, load
from os import path, walk, makedirs
from shutil import copy
from uuid import uuid4

# .832104802131654 - resnet50
THRESHOLD = 0.832104802131654


def process(session, DEBUG):
    clusters = {}

    if DEBUG:
        delta_table = {}

    files = [
        path.join(root, f)
        for root, _, files in walk(f"./.tmp/{session}/vectors/")
        for f in files
    ]

    for file in tqdm(desc="Finding duplicates", iterable=files):
        similar_images = _calculate_cosine_delta(file, files)
        clusters[file] = list(similar_images.keys())
        if DEBUG:
            delta_table[file] = similar_images

    if DEBUG:
        # output delta_table to a json file
        with open(f"./.tmp/{session}/delta_table.json", "w") as f:
            dump(delta_table, f)

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
    with open(f"./.tmp/{session}/embedding_map.json", "r") as em:
        embedding_map = load(em)
        for k, v in groups.items():
            folder = path.join(
                f"./output/{session}/images/", uuid4().hex if len(v) != 1 else "single"
            )
            if not path.exists(folder):
                makedirs(folder)
            for f in v:
                id = path.basename(f).split(".")[0]
                org_path = embedding_map[id]
                copy(
                    org_path,
                    path.join(
                        folder,
                        path.basename(org_path)[: path.basename(org_path).rfind(".")]
                        + f".{id[:16]}"
                        + path.basename(org_path)[path.basename(org_path).rfind(".") :],
                    ),
                )


def _calculate_cosine_delta(target, batch):
    result = {target: 1.0}
    target_tensor = tload(target).unsqueeze(dim=0)

    for k in batch:
        if k != target:
            cos_sim = cos(target_tensor, tload(k).unsqueeze(dim=0))[0].item()
            if cos_sim >= THRESHOLD:
                result[k] = cos_sim

    return result
