"""
Event Watcher - Turning downloaded pages into a list of candidate events.

Deterministic rules only (no AI services). Supported inputs:
  * RSS / Atom feeds
  * iCalendar (.ics) feeds
  * JSON event feeds (e.g. a venue's /events.json), including "next page" links
  * Web pages:
      1. schema.org Event data embedded for search engines (JSON-LD), used by most
         ticketing and venue sites;
      2. otherwise, repeated "cards" or rows in the page (event listings, line-ups,
         fixture lists), found by looking for sibling elements with the same shape;
      3. otherwise, meaningful paragraphs of text.
Remote pages are only read as text; nothing from them is ever executed.

Every item is a dict: title, link, date (display text), date_raw, date_kind
("event" = when it happens, "published" = when a news item was posted), description, venue.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

Item = Dict[str, Any]
_F = re.IGNORECASE | re.DOTALL

# ---------------------------------------------------------------- text helpers

def squash(text: str) -> str:
    return " ".join(html.unescape(str(text or "")).replace(" ", " ").split())


def clean_html(raw: str) -> str:
    """Readable text of an HTML fragment, one block per line."""
    text = re.sub(r"<!--.*?-->", " ", raw, flags=re.DOTALL)
    for tag in ("script", "style", "noscript", "svg", "template", "iframe", "nav", "footer", "header"):
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", " ", text, flags=_F)
    text = re.sub(r"</(p|div|h[1-6]|li|tr|article|section)\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace(" ", " ")
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


# Ticket/status phrases that change over time. They are removed from titles so an event
# going from "Buy Tickets" to "Sold Out" is not reported as a new event.
_STATUS = re.compile(
    r"\b(buy tickets?|get tickets?|book (?:now|tickets?)|tickets? on sale(?: now)?|on sale now|sold out|"
    r"more info(?:rmation)?|find out more|read more|learn more|limited availability|few tickets left|"
    r"last (?:few )?tickets|just announced|extra (?:date|show)s? added|new date|rescheduled|cancelled|postponed)\b[:!.]*",
    re.IGNORECASE,
)


def clean_title(title: str) -> str:
    t = _STATUS.sub(" ", squash(title))
    t = re.sub(r"\s*[|•·–—-]\s*$", "", " ".join(t.split())).strip(" :|-–—")
    return t[:200]


# ---------------------------------------------------------------- dates

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DAY = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"

_DATE_PATTERNS = [
    re.compile(rf"\b((?:{_DAY},?\s+)?\d{{1,2}}(?:st|nd|rd|th)?\s+{_MON},?(?:\s+\d{{4}})?)\b", re.IGNORECASE),
    re.compile(rf"\b((?:{_DAY},?\s+)?{_MON}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?)\b", re.IGNORECASE),
    re.compile(r"\b(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?)\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"),
]


def detect_date(text: str) -> Optional[str]:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text or "")
        if m:
            return m.group(1).strip(" ,")
    return None


def parse_date(text: Optional[str]) -> Optional[datetime]:
    """Best-effort parse of the date formats venues use. Returns None when unsure."""
    if not text:
        return None
    s = str(text).strip()
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})(?:[T ](\d{2}):?(\d{2}))?", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm = int(m.group(4) or 0), int(m.group(5) or 0)
        try:
            return datetime(y, mo, d, hh, mm)
        except ValueError:
            return None
    m = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON}),?\s+(\d{{4}})", s, re.IGNORECASE) or \
        re.search(rf"({_MON})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", s, re.IGNORECASE)
    if m:
        a, b, year = m.group(1), m.group(2), int(m.group(3))
        day, mon = (int(a), b) if a.isdigit() else (int(b), a)
        month = _MONTHS.get(mon[:3].lower())
        time_m = re.search(r"\b(\d{1,2}):(\d{2})\b", s[m.end():m.end() + 20])
        try:
            return datetime(year, month or 0, day, int(time_m.group(1)) if time_m else 0,
                            int(time_m.group(2)) if time_m else 0)
        except (ValueError, TypeError):
            return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)  # UK order: day/month/year
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def pretty_date(raw: Optional[str]) -> Optional[str]:
    dt = parse_date(raw)
    if not dt:
        return squash(raw)[:100] if raw else None
    text = dt.strftime("%a %d %b %Y")
    if dt.hour or dt.minute:
        text += dt.strftime(", %H:%M")
    return text


def is_past(raw: Optional[str], now: Optional[datetime] = None) -> bool:
    dt = parse_date(raw)
    if not dt:
        return False
    now = now or datetime.now()
    return dt.date() < (now - timedelta(days=1)).date()


# ---------------------------------------------------------------- venues

_VENUE_PATTERNS = [
    re.compile(r"\b(The O2 Belfast|SSE Arena(?:\s+Belfast)?|Odyssey Arena|Boucher (?:Road )?Playing Fields|Boucher Road|"
               r"Ormeau Park|Windsor Park|National Football Stadium at Windsor Park|Ulster Hall|Waterfront Hall|"
               r"Belfast Waterfront|Custom House Square|Kingspan Stadium|Casement Park|Botanic Gardens|"
               r"Grand Opera House|Lyric Theatre|Limelight|Belfast Empire|Wembley Stadium|Aviva Stadium|"
               r"Hampden Park|3Arena|Croke Park|Marlay Park|The O2)\b", re.IGNORECASE),
    re.compile(r"\b(?:at|venue|location)\s*[:\-–]\s*([A-Z0-9][A-Za-z0-9 &',.\-]{3,40})"),
    re.compile(r"\b([A-Z][A-Za-z0-9']+(?:\s+[A-Z][A-Za-z0-9']+){0,3}\s+(?:Arena|Stadium|Hall|Theatre|Theater|Centre|"
               r"Center|Park|Pavilion|Bowl|Fields))\b"),
]


def detect_venue(text: str) -> Optional[str]:
    for pattern in _VENUE_PATTERNS:
        m = pattern.search(text or "")
        if m:
            venue = m.group(1).strip(" :-–\t,.")
            if 3 <= len(venue) <= 60:
                return venue
    return None


# ---------------------------------------------------------------- feeds

def _tag(block: str, names: str) -> Optional[str]:
    m = re.search(rf"<(?:{names})\b[^>]*>(.*?)</(?:{names})\s*>", block, _F)
    if not m:
        return None
    return re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.DOTALL)


def parse_feed(xml_text: str) -> List[Item]:
    items: List[Item] = []
    for block in re.findall(r"<item\b[^>]*>(.*?)</item\s*>", xml_text, _F):
        title = clean_html(_tag(block, "title") or "").strip()
        if not title:
            continue
        link = html.unescape((_tag(block, "link") or "").strip())
        guid = html.unescape((_tag(block, "guid") or "").strip())
        items.append(_item(title, link or (guid if guid.startswith("http") else ""),
                           (_tag(block, "pubDate|dc:date") or "").strip() or None, "published",
                           clean_html(_tag(block, "content:encoded|description") or "")))
    if items:
        return items
    for block in re.findall(r"<entry\b[^>]*>(.*?)</entry\s*>", xml_text, _F):
        title = clean_html(_tag(block, "title") or "").strip()
        if not title:
            continue
        link_m = (re.search(r"<link\b[^>]*rel=[\"']alternate[\"'][^>]*href=[\"']([^\"']+)[\"']", block, re.IGNORECASE)
                  or re.search(r"<link\b[^>]*href=[\"']([^\"']+)[\"']", block, re.IGNORECASE))
        items.append(_item(title, html.unescape(link_m.group(1).strip()) if link_m else "",
                           (_tag(block, "published|updated") or "").strip() or None, "published",
                           clean_html(_tag(block, "summary|content") or "")))
    return items


def _ics_unescape(value: str) -> str:
    return (value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\")).strip()


def parse_ics(ics_text: str) -> List[Item]:
    unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
    items = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.DOTALL | re.IGNORECASE):
        props: Dict[str, str] = {}
        for line in block.splitlines():
            m = re.match(r"([A-Za-z-]+)(?:;[^:]*)?:(.*)", line)
            if m and m.group(1).upper() not in props:
                props[m.group(1).upper()] = m.group(2)
        items.append(_item(_ics_unescape(props.get("SUMMARY", "")) or "Calendar Event",
                           props.get("URL", "").strip(), props.get("DTSTART", "").strip() or None, "event",
                           _ics_unescape(props.get("DESCRIPTION", "")),
                           _ics_unescape(props.get("LOCATION", "")) or None))
    return items


# ---------------------------------------------------------------- JSON feeds and JSON-LD

_TITLE_KEYS = ("title", "name", "headline", "eventName", "event_name")
_LINK_KEYS = ("url", "link", "href", "permalink", "eventUrl", "event_url", "web_url")
_DATE_KEYS = ("startDate", "start_date", "eventStartDate", "event_start_date", "start", "startTime",
              "start_time", "dateTime", "datetime", "eventDate", "event_date", "date")
_VENUE_KEYS = ("venue", "venueName", "venue_name", "location", "place")
_DESC_KEYS = ("description", "summary", "subtitle", "supportingAct", "supporting_act", "excerpt", "strapline")
_NEXT_PATHS = (("meta", "pagination", "links", "next"), ("links", "next"), ("pagination", "next"),
               ("next_page_url",), ("next",), ("nextPage",))


def _first_str(obj: Dict[str, Any], keys: Iterable[str], nested: Tuple[str, ...] = ("date", "name", "local", "value", "dateTime")) -> Optional[str]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, dict):
            for sub in nested:
                if isinstance(value.get(sub), str) and value[sub].strip():
                    return value[sub]
            continue
        if isinstance(value, list) and value and isinstance(value[0], (str, dict)):
            value = value[0]
            if isinstance(value, dict):
                value = next((value[s] for s in nested if isinstance(value.get(s), str)), None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _json_to_item(obj: Dict[str, Any], base_url: str) -> Optional[Item]:
    title = _first_str(obj, _TITLE_KEYS)
    if not title:
        return None
    link = _first_str(obj, _LINK_KEYS) or ""
    link = urljoin(base_url, link) if link else ""
    venue = _first_str(obj, _VENUE_KEYS, nested=("name",))
    location = obj.get("location")
    if isinstance(location, dict):
        address = location.get("address")
        locality = address.get("addressLocality") if isinstance(address, dict) else None
        if venue and isinstance(locality, str) and locality.lower() not in venue.lower():
            venue = f"{venue}, {locality}"
    desc = _first_str(obj, _DESC_KEYS, nested=("name", "text")) or ""
    return _item(clean_html(title), link, _first_str(obj, _DATE_KEYS), "event", clean_html(desc)[:600],
                 clean_html(venue) if venue else None)


def _object_lists(node: Any, depth: int = 0) -> Iterable[List[Dict[str, Any]]]:
    if depth > 6:
        return
    if isinstance(node, list):
        dicts = [x for x in node if isinstance(x, dict)]
        if dicts:
            yield dicts
        for x in dicts[:50]:
            yield from _object_lists(x, depth + 1)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _object_lists(value, depth + 1)


def parse_json_feed(text: str, base_url: str) -> Tuple[List[Item], Optional[str]]:
    """Find the list of event-like objects in a JSON document. Returns (items, next_page_url)."""
    try:
        data = json.loads(text)
    except ValueError:
        return [], None
    best: List[Dict[str, Any]] = []
    for objs in _object_lists(data):
        titled = [o for o in objs if _first_str(o, _TITLE_KEYS)]
        if len(titled) >= max(1, len(objs) // 2) and len(titled) > len(best):
            best = titled
    items = [i for i in (_json_to_item(o, base_url) for o in best) if i]
    next_url = None
    if isinstance(data, dict):
        for path in _NEXT_PATHS:
            node: Any = data
            for key in path:
                node = node.get(key) if isinstance(node, dict) else None
            if isinstance(node, str) and node.strip():
                next_url = urljoin(base_url, node.strip())
                break
    return items, next_url


_EVENT_TYPES = re.compile(r"(Event|Festival)$")


def parse_json_ld_events(raw_html: str, base_url: str) -> List[Item]:
    found: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(isinstance(t, str) and _EVENT_TYPES.search(t) for t in types) and node.get("name"):
                found.append(node)
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for block in re.findall(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script\s*>", raw_html, _F):
        try:
            walk(json.loads(html.unescape(block.strip()) if block.strip().startswith("&") else block.strip()))
        except ValueError:
            continue
    items, seen = [], set()
    for obj in found:
        item = _json_to_item(obj, base_url)
        if item and (item["title"], item["date_raw"]) not in seen:
            seen.add((item["title"], item["date_raw"]))
            items.append(item)
    return items


# ---------------------------------------------------------------- HTML listings (repeated cards/rows)

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "nav", "footer", "header", "select", "form"}
_STRONG_HINT = re.compile(r"event|fixture|gig|concert|show|lineup|line-up|match|performance|listing|whats-?on|"
                          r"production|programme|tour|result", re.IGNORECASE)


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "_text")

    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional["_Node"]):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: List[Any] = []
        self._text: Optional[str] = None

    def elements(self) -> Iterable["_Node"]:
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.elements()

    def text(self) -> str:
        if self._text is None:
            parts = []
            for child in self.children:
                parts.append(child.text() if isinstance(child, _Node) else child)
            self._text = squash(" ".join(parts))
        return self._text

    def first(self, tags: Iterable[str]) -> List["_Node"]:
        wanted = set(tags)
        return [e for e in self.elements() if e.tag in wanted]

    def signature(self) -> Tuple[str, str]:
        classes = sorted(c for c in self.attrs.get("class", "").split() if not re.search(r"\d{3,}", c))
        return self.tag, " ".join(classes)


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, None)
        self.cur = self.root
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag in _SKIP:
                self.skip_depth += 1
            return
        if tag in _SKIP:
            self.skip_depth = 1
            return
        node = _Node(tag, {k: (v or "") for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        if not self.skip_depth and tag not in _SKIP:
            self.cur.children.append(_Node(tag, {k: (v or "") for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag in _SKIP:
                self.skip_depth -= 1
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent  # type: ignore[assignment]
        if node is not self.root:
            self.cur = node.parent  # type: ignore[assignment]

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.cur.children.append(data)


def _is_inside(node: _Node, ancestors: set) -> bool:
    p = node.parent
    while p is not None:
        if id(p) in ancestors:
            return True
        p = p.parent
    return False


def _card_to_item(card: _Node, page_url: str) -> Optional[Item]:
    text = card.text()
    date_raw = detect_date(text)
    headings = [(int(h.tag[1]), h.text()) for h in card.first(("h1", "h2", "h3", "h4", "h5", "h6")) if h.text()]
    top = min((level for level, _ in headings), default=0)
    main = [t for level, t in headings if level == top]
    if len(main) == 1:
        # the most prominent heading is the name; a single sub-heading is kept as a subtitle
        title = main[0]
        sub = [t for level, t in headings if level == top + 1]
        if len(sub) == 1 and len(sub[0]) > 3 and sub[0].lower() not in title.lower():
            title = f"{title} – {sub[0]}"
    else:
        title = text.replace(date_raw, " ") if date_raw else text
        title = re.sub(r",?\s*\d{1,2}[:.]\d{2}\s*(?:am|pm|bst|gmt)?", " ", title, flags=re.IGNORECASE)
    title = clean_title(title)
    if not 4 <= len(title) <= 200:
        return None
    link = page_url
    for a in ([card] if card.tag == "a" else []) + card.first(("a",)):
        href = a.attrs.get("href", "").strip()
        if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
            candidate = urljoin(page_url, href)
            if candidate.startswith(("http://", "https://")):
                link = candidate
                break
    return _item(title, link, date_raw, "event", text[:500], detect_venue(text))


def parse_listing_cards(raw_html: str, page_url: str) -> List[Item]:
    builder = _TreeBuilder()
    try:
        builder.feed(raw_html)
        builder.close()
    except Exception:
        return []
    groups: List[Tuple[int, List[_Node]]] = []
    for parent in [builder.root, *builder.root.elements()]:
        kids = [c for c in parent.children if isinstance(c, _Node)]
        by_sig: Dict[Tuple[str, str], List[_Node]] = {}
        for kid in kids:
            by_sig.setdefault(kid.signature(), []).append(kid)
        for sig, members in by_sig.items():
            members = [m for m in members if 15 <= len(m.text()) <= 1500 and (m.tag == "a" or m.first(("a", "h2", "h3", "h4", "h5")))]
            if len(members) < 2:
                continue
            dated = sum(1 for m in members if detect_date(m.text()))
            hint = _STRONG_HINT.search(" ".join((sig[1], parent.attrs.get("class", ""), parent.attrs.get("id", ""))))
            if dated >= len(members) / 2 or (hint and len(members) >= 3):
                d, p = 0, parent
                while p is not None:
                    d, p = d + 1, p.parent
                groups.append((d, members))
    groups.sort(key=lambda g: g[0])  # outermost lists first; skip lists nested inside chosen cards
    chosen: set = set()
    items: List[Item] = []
    for _, members in groups:
        if any(_is_inside(m, chosen) for m in members):
            continue
        for m in members:
            chosen.add(id(m))
            item = _card_to_item(m, page_url)
            if item:
                items.append(item)
        if len(items) >= 80:
            break
    return items


def parse_webpage(raw: str, page_url: str) -> List[Item]:
    items = parse_json_ld_events(raw, page_url)
    if items:
        return items
    items = parse_listing_cards(raw, page_url)
    if items:
        return items
    fallback = []
    for para in clean_html(raw).split("\n"):
        if 30 <= len(para) <= 600:
            fallback.append(_item(para[:120], page_url, detect_date(para), "event", para, detect_venue(para)))
        if len(fallback) >= 15:
            break
    return fallback


# ---------------------------------------------------------------- entry point

def _item(title: str, link: str, date_raw: Optional[str], kind: str, description: str = "",
          venue: Optional[str] = None) -> Item:
    return {"title": squash(title)[:300], "link": link or "", "date_raw": squash(date_raw) if date_raw else None,
            "date_kind": kind, "description": description or "", "venue": venue}


def looks_like_json(raw: str) -> bool:
    return raw.lstrip()[:1] in ("{", "[")


def extract(raw: str, source_type: str, page_url: str) -> Tuple[str, List[Item], Optional[str], int]:
    """Returns (detected_type, items, next_page_url, items_read).
    items_read counts everything read from the page; items whose event date has already
    passed are then dropped from `items` (results, past gigs are never new announcements)."""
    head = raw[:2000].lower()
    next_url = None
    if looks_like_json(raw):
        items, next_url = parse_json_feed(raw, page_url)
        detected = "json_feed"
    elif source_type in ("rss", "atom") or "<rss" in head or "<feed" in head or "<rdf:rdf" in head:
        items, detected = parse_feed(raw), "rss"
    elif source_type == "calendar_ics" or "begin:vcalendar" in head:
        items, detected = parse_ics(raw), "calendar_ics"
    else:
        items, detected = parse_webpage(raw, page_url), source_type
    now = datetime.now()
    result = []
    for item in items:
        blob = f"{item['title']} {item.get('description') or ''}"
        if not item.get("date_raw") and item["date_kind"] == "event":
            item["date_raw"] = detect_date(blob)
        if item["date_kind"] == "event" and is_past(item.get("date_raw"), now):
            continue  # already happened: results, past gigs - never "new announcements"
        if item["date_kind"] == "event":
            item["date"] = pretty_date(item["date_raw"])
        else:  # news item: show the event date it mentions, else when it was published
            mentioned = detect_date(blob)
            item["date"] = pretty_date(mentioned) if mentioned else item.get("date_raw")
        item["venue"] = item.get("venue") or detect_venue(blob)
        if not str(item.get("link") or "").startswith(("http://", "https://")):
            item["link"] = page_url
        result.append(item)
    if next_url and urlsplit(next_url).netloc != urlsplit(page_url).netloc:
        next_url = None  # only follow pagination on the same website
    return detected, result, next_url, len(items)
