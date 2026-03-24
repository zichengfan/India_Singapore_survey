#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path


SCENE_ORDER = ["Campus", "Commercial", "Highway", "Industrial", "Residential"]
COUNTRY_ORDER = ["Singapore", "India"]
COUNTRY_CODE = {"Singapore": "SG", "India": "IND"}
SCENE_CODE = {
    "Campus": "CAM",
    "Commercial": "COM",
    "Highway": "HWY",
    "Industrial": "IND",
    "Residential": "RES",
}
SET_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate image pool CSV for survey uploads."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to the repository root.",
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="Git commit hash used to build permanent raw.githubusercontent.com links.",
    )
    parser.add_argument(
        "--owner",
        default="zichengfan",
        help="GitHub owner or org name.",
    )
    parser.add_argument(
        "--repo",
        default="India_Singapore_survey",
        help="GitHub repository name.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to Survey_sample_images/image_pool.csv",
    )
    parser.add_argument(
        "--question-output",
        type=Path,
        default=None,
        help="Output CSV path for one-row-per-set survey imports. Defaults to Survey_sample_images/question_sets.csv",
    )
    return parser.parse_args()


def build_url(owner: str, repo: str, commit: str, rel_path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{rel_path}"


def collect_images(images_root: Path) -> dict[str, dict[str, list[Path]]]:
    grouped: dict[str, dict[str, list[Path]]] = {country: {} for country in COUNTRY_ORDER}
    for country in COUNTRY_ORDER:
        country_dir = images_root / country
        for path in sorted(country_dir.iterdir()):
            if not path.is_file() or path.name == ".DS_Store":
                continue
            scene = path.stem.split("_", 1)[0]
            grouped[country].setdefault(scene, []).append(path)
    return grouped


def validate_groups(grouped: dict[str, dict[str, list[Path]]]) -> int:
    expected_count = None
    for country in COUNTRY_ORDER:
        for scene in SCENE_ORDER:
            images = grouped.get(country, {}).get(scene, [])
            if not images:
                raise ValueError(f"Missing images for {country}/{scene}")
            if expected_count is None:
                expected_count = len(images)
            elif len(images) != expected_count:
                raise ValueError(
                    f"Inconsistent image counts. {country}/{scene} has {len(images)} "
                    f"images, expected {expected_count}."
                )
    assert expected_count is not None
    if expected_count > len(SET_LABELS):
        raise ValueError("Too many sets for built-in labels.")
    return expected_count


def make_image_id(country: str, scene: str, path: Path) -> str:
    suffix = path.stem.split("_", 1)[1]
    return f"{COUNTRY_CODE[country]}_{SCENE_CODE[scene]}_{suffix}"


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    images_root = repo_root / "Survey_sample_images"
    output_path = args.output or images_root / "image_pool.csv"
    question_output_path = args.question_output or images_root / "question_sets.csv"

    grouped = collect_images(images_root)
    set_count = validate_groups(grouped)

    rows: list[dict[str, str]] = []
    question_rows: list[dict[str, str]] = []
    for set_index in range(set_count):
        set_label = SET_LABELS[set_index]
        question_row: dict[str, str] = {"image_set": set_label}
        for country in COUNTRY_ORDER:
            for scene in SCENE_ORDER:
                path = grouped[country][scene][set_index]
                rel_path = path.relative_to(repo_root).as_posix()
                image_id = make_image_id(country, scene, path)
                image_url = build_url(args.owner, args.repo, args.commit, rel_path)
                rows.append(
                    {
                        "image_id": image_id,
                        "image_url": image_url,
                        "scene_type": scene,
                        "country": country,
                        "image_set": set_label,
                        "notes": "",
                    }
                )
                country_prefix = "sg" if country == "Singapore" else "ind"
                scene_prefix = scene.lower()
                question_row[f"{country_prefix}_{scene_prefix}_id"] = image_id
                question_row[f"{country_prefix}_{scene_prefix}_url"] = image_url
        question_rows.append(question_row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_id", "image_url", "scene_type", "country", "image_set", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    question_fieldnames = ["image_set"]
    for country in COUNTRY_ORDER:
        country_prefix = "sg" if country == "Singapore" else "ind"
        for scene in SCENE_ORDER:
            scene_prefix = scene.lower()
            question_fieldnames.append(f"{country_prefix}_{scene_prefix}_id")
            question_fieldnames.append(f"{country_prefix}_{scene_prefix}_url")

    with question_output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=question_fieldnames)
        writer.writeheader()
        writer.writerows(question_rows)


if __name__ == "__main__":
    main()
