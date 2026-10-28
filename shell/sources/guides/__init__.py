"""Raid guides chosen by the player, cached as Markdown with their in-article images (cache/guides/<raid>/).

Third-party content: kept locally for the Ghost to read when it writes an encounter file, never published.
"""

GUIDES = {
    "deep-stone-crypt": {
        "grindout": "https://grindout.com/destiny-2/guides/deep-stone-crypt",
        "shacknews": "https://www.shacknews.com/article/121651/deep-stone-crypt-raid-guide-destiny-2",
        "overgear": "https://overgear.com/guides/destiny2/deep-stone-crypt-raid-guide/",
    },
}
ENCOUNTERS = {
    "deep-stone-crypt": ["desolation", "crypt-security", "atraks-1", "descent", "taniks-reborn",
                         "taniks-abomination"],
}
