"""MMOUI/ESOUI API client — clean JSON API, no HTML scraping."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests


# ── API endpoints ─────────────────────────────────────────────────────────────

_GLOBAL_CONFIG_URL = "https://api.mmoui.com/v3/globalconfig.json"
_GAME_ID = "ESO"

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate",
})

# Resolved lazily on first use
_file_list_url: str = ""
_file_details_url: str = ""
_category_list_url: str = ""


def _init_urls() -> None:
    global _file_list_url, _file_details_url, _category_list_url
    if _file_list_url:
        return
    gc = _SESSION.get(_GLOBAL_CONFIG_URL, timeout=15).json()
    eso = next((g for g in gc.get("GAMES", []) if g.get("GameID") == _GAME_ID), None)
    if not eso:
        raise RuntimeError("ESO not found in MMOUI global config")
    game_cfg = _SESSION.get(eso["GameConfig"], timeout=15).json()
    feeds = game_cfg.get("APIFeeds", {})
    _file_list_url = feeds["FileList"]
    _file_details_url = feeds["FileDetails"]   # append "{id}.json"
    _category_list_url = feeds["CategoryList"]


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Category:
    cat_id: int
    name: str
    icon_url: str
    file_count: int


@dataclass
class RemoteAddonInfo:
    addon_id: int
    name: str              # UIName — display name
    version: str
    date: int              # UIDate unix ms timestamp
    author: str
    description: str       # filled by fetch_addon_details()
    changelog: str         # filled by fetch_addon_details()
    category_id: int
    category: str          # display name, resolved from category list
    downloads_total: int
    downloads_monthly: int
    favorites: int
    info_url: str
    download_url: str      # direct CDN zip URL, filled by fetch_addon_details()
    filename: str          # zip filename
    dirs: list[str]        # UIDir — actual folder name(s) extracted from zip
    md5: str
    thumbs: list[str]


def _to_list(value) -> list[str]:
    """Normalise UIDir/UIIMG_Thumbs — API returns str, list, or null."""
    if isinstance(value, list):
        return [v for v in value if v]
    if isinstance(value, str) and value:
        return [value]
    return []


def _strip_bbcode(text: str) -> str:
    """Remove BBCode tags from description text."""
    text = re.sub(r'\[/?[A-Za-z][^\]]*\]', '', text)
    return text.strip()


def _parse_filelist_entry(raw: dict, cats: dict[int, str]) -> RemoteAddonInfo:
    uid = int(raw.get("UID", 0))
    cat_id = int(raw.get("UICATID", 0))
    return RemoteAddonInfo(
        addon_id=uid,
        name=raw.get("UIName", ""),
        version=raw.get("UIVersion", ""),
        date=int(raw.get("UIDate", 0)),
        author=raw.get("UIAuthorName", ""),
        description="",
        changelog="",
        category_id=cat_id,
        category=cats.get(cat_id, ""),
        downloads_total=int(raw.get("UIDownloadTotal", 0)),
        downloads_monthly=int(raw.get("UIDownloadMonthly", 0)),
        favorites=int(raw.get("UIFavoriteTotal", 0)),
        info_url=raw.get("UIFileInfoURL", ""),
        download_url="",
        filename="",
        dirs=_to_list(raw.get("UIDir")),
        md5="",
        thumbs=_to_list(raw.get("UIIMG_Thumbs")),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_categories() -> list[Category]:
    _init_urls()
    data = _SESSION.get(_category_list_url, timeout=15).json()
    return [
        Category(
            cat_id=int(c["UICATID"]),
            name=c.get("UICATTitle", ""),
            icon_url=c.get("UICATICON", ""),
            file_count=int(c.get("UICATFileCount", 0)),
        )
        for c in data
    ]


def fetch_all_addons() -> list[RemoteAddonInfo]:
    """Fetch the complete addon list (~3000 items) in one request."""
    _init_urls()
    cats = {c.cat_id: c.name for c in fetch_categories()}
    data = _SESSION.get(_file_list_url, timeout=30).json()
    return [_parse_filelist_entry(raw, cats) for raw in data]


def fetch_addon_details(addon_id: int) -> dict:
    """
    Return full details for one addon: download URL, description, changelog, md5.
    Merges into a dict so callers can update their RemoteAddonInfo.
    """
    _init_urls()
    url = f"{_file_details_url}{addon_id}.json"
    data = _SESSION.get(url, timeout=15).json()
    if isinstance(data, list):
        data = data[0] if data else {}
    return {
        "download_url": data.get("UIDownload", ""),
        "filename":     data.get("UIFileName", ""),
        "md5":          data.get("UIMD5", ""),
        "description":  _strip_bbcode(data.get("UIDescription", "")),
        "changelog":    _strip_bbcode(data.get("UIChangeLog", "")),
    }


def download_zip(
    download_url: str,
    dest_path: str,
    progress_callback=None,
) -> None:
    """Stream a zip to dest_path. progress_callback(bytes_done, total) is optional."""
    with _SESSION.get(download_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                done += len(chunk)
                if progress_callback:
                    progress_callback(done, total)
