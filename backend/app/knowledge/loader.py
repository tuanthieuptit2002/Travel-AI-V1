"""Load markdown/text travel knowledge documents from disk."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.knowledge.models import LoadedDocument

_DESTINATION_ALIASES = {
    "hanoi": "Hanoi",
    "danang": "Da Nang",
    "da-nang": "Da Nang",
    "hoian": "Hoi An",
    "hoi-an": "Hoi An",
    "dalat": "Da Lat",
    "da-lat": "Da Lat",
    "nhatrang": "Nha Trang",
    "nha-trang": "Nha Trang",
    "phuquoc": "Phu Quoc",
    "phu-quoc": "Phu Quoc",
    "halong": "Ha Long",
    "ha-long": "Ha Long",
    "hochiminh": "Ho Chi Minh City",
    "ho-chi-minh": "Ho Chi Minh City",
    "saigon": "Ho Chi Minh City",
}

_CATEGORY_FOLDERS = {
    "food": "food",
    "transportation": "transportation",
    "travel_tips": "travel_tips",
    "culture": "culture",
    "safety": "safety",
    "seasonal": "seasonal",
}


def load_knowledge_documents(root: Path | str) -> List[LoadedDocument]:
    root_path = Path(root)
    if not root_path.exists():
        return []

    documents: List[LoadedDocument] = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        relative = path.relative_to(root_path).as_posix()
        destination = _destination_from_path(relative)
        category = _category_from_path(relative)
        title = _title_from_content(text) or path.stem.replace("-", " ").replace("_", " ").title()
        documents.append(
            LoadedDocument(
                title=title,
                content=text,
                source=relative,
                destination=destination,
                category=category,
                metadata={"path": relative, "filename": path.name},
            )
        )
    return documents


def _destination_from_path(relative: str) -> Optional[str]:
    parts = relative.lower().split("/")
    if len(parts) >= 2 and parts[0] == "vietnam":
        return _DESTINATION_ALIASES.get(parts[1])
    for part in parts:
        if part in _DESTINATION_ALIASES:
            return _DESTINATION_ALIASES[part]
    return None


def _category_from_path(relative: str) -> Optional[str]:
    parts = relative.lower().split("/")
    if parts and parts[0] in _CATEGORY_FOLDERS:
        return _CATEGORY_FOLDERS[parts[0]]
    if len(parts) >= 3 and parts[0] == "vietnam":
        stem = Path(parts[-1]).stem.lower()
        mapping = {
            "food": "food",
            "transport": "transportation",
            "tips": "travel_tips",
            "culture": "culture",
            "safety": "safety",
            "seasonal": "seasonal",
            "guide": "destination_guide",
        }
        for key, value in mapping.items():
            if key in stem:
                return value
        return "destination_guide"
    return "general"


def _title_from_content(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None
