"""
Event Watcher - Preset watchers and first-run examples, focused on Belfast venues.

Every source below is a free, public web page or feed; none needs an account or API key.
Each was checked to return readable event data. Websites change over time: if one stops
working, Event Watcher reports it under Sources and with a "needs attention" notification,
and the URL can simply be edited or replaced.
"""

_O2 = {
    "name": "The O2 Belfast (SSE Arena) - all events",
    "category": "Concerts",
    "source_type": "json_feed",
    "source_url": "https://theo2belfast.com/events.json",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 180,
    "description": "Every concert, show and Belfast Giants game at The O2 Belfast, the arena formerly called "
                   "the SSE Arena, read from the venue's own public events feed.",
}
_BOUCHER = {
    "name": "Boucher Road Playing Fields - concerts",
    "category": "Concerts",
    "source_type": "event_listing",
    "source_url": "https://www.songkick.com/venues/1780193-boucher-playing-fields",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 360,
    "description": "Big outdoor concerts at Boucher Road Playing Fields (public Songkick venue listing). "
                   "Belfast City Council plans to end concerts there after 2027.",
}
_ORMEAU = {
    "name": "Belsonic - Ormeau Park",
    "category": "Festivals",
    "source_type": "event_listing",
    "source_url": "https://www.belsonic.com/",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 360,
    "description": "Belsonic line-up announcements at Ormeau Park, from the festival's own website.",
}
_FOOTBALL = {
    "name": "Northern Ireland football - Windsor Park fixtures",
    "category": "Football",
    "source_type": "sports_fixture",
    "source_url": "https://www.irishfa.com/ifa-international/fixtures-and-results",
    "keywords": ["Northern Ireland"],
    "exclude_keywords": [],
    "check_interval_minutes": 360,
    "description": "Northern Ireland international fixtures from the Irish FA, including home games at Windsor Park "
                   "and away games people watch in bars.",
}
_AIKEN = {
    "name": "Aiken Promotions - Belfast announcements",
    "category": "Concerts",
    "source_type": "webpage",
    "source_url": "https://aikenpromotions.com/",
    "keywords": ["Belfast"],
    "exclude_keywords": [],
    "check_interval_minutes": 180,
    "description": "\"Just announced\" shows from Aiken Promotions, promoter of many big Belfast gigs "
                   "(The O2, Boucher Road, Ormeau Park, Custom House Square). Only items mentioning Belfast.",
}
_WATERFRONT = {
    "name": "Waterfront Hall - what's on",
    "category": "Theatre",
    "source_type": "event_listing",
    "source_url": "https://www.waterfront.co.uk/",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 720,
    "description": "Shows, comedy and concerts at the Waterfront Hall, from the venue's website.",
}
_ULSTER_HALL = {
    "name": "Ulster Hall - what's on",
    "category": "Concerts",
    "source_type": "event_listing",
    "source_url": "https://www.ulsterhall.co.uk/",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 720,
    "description": "Concerts and comedy at the Ulster Hall, from the venue's website.",
}
_VISIT_BELFAST = {
    "name": "Visit Belfast - what's on",
    "category": "General",
    "source_type": "event_listing",
    "source_url": "https://visitbelfast.com/whats-on/",
    "keywords": [],
    "exclude_keywords": [],
    "check_interval_minutes": 720,
    "description": "Featured city events from Visit Belfast, the official tourism site.",
}

PRESETS = [
    {"id": "preset-o2-belfast", **_O2},
    {"id": "preset-boucher-road", **_BOUCHER},
    {"id": "preset-ormeau-belsonic", **_ORMEAU},
    {"id": "preset-ni-football", **_FOOTBALL},
    {"id": "preset-aiken-belfast", **_AIKEN},
    {"id": "preset-waterfront", **_WATERFRONT},
    {"id": "preset-ulster-hall", **_ULSTER_HALL},
    {"id": "preset-visit-belfast", **_VISIT_BELFAST},
]

# Watchers created on the very first start (the venues the owner asked for).
SEED_WATCHERS = [
    {"id": "watcher-o2-belfast", **_O2},
    {"id": "watcher-boucher-road", **_BOUCHER},
    {"id": "watcher-ormeau-belsonic", **_ORMEAU},
    {"id": "watcher-ni-football", **_FOOTBALL},
    {"id": "watcher-aiken-belfast", **_AIKEN},
]
