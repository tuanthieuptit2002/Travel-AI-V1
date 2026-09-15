from typing import Dict, Tuple


VIETNAM_DESTINATIONS: Dict[str, Tuple[str, float, float]] = {
    "hanoi": ("Hanoi", 21.0278, 105.8342),
    "da nang": ("Da Nang", 16.0544, 108.2022),
    "hoi an": ("Hoi An", 15.8801, 108.3380),
    "ho chi minh city": ("Ho Chi Minh City", 10.8231, 106.6297),
    "da lat": ("Da Lat", 11.9404, 108.4583),
    "nha trang": ("Nha Trang", 12.2388, 109.1967),
    "phu quoc": ("Phu Quoc", 10.2899, 103.9840),
    "ha long": ("Ha Long", 20.9511, 107.0730),
}

DESTINATION_ALIASES = {
    "ha noi": "hanoi",
    "hà nội": "hanoi",
    "danang": "da nang",
    "da nang city": "da nang",
    "đà nẵng": "da nang",
    "hoian": "hoi an",
    "hội an": "hoi an",
    "saigon": "ho chi minh city",
    "sài gòn": "ho chi minh city",
    "ho chi minh": "ho chi minh city",
    "hồ chí minh": "ho chi minh city",
    "hồ chí minh city": "ho chi minh city",
    "dalat": "da lat",
    "đà lạt": "da lat",
    "nhatrang": "nha trang",
    "phuquoc": "phu quoc",
    "phú quốc": "phu quoc",
    "halong": "ha long",
    "hạ long": "ha long",
    "ha long bay": "ha long",
    "vịnh hạ long": "ha long",
}


def normalize_destination(destination: str) -> str:
    normalized = " ".join(destination.casefold().strip().split())
    return DESTINATION_ALIASES.get(normalized, normalized)
