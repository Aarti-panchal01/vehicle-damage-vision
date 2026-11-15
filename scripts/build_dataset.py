"""Build the Role 1 evaluation image set from public Kaggle datasets.

Reads data/cardd_eval/labels.json, downloads each source image from Kaggle
(needs ~/.kaggle/kaggle.json), resizes it, applies the listed synthetic
degradation, and writes data/cardd_eval/images/<image_id>.jpg.

Usage:
    python scripts/build_dataset.py --raw-dir ../vehicle-claim-genai-raw
"""

from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = REPO_ROOT / "data" / "cardd_eval" / "labels.json"
IMAGES_DIR = REPO_ROOT / "data" / "cardd_eval" / "images"
MAX_SIDE_PX = 1024

KAGGLE_SOURCES = {
    "cardd": ("gabrielfcarvalho/cardd-with-yolo-annotations-images-labels", "test/images/{name}"),
    "car_damage_assessment": ("hamzamanssor/car-damage-assessment", "image/{name}"),
}


def download_source_image(source: str, source_file: str, raw_dir: Path) -> Path:
    """Download one source image from Kaggle unless it is already cached in raw_dir."""
    target_dir = raw_dir / source
    target_path = target_dir / source_file
    if target_path.exists():
        return target_path
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    dataset, path_template = KAGGLE_SOURCES[source]
    target_dir.mkdir(parents=True, exist_ok=True)
    api.dataset_download_file(dataset, path_template.format(name=source_file), path=str(target_dir), quiet=True)
    zipped = target_dir / (source_file + ".zip")
    if zipped.exists():
        import zipfile

        with zipfile.ZipFile(zipped) as archive:
            archive.extractall(target_dir)
        zipped.unlink()
    return target_path


def resize_to_max_side(image: Image.Image, max_side: int = MAX_SIDE_PX) -> Image.Image:
    """Shrink an image so its longest side is at most max_side pixels."""
    scale = max_side / max(image.size)
    if scale >= 1:
        return image
    new_size = (round(image.width * scale), round(image.height * scale))
    return image.resize(new_size, Image.LANCZOS)


def apply_degradation(image: Image.Image, degradation: str | None) -> Image.Image:
    """Apply a named synthetic quality degradation used to build the bad-photo cases."""
    if degradation is None:
        return image
    if degradation.startswith("gaussian_blur_r"):
        radius = float(degradation.removeprefix("gaussian_blur_r"))
        return image.filter(ImageFilter.GaussianBlur(radius))
    if degradation.startswith("darken_"):
        factor = float(degradation.removeprefix("darken_"))
        return ImageEnhance.Brightness(image).enhance(factor)
    if degradation.startswith("lowres_"):
        size_part, quality_part = degradation.removeprefix("lowres_").split("_jpeg")
        small = image.copy()
        small.thumbnail((int(size_part), int(size_part)))
        buffer = BytesIO()
        small.save(buffer, format="JPEG", quality=int(quality_part))
        return Image.open(BytesIO(buffer.getvalue())).convert("RGB")
    raise ValueError(f"Unknown degradation: {degradation}")


def build(raw_dir: Path) -> int:
    """Build every image listed in labels.json and return how many were written."""
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for item in labels["items"]:
        source_path = download_source_image(item["source"], item["source_file"], raw_dir)
        image = Image.open(source_path).convert("RGB")
        image = apply_degradation(resize_to_max_side(image), item["degradation"])
        image.save(IMAGES_DIR / f"{item['image_id']}.jpg", format="JPEG", quality=88)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=REPO_ROOT.parent / "vehicle-claim-genai-raw")
    args = parser.parse_args(argv)
    count = build(args.raw_dir)
    print(f"Wrote {count} images to {IMAGES_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
