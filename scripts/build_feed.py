#!/usr/bin/env python3
"""
Generate a webЯcade feed from the cached metadata produced by RGSX.

The script expects the RGSX cache directory (default: /mnt/rgsx/saves/ports/RGSX)
to contain:
  - systems_list.json
  - games/<System>.json

Environment variables:
  RGSX_DATA_PATH       Base path for the RGSX cache (default /mnt/rgsx/saves/ports/RGSX).
  RGSX_SYSTEMS_FILE    Override path to systems_list.json.
  SYSTEM_MAPPING_PATH  Path to JSON mapping of RGSX system name -> webЯcade type.
  FEED_OUTPUT_PATH     Output path for generated feed JSON.
  FEED_TITLE           Feed title string.
  FEED_DESCRIPTION     Feed description string.
  FEED_CATEGORY_PREFIX Optional string prefixed to each category title.
  ROM_PREFIX_URL       Optional base URL used when game metadata lacks a fully-qualified URL.
  NEOGEO_BIOS_URL      URL to Neo Geo BIOS file (neogeo.zip) required for Neo Geo games.
  PSX_BIOS_URLS        Comma-separated URLs to PlayStation BIOS files (scph5500.bin,scph5501.bin,scph5502.bin).

Command line flags:
  --dry-run            Do not write feed file; emit to stdout instead.
  --log-level LEVEL    Override log level (default INFO).
  --once               Accepted for compatibility with entrypoint scripts (no functional change).
"""

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union
from urllib.parse import unquote


DEFAULT_RGSX_PATH = Path("/mnt/rgsx/saves/ports/RGSX")
DEFAULT_OUTPUT_PATH = Path("/var/www/html/content/feeds/rgsx_feed.json")


@dataclass
class Config:
    rgsx_base: Path
    systems_file: Path
    games_dir: Path
    mapping_path: Path
    output_path: Path
    feed_title: str
    feed_description: str
    category_prefix: str
    rom_prefix_url: Optional[str]
    neogeo_bios_url: Optional[str]
    psx_bios_urls: Optional[List[str]]


def load_json(path: Path) -> Optional[Iterable]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        logging.error("File not found: %s", path)
    except json.JSONDecodeError as exc:
        logging.error("Failed to parse JSON from %s: %s", path, exc)
    except OSError as exc:
        logging.error("Failed to read %s: %s", path, exc)
    return None


def build_config() -> Config:
    rgsx_base = Path(os.environ.get("RGSX_DATA_PATH", DEFAULT_RGSX_PATH))
    systems_file = Path(os.environ.get("RGSX_SYSTEMS_FILE", rgsx_base / "systems_list.json"))
    games_dir = rgsx_base / "games"
    mapping_path = Path(os.environ.get("SYSTEM_MAPPING_PATH", "/opt/rgsx/system_mapping.json"))
    output_path = Path(os.environ.get("FEED_OUTPUT_PATH", DEFAULT_OUTPUT_PATH))
    feed_title = os.environ.get("FEED_TITLE", "RGSX Library")
    feed_description = os.environ.get(
        "FEED_DESCRIPTION", f"Generated from RGSX caches on {datetime.utcnow().isoformat()}Z"
    )
    category_prefix = os.environ.get("FEED_CATEGORY_PREFIX", "")
    rom_prefix_url = os.environ.get("ROM_PREFIX_URL")
    neogeo_bios_url = os.environ.get(
        "NEOGEO_BIOS_URL",
        "https://archive.org/download/neogeoaesmvscomplete/BIOS/neogeo.zip"
    )

    # PlayStation BIOS files (can be comma-separated list)
    psx_bios_env = os.environ.get(
        "PSX_BIOS_URLS",
        "https://psx.arthus.net/roms/bios/scph5500.bin,https://psx.arthus.net/roms/bios/scph5501.bin,https://psx.arthus.net/roms/bios/scph5502.bin"
    )
    psx_bios_urls = [url.strip() for url in psx_bios_env.split(",") if url.strip()] if psx_bios_env else None

    return Config(
        rgsx_base=rgsx_base,
        systems_file=systems_file,
        games_dir=games_dir,
        mapping_path=mapping_path,
        output_path=output_path,
        feed_title=feed_title,
        feed_description=feed_description,
        category_prefix=category_prefix,
        rom_prefix_url=rom_prefix_url.rstrip("/") if rom_prefix_url else None,
        neogeo_bios_url=neogeo_bios_url,
        psx_bios_urls=psx_bios_urls,
    )


ROM_EXT_RE = re.compile(r"\.(zip|7z|chd|rar|iso|bin|cue|gba|gbc|gb|nes|sfc|smc|smd|md|pce|iso|img)$", re.IGNORECASE)


def map_system_name(system: Dict, mapping: Dict[str, str]) -> Optional[str]:
    name = system.get("name") or system.get("platform_name")
    if not name:
        return None

    mapped = mapping.get(name)
    if mapped:
        return mapped

    folder = system.get("folder")
    if folder:
        mapped = mapping.get(folder) or mapping.get(folder.lower())
        if mapped:
            logging.debug("Using folder mapping %s -> %s", folder, mapped)
            return mapped

    # Attempt case-insensitive lookup when exact match fails.
    lowered = name.lower()
    for key, value in mapping.items():
        if key.lower() == lowered:
            logging.debug("Using case-insensitive mapping %s -> %s", key, value)
            return value

    logging.warning("System '%s' is not mapped; skipping.", name)
    return None


def resolve_rom_url(game: Dict, rom_prefix: Optional[str]) -> Optional[str]:
    url = game.get("url") or game.get("rom") or game.get("href")
    if url:
        return url

    if rom_prefix:
        candidate = game.get("path") or game.get("rom_path")
        if candidate:
            return f"{rom_prefix}/{candidate.lstrip('/')}"

    return None


def extract_thumbnail(game: Dict) -> Optional[str]:
    return game.get("img") or game.get("thumbnail") or game.get("image")


def extract_background(game: Dict) -> Optional[str]:
    return game.get("background") or game.get("banner") or game.get("screenshot")


def normalize_game_entry(entry: Union[Dict, List, str]) -> Dict:
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, list):
        normalized: Dict[str, str] = {}
        if entry:
            normalized["title"] = entry[0]
        if len(entry) > 1:
            normalized["url"] = entry[1]
        if len(entry) > 2:
            normalized["size"] = entry[2]
        return normalized
    if isinstance(entry, str):
        return {"title": entry}
    return {}


def derive_title_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    segment = unquote(url.split("/")[-1])
    return os.path.splitext(segment)[0] or segment


def clean_title(raw_title: Optional[str], rom_url: Optional[str]) -> Optional[str]:
    candidate = (raw_title or "").strip()
    if candidate:
        candidate = ROM_EXT_RE.sub("", candidate).strip()
    if not candidate and rom_url:
        candidate = ROM_EXT_RE.sub("", derive_title_from_url(rom_url) or "").strip()
    return candidate or None


def build_items(
    games: Iterable[Dict], system_type: str, rom_prefix: Optional[str]
) -> List[Dict]:
    items: List[Dict] = []

    for raw_game in games:
        game = normalize_game_entry(raw_game)
        rom_url = resolve_rom_url(game, rom_prefix)
        title = clean_title(game.get("title") or game.get("name"), rom_url)

        if not title or not rom_url:
            logging.debug("Skipping game with missing title/url: %s", game)
            continue

        item = {
            "title": title,
            "type": system_type,
            "props": {
                "rom": rom_url,
            },
        }

        thumbnail = extract_thumbnail(game)
        if thumbnail:
            item["thumbnail"] = thumbnail

        background = extract_background(game)
        if background:
            item["background"] = background

        items.append(item)

    return items


def generate_feed(config: Config, *, dry_run: bool) -> int:
    systems = load_json(config.systems_file)
    if systems is None:
        logging.error("Unable to load systems list.")
        return 1

    mapping = load_json(config.mapping_path)
    if mapping is None:
        logging.error("Unable to load system mapping.")
        return 1

    feed = {
        "title": config.feed_title,
        "longTitle": config.feed_title,
        "description": config.feed_description,
        "categories": [],
    }

    # Add feed-level properties for systems that require BIOS files
    feed_props = {}
    if config.neogeo_bios_url:
        feed_props["neogeo_bios"] = config.neogeo_bios_url
    if config.psx_bios_urls:
        feed_props["psx_bios"] = config.psx_bios_urls
    if feed_props:
        feed["props"] = feed_props

    for system in systems:
        system_type = map_system_name(system, mapping)
        if not system_type:
            continue

        system_name = system.get("platform_name") or system.get("name") or "Unknown"
        games_file = config.games_dir / f"{system_name}.json"
        games = load_json(games_file)
        if games is None:
            logging.warning("Skipping system '%s'; games file missing or invalid.", system_name)
            continue

        items = build_items(games, system_type, config.rom_prefix_url)
        if not items:
            logging.info("No valid games for system '%s'; skipping.", system_name)
            continue

        category_title = f"{config.category_prefix}{system_name}"
        feed["categories"].append({"title": category_title, "items": items})

    if not feed["categories"]:
        logging.error("No categories generated; feed will not be written.")
        return 1

    if dry_run:
        print(json.dumps(feed, indent=2))
        return 0

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with config.output_path.open("w", encoding="utf-8") as handle:
            json.dump(feed, handle, indent=2)
            logging.info("Feed written to %s", config.output_path)
    except OSError as exc:
        logging.error("Failed to write feed: %s", exc)
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a webЯcade feed from RGSX caches.")
    parser.add_argument("--dry-run", action="store_true", help="Emit feed to stdout instead of writing.")
    parser.add_argument("--log-level", default="INFO", help="Set log level (DEBUG, INFO, WARNING, ...).")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Accepted for compatibility with scheduling scripts (no functional change).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = build_config()

    logging.debug("Configuration: %s", config)
    return generate_feed(config, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
