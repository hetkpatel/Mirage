# LensLib

LensLib is a command-line utility designed to organize and process photos and videos in a specified directory or directories. The project provides functionalities such as duplicate detection, culling, and organization.

## Features

- **Photos and Videos**: LensLib can organize photos and videos. Works on multiple formats such as `JPEG`, `PNG`, `HEIC/HEIF` (iOS format), `MP4`, and `MOV`.

- **Duplicate Grouping**: Groups photos and videos based on specific criteria, enhancing the organization and accessibility of the files.

- **Image Aesthetics Assessment**: Using Vision Neural Models, LensLibs can calculate which image from duplicates looks the best and cull them from the others.

## Usage

### Prerequisites

#### Software

- Python 3.x
- Required Python packages: `torch`, `torchvision`, `Pillow`, `pillow_heif`, `pyiqa`, `mimetypes`, `argparse`, `uuid`, `tqdm` (all packages can be installed with `requirements.txt`)

#### Hardware

- At least 4GB of memory for vector embeddings
- Capable processor for vision models (CNNs like ResNet or VGG19)

I ran this on a Raspberry Pi 4 8GB with a 128GB SD card running Raspbian with Python 3.11.2 without any issues.

### Installation

Clone the repository and install the required dependencies:

```bash
$ git clone https://github.com/hetkpatel/LensLib.git
$ cd LensLib
$ pip install -r requirements.txt
```

### Run

```bash
$ python pipeline.py [dir] [--dry_run] [--show_unsupported_files] [--quality_check]
```

#### Arguments

- `dir`: One or more directory paths containing the images and videos to be processed. LensLib will crawl through all sub-directories from the parent directory and find all photos and videos to process.

- `--dry_run` (`-d`): Perform a dry run without any modifications. Useful for previewing changes.

- `--show_unsupported_files` (`-u`): Display unsupported files during execution.

- `--quality_check` (`-q`): Enable image quality checking.

### Example

```bash
$ python pipeline.py /path/to/images --dry_run --show_unsupported_files --quality_check
```

## Output

LensLib generates an organized output structure in the current working directory:

- `./output/{session}/images`: Processed and grouped images.
  
- `./output/{session}/videos`: Processed and grouped videos.

## CAUTION!!!

Use caution when running LensLib without the `--dry_run` option, as it will modify files and directories. Always review the dry run output before proceeding with actual modifications.

## License

This project is licensed under the GNU AGPLv3 License - see the [LICENSE](LICENSE) file for details.