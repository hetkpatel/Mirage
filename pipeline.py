from os import walk, path, makedirs
from uuid import uuid4
from shutil import rmtree
from mimetypes import guess_type
from argparse import ArgumentParser, ArgumentTypeError

import images_util.image_embed as emb
import images_util.image_group as grp
import images_util.quality_check as qc
import images_util.order_date as od

_DEBUG = False


def is_valid_path(arg):
    if not path.exists(arg):
        raise ArgumentTypeError(f"The path '{arg}' does not exist.")
    return arg


parser = ArgumentParser(prog="LensLib")
parser.add_argument(dest="dir", type=is_valid_path, nargs="+")
parser.add_argument("--dry_run", "--dry", action="store_true")
parser.add_argument("--show_unsupported_files", "-u", action="store_true")
parser.add_argument("--quality_check", "-q", action="store_true")

args = parser.parse_args()


list_of_files = [
    path.join(root, file)
    for d in args.dir
    for root, _, files in walk(d)
    for file in files
    if file not in [".DS_Store"]
]

uf = []


def extract_type(f):
    try:
        return guess_type(f)[0].split("/")[0]
    except AttributeError:
        uf.append(f)
        return "unsupported file"


list_of_files = list(set(list_of_files))
formats = [extract_type(f) for f in list_of_files]
list_of_files = [f for f in list_of_files if f not in uf]

if len(formats) == 0:
    print("No images or video found. Exiting program...")
    exit(0)

content = [
    f"{f[1]} {f[0]}{'' if f[1] == 1 else 's'}"
    for f in [(format, formats.count(format)) for format in set(formats)]
]
print(f"Found {', '.join(content)}")
if len(uf) >= 1 and (len(uf) <= 10 or args.show_unsupported_files):
    print(f"Unsupported files:")
    print("\n".join(uf))
del formats, uf, content

DRY_RUN_CHECK = args.dry_run
if not DRY_RUN_CHECK:
    if (
        input(
            "\nWARNING: This is NOT a dry run. Continue? (Type CONTINUE to move forward, any key to cancel): "
        )
        .strip()
        .lower()
        != "continue"
    ):
        print("Canceling run...")
        exit(0)
    else:
        print(
            "------------------------------------------------------\nDRY RUN MODE DISABLED: Files or directories WILL BE modified.\n------------------------------------------------------\n"
        )
else:
    print(
        "------------------------------------------------------\nDRY RUN MODE ENABLED: No files or directories will be modified.\n------------------------------------------------------\n"
    )

if DRY_RUN_CHECK:
    exit(0)

# START ------------------------------------------------------
if not DRY_RUN_CHECK:
    session = uuid4().hex
    print(f"\nSession ID: {session}\n")
    if not path.exists(f"./.tmp/{session}"):
        makedirs(f"./.tmp/{session}")
    if not path.exists(f"./output/{session}/images"):
        makedirs(f"./output/{session}/images")
    if not path.exists(f"./output/{session}/videos"):
        makedirs(f"./output/{session}/videos")

    print("START: Creating Image Embedding")
    emb.process(session=session, input=list_of_files)
    print("FINISH")

    print("START: Grouping Images")
    grp.process(session=session, DEBUG=_DEBUG)
    print("FINISH")

    if args.quality_check:
        print("START: Image Quality Check")
        qc.process(session=session)
        print("FINISH")

    print("START: Order by Date")
    od.process(session=session)
    print("FINISH")


rmtree(f"./.tmp")
