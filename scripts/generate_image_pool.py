#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


SCENE_ORDER = ["Campus", "Commercial", "Highway", "Industrial", "Residential"]
COUNTRY_ORDER = ["India", "Singapore"]
COUNTRY_CODE = {"Singapore": "SG", "India": "IND"}
SCENE_CODE = {
    "Campus": "CAM",
    "Commercial": "COM",
    "Highway": "HWY",
    "Industrial": "IND",
    "Residential": "RES",
}
SET_LABELS_BY_COUNTRY = {"India": "ABCDE", "Singapore": "FGHIJ"}
IMAGES_PER_SCENE = 5


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
        "--git-ref",
        "--commit",
        dest="git_ref",
        default=None,
        help=(
            "Git ref used to build raw.githubusercontent.com links. "
            "Defaults to the current branch name, or HEAD commit if detached."
        ),
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
        help="Output CSV path. Defaults to Survey_sample_images/image_pool.csv.",
    )
    parser.add_argument(
        "--question-output",
        type=Path,
        default=None,
        help=(
            "Output CSV path for one-row-per-set survey imports. "
            "Defaults to Survey_sample_images/question_sets.csv."
        ),
    )
    parser.add_argument(
        "--images-root",
        type=Path,
        default=None,
        help="Image source directory. Defaults to Survey_Images.",
    )
    return parser.parse_args()


def build_url(owner: str, repo: str, git_ref: str, rel_path: str) -> str:
    return f"raw.githubusercontent.com/{owner}/{repo}/{git_ref}/{rel_path}"


def collect_images(images_root: Path) -> dict[str, dict[str, list[Path]]]:
    grouped: dict[str, dict[str, list[Path]]] = {country: {} for country in COUNTRY_ORDER}
    for country in COUNTRY_ORDER:
        country_dir = images_root / country
        if not country_dir.is_dir():
            raise ValueError(f"Missing country directory: {country_dir}")
        for scene in SCENE_ORDER:
            scene_dir = country_dir / scene
            if not scene_dir.is_dir():
                raise ValueError(f"Missing scene directory: {scene_dir}")
            images = [
                path
                for path in sorted(scene_dir.iterdir())
                if path.is_file() and path.name != ".DS_Store"
            ]
            grouped[country][scene] = images
    return grouped


def validate_groups(grouped: dict[str, dict[str, list[Path]]]) -> None:
    for country in COUNTRY_ORDER:
        for scene in SCENE_ORDER:
            images = grouped.get(country, {}).get(scene, [])
            if len(images) < IMAGES_PER_SCENE:
                raise ValueError(
                    f"Not enough images for {country}/{scene}. "
                    f"Found {len(images)}, need at least {IMAGES_PER_SCENE}."
                )
        if len(SET_LABELS_BY_COUNTRY[country]) < IMAGES_PER_SCENE:
            raise ValueError(f"Not enough set labels configured for {country}.")


def make_image_id(country: str, scene: str, path: Path) -> str:
    stem_parts = path.stem.split("_", 1)
    suffix = stem_parts[1] if len(stem_parts) > 1 else stem_parts[0]
    return f"{COUNTRY_CODE[country]}_{SCENE_CODE[scene]}_{suffix}"


def resolve_git_ref(repo_root: Path, git_ref: str | None) -> str:
    if git_ref:
        return git_ref

    branch = subprocess.check_output(
        ["git", "-C", str(repo_root), "branch", "--show-current"],
        text=True,
    ).strip()
    if branch:
        return branch

    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    git_ref = resolve_git_ref(repo_root, args.git_ref)
    images_root = (args.images_root or (repo_root / "Survey_Images")).resolve()
    sample_root = repo_root / "Survey_sample_images"
    output_path = args.output or sample_root / "image_pool.csv"
    question_output_path = args.question_output or sample_root / "question_sets.csv"

    grouped = collect_images(images_root)
    validate_groups(grouped)

    question_fieldnames = ["image_set"]
    for country in COUNTRY_ORDER:
        country_prefix = "sg" if country == "Singapore" else "ind"
        for scene in SCENE_ORDER:
            scene_prefix = scene.lower()
            question_fieldnames.append(f"{country_prefix}_{scene_prefix}_id")
            question_fieldnames.append(f"{country_prefix}_{scene_prefix}_url")

    rows: list[dict[str, str]] = []
    question_rows: list[dict[str, str]] = []
    for country in COUNTRY_ORDER:
        for set_index, set_label in enumerate(SET_LABELS_BY_COUNTRY[country][:IMAGES_PER_SCENE]):
            question_row: dict[str, str] = {fieldname: "" for fieldname in question_fieldnames}
            question_row["image_set"] = set_label
            for scene in SCENE_ORDER:
                path = grouped[country][scene][set_index]
                rel_path = path.relative_to(repo_root).as_posix()
                image_id = make_image_id(country, scene, path)
                image_url = build_url(args.owner, args.repo, git_ref, rel_path)
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

    with question_output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=question_fieldnames)
        writer.writeheader()
        writer.writerows(question_rows)


if __name__ == "__main__":
    main()
