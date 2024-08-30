from os import walk, path, makedirs
from uuid import uuid4
from shutil import rmtree
import sys
from mimetypes import guess_type
from argparse import ArgumentParser, ArgumentTypeError

import images_pipeline.image_embed as iemb
import images_pipeline.image_group as igrp
import images_pipeline.quality_check as iqc
import images_pipeline.order_date as iord


def main():
    # Grab arguments
    def _is_valid_path(arg):
        if not path.exists(arg):
            raise ArgumentTypeError(f"The path '{arg}' does not exist.")
        return arg

    parser = ArgumentParser(prog="Project-Mirage")
    parser.add_argument(dest="dir", type=_is_valid_path, nargs="+")
    parser.add_argument("--dry_run", "--dry", action="store_true")
    parser.add_argument("--show_unsupported_files", "-u", action="store_true")
    parser.add_argument("--quality_check", "-q", action="store_true")
    parser.add_argument("--order_by_date", "-o", action="store_true")
    args = parser.parse_args()

    # Build list of images and videos
    print(f"Walking directory: {args.dir}")
    # AVOID certain files/directories (e.g. .DS_Store)
    list_of_files = [
        path.join(root, file)
        for d in args.dir
        for root, _, files in walk(d)
        for file in files
        if file not in [".DS_Store"]
    ]

    unsupported_files = []
    image_flag = video_flag = False

    def _extract_type(f):
        nonlocal image_flag, video_flag
        try:
            format_type = guess_type(f)[0].split("/")[0]
            if format_type == "image":
                image_flag = True
                return "image"
            elif format_type == "video":
                video_flag = True
                return "video"
            else:
                unsupported_files.append(f)
                return "unsupported file"
        except AttributeError:
            unsupported_files.append(f)
            return "unsupported file"

    # Remove duplicates
    list_of_files = list(set(list_of_files))
    # Extract file formats from video, images, etc.
    formats = [_extract_type(f) for f in list_of_files]
    # Some files may be unsupported (OS dependent)
    list_of_files = [f for f in list_of_files if f not in unsupported_files]

    # If no files are found than exit program
    if len(list_of_files) == 0:
        print("No files found to process. Exiting program...")
        sys.exit(0)

    # Output total number of files found grouped by formats
    content = [
        f"{f[1]} {f[0]}{'' if f[1] == 1 else 's'}"
        for f in [(format, formats.count(format)) for format in set(formats)]
    ]
    print(f"Found {', '.join(content)}")
    # Output total unsupported files and (if args) list them out
    if len(unsupported_files) >= 1 and (
        len(unsupported_files) <= 10 or args.show_unsupported_files
    ):
        print(f"Unsupported files:")
        print("\n".join(unsupported_files))
    # Clean up
    del formats, unsupported_files, content

    # CHECK DRY RUN REQUIREMENT
    # DRY_RUN_CHECK = False
    DRY_RUN_CHECK = args.dry_run
    if DRY_RUN_CHECK:
        print(
            "------------------------------------------------------\n"
            + "DRY RUN MODE ENABLED: No files or directories will be modified.\n"
            + "------------------------------------------------------\n"
        )
        sys.exit(0)

    if (
        input(
            "\nWARNING: This is NOT a dry run. Continue? (Type CONTINUE to move forward, any key to cancel): "
        )
        .strip()
        .lower()
        != "continue"
    ):
        print("Canceling run...")
        sys.exit(0)
    print(
        "------------------------------------------------------\n"
        + "DRY RUN MODE DISABLED: Files or directories WILL BE modified.\n"
        + "------------------------------------------------------\n"
    )

    # START ------------------------------------------------------
    if not DRY_RUN_CHECK:  # Extra layer of check
        # Create session ID
        session = uuid4().hex
        print(f"\nSession ID: {session}\n")

        # Make 'tmp' folder
        if not path.exists(f"./.tmp/{session}/i"):
            makedirs(f"./.tmp/{session}/i")
        if not path.exists(f"./.tmp/{session}/v"):
            makedirs(f"./.tmp/{session}/v")

        # Make 'output' folder
        if not path.exists(f"./output/{session}/images"):
            makedirs(f"./output/{session}/images")
        if not path.exists(f"./output/{session}/videos"):
            makedirs(f"./output/{session}/videos")

        if video_flag:
            pass
        else:
            print("Skipping videos since no video files found\n")

        if image_flag:
            # Start Image Embedding
            print("START: Creating Image Embedding")
            iemb.process(session=session, input=list_of_files)
            print("FINISH\n")

            # Start Image Embedding
            print("START: Grouping Images")
            igrp.process(session=session)
            print("FINISH\n")

            if args.quality_check:
                print("START: Image Quality Check")
                iqc.process(session=session)
                print("FINISH\n")

            if args.order_by_date:
                print("START: Order by Date")
                iord.process(session=session)
                print("FINISH\n")
        else:
            print("Skipping images since no video files found\n")

    # rmtree(f"./.tmp")


if __name__ == "__main__":
    main()
