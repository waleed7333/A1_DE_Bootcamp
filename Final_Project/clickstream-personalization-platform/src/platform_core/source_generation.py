"""Generate small, deterministic local sources for the project.

The generator intentionally keeps each source in one location:
- Clickstream: one mixed JSONL file.
- Web logs: one mixed .log file containing NDJSON records.
- PostgreSQL seeds: correct CSV files only.

Spark, not the generator, decides whether a streamed record is accepted or quarantined.
"""

from __future__ import annotations

import ipaddress
import os
import random
import maxminddb
import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from platform_core.config import load_settings

UTC_NOW = UTC
MONEY = Decimal("0.01")
VALID_EVENT_TYPES = { "page_view", "product_view", "search", "scroll", "add_to_cart", "remove_from_cart", "checkout_start", "checkout_complete", "login", "logout", }
PRODUCT_EVENTS = {"product_view", "add_to_cart", "remove_from_cart", "checkout_start", "checkout_complete"}
CHECKOUT_EVENTS = {"checkout_start", "checkout_complete"}
PRODUCT_CATEGORIES = {
    "Electronics": ["Wireless Earbuds", "Smart Watch", "Bluetooth Speaker", "USB-C Hub", "Gaming Mouse", "Portable Charger"],
    "Home": ["Coffee Maker", "Desk Lamp", "Air Purifier", "Storage Basket", "Kitchen Scale", "Water Bottle"],
    "Fashion": ["Everyday Backpack", "Cotton Hoodie", "Running Shoes", "Classic Cap", "Travel Wallet", "Sports Jacket"],
    "Beauty": ["Skin Care Set", "Hair Dryer", "Face Cleanser", "Body Lotion", "Makeup Brush Set", "Perfume Mist"],
    "Sports": ["Yoga Mat", "Resistance Bands", "Fitness Tracker", "Insulated Bottle", "Training Gloves", "Jump Rope"],
    "Books": ["Data Engineering Guide", "Product Design Book", "Business Analytics Book", "Python Cookbook", "Leadership Journal", "Travel Notebook"],
}
GEO_CANDIDATE_IPS = [ "128.101.101.101", "128.32.12.14", "128.210.11.57", "128.2.42.95", "129.21.1.40", "129.105.49.1", "130.149.17.13", "131.111.8.42", "132.239.180.101", "137.132.21.27", "140.112.8.139", "143.248.5.130", "145.100.185.15", "147.102.222.210", "152.3.43.27", "155.246.89.20", "160.39.9.21", "171.64.7.115", "193.51.208.13", "202.112.0.36", ]
FIRST_NAMES = ["Alex", "Maya", "Noah", "Lina", "Omar", "Sara", "Yusuf", "Nora", "Daniel", "Mina", "Adam", "Hana"]
LAST_NAMES = ["Smith", "Brown", "Khan", "Miller", "Ali", "Jones", "Hassan", "Wilson", "Taylor", "Saleh", "Martin", "Moore"]
BROWSERS = [("Chrome", "Windows"), ("Chrome", "Android"), ("Safari", "iOS"), ("Firefox", "Windows"), ("Edge", "Windows")]
TRAFFIC_SOURCES = ["organic", "paid_search", "email", "social", "direct"]

PRODUCT_FIELDS = ["product_id", "product_name", "category", "price", "inventory", "created_at", "updated_at"]
USER_FIELDS = ["user_id", "email", "first_name", "last_name", "membership_type", "account_status", "country_code", "city", "created_at", "updated_at"]
ORDER_FIELDS = [
    "order_id", "user_id", "checkout_id", "order_timestamp", "order_status", "payment_status", "currency",
    "subtotal_amount", "discount_amount", "tax_amount", "shipping_amount", "total_amount", "created_at", "updated_at",
]
ORDER_ITEM_FIELDS = ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "line_total", "created_at", "updated_at"]


@dataclass(frozen=True)
class SourceCheck:
    """One small source validation result shown by the command line."""

    status: str
    check: str
    detail: str


class SourceValidationError(ValueError):
    """Raised when a generated local source violates its expected contract."""


def _check(status: str, check: str, detail: str) -> SourceCheck:
    return SourceCheck(status, check, detail)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC_NOW).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SourceValidationError(f"Timestamp has no timezone: {value}")
    return parsed.astimezone(UTC_NOW)


def _money(value: Decimal | float | str) -> str:
    return format(Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP), ".2f")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows_list = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows_list)
    return len(rows_list)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_lines(path: Path, lines: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    line_list = list(lines)
    path.write_text("\n".join(line_list) + "\n", encoding="utf-8")
    return len(line_list)


def _read_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _clear_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

def _geoip_path(project_root: Path) -> Path:
    """Return the local GeoLite2 database path used by source generation."""
    env_value = os.environ.get("GEOIP_DATABASE_PATH")

    if env_value:
        env_path = Path(env_value)

        if not env_path.is_absolute():
            env_path = project_root / env_path

        if env_path.is_file():
            return env_path

    return project_root / "data" / "reference" / "GeoLite2-City.mmdb"


def _is_public_ipv4(value: str) -> bool:
    """Return True only for public IPv4 addresses."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        address.version == 4
        and not address.is_private
        and not address.is_loopback
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_link_local
        and not address.is_unspecified
    )


def _resolve_geoip(reader: Any, ip_address: str) -> dict[str, Any] | None:
    """Resolve one IP address using GeoLite2 and require city-level detail."""
    if not _is_public_ipv4(ip_address):
        return None

    try:
        record = reader.get(ip_address) or {}
    except Exception:
        return None

    country = record.get("country") or {}
    city = record.get("city") or {}
    location = record.get("location") or {}

    country_code = country.get("iso_code")
    country_name = (country.get("names") or {}).get("en")
    city_name = (city.get("names") or {}).get("en")
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    timezone = location.get("time_zone")

    if not all(
        [
            country_code,
            country_name,
            city_name,
            latitude is not None,
            longitude is not None,
            timezone,
        ]
    ):
        return None

    return {
        "ip_address": ip_address,
        "country_code": country_code,
        "country_name": country_name,
        "city": city_name,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "timezone": timezone,
    }


def _random_public_ipv4(randomizer: random.Random) -> str:
    """Generate one deterministic public IPv4 candidate."""
    while True:
        value = randomizer.randint(1, (2**32) - 2)
        ip_address = str(ipaddress.ip_address(value))

        if _is_public_ipv4(ip_address):
            return ip_address


def _discover_geo_locations( project_root: Path, randomizer: random.Random, minimum: int = 10, ) -> list[dict[str, Any]]:
    """Build a small deterministic IP pool proven by the local GeoLite2 file.

    Source records only carry ip_address. Country/city are not generated into
    Clickstream or Web Logs. Spark must derive them later from GeoLite2.

    Selection policy:
    - Read all candidate IPs first.
    - Keep only IPs that GeoLite2 can enrich with country/city/lat/lon/timezone.
    - Prefer country diversity before filling extra cities.
    """
    database_path = _geoip_path(project_root)

    if not database_path.is_file():
        raise SourceValidationError(
            f"GeoLite2 database not found: {database_path}"
        )

    discovered: list[dict[str, Any]] = []
    seen_ips: set[str] = set()
    seen_geo_keys: set[tuple[str, str]] = set()

    def add_candidate(reader: Any, ip_address: str) -> None:
        if ip_address in seen_ips:
            return

        seen_ips.add(ip_address)

        location = _resolve_geoip(reader, ip_address)

        if location is None:
            return

        geo_key = (
            str(location["country_code"]),
            str(location["city"]),
        )

        if geo_key in seen_geo_keys:
            return

        seen_geo_keys.add(geo_key)
        discovered.append(location)

    with maxminddb.open_database(str(database_path)) as reader:
        # First, test all fixed candidate IPs. Do not stop after the first 6,
        # because the first valid IPs may all belong to the same country.
        for ip_address in GEO_CANDIDATE_IPS:
            add_candidate(reader, ip_address)

        # If the fixed list is not enough, add deterministic random public IPv4s.
        attempts = 0
        max_attempts = 50_000

        while len(discovered) < minimum and attempts < max_attempts:
            attempts += 1
            add_candidate(reader, _random_public_ipv4(randomizer))

    if len(discovered) < minimum:
        raise SourceValidationError(
            "Could not discover enough GeoLite2-enrichable public IPs. "
            f"Required={minimum}, discovered={len(discovered)}. "
            "Update GEO_CANDIDATE_IPS with public IPs that exist in the local "
            "GeoLite2-City.mmdb file."
        )

    selected: list[dict[str, Any]] = []
    selected_countries: set[str] = set()

    # Pass 1: prefer one city per country.
    for location in discovered:
        country = str(location["country_code"])

        if country in selected_countries:
            continue

        selected.append(location)
        selected_countries.add(country)

        if len(selected) >= minimum:
            return selected

    # Pass 2: fill remaining slots with additional valid cities.
    selected_keys = {
        (str(item["country_code"]), str(item["city"]))
        for item in selected
    }

    for location in discovered:
        geo_key = (
            str(location["country_code"]),
            str(location["city"]),
        )

        if geo_key in selected_keys:
            continue

        selected.append(location)
        selected_keys.add(geo_key)

        if len(selected) >= minimum:
            return selected

    return selected

class LocalSourceGenerator:
    """Create deterministic source files while preserving the static catalog."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.settings = load_settings(project_root)
        self.generation = self.settings["source_generation"]
        self.random = random.Random(int(self.generation["deterministic_seed"]))
        self.source_root = project_root / self.settings["paths"]["source"]
        self.catalog_path = project_root / self.settings["paths"]["product_catalog"]
        self.manifest_path = self.source_root / "generation_manifest.json"
        self.base_time = _parse_timestamp(self.generation["base_timestamp"])
        self.locations = _discover_geo_locations( project_root, random.Random(int(self.generation["deterministic_seed"]) + 7919), minimum=6, )

    def generate(self) -> tuple[list[SourceCheck], bool]:
        """Generate every source and validate the result without Kafka or Docker."""
        try:
            catalog_action, catalog = self._ensure_catalog()
            for folder in ("clickstream", "web_logs", "postgres"):
                _clear_directory(self.source_root / folder)
            if self.manifest_path.exists():
                self.manifest_path.unlink()

            users = self._users()
            orders, items = self._orders(catalog, users)
            clickstream, clickstream_counts = self._clickstream(orders, items, users)
            web_logs, web_log_counts = self._web_logs(clickstream)
            files = self._write_files(users, orders, items, clickstream, web_logs)
            manifest = {
                "status": "GENERATED",
                "generated_at": _timestamp(datetime.now(UTC_NOW)),
                "deterministic_seed": int(self.generation["deterministic_seed"]),
                "catalog_checksum": _sha256(self.catalog_path),
                "catalog_action": catalog_action,
                "counts": {
                    "products": len(catalog),
                    "users": len(users),
                    "orders": len(orders),
                    "order_items": len(items),
                    **clickstream_counts,
                    **web_log_counts,
                },
                "files": files,
                "source_policy": {
                    "clickstream_file": "data/source/clickstream/clickstream_events.jsonl",
                    "web_log_file": "data/source/web_logs/webserver_access.log",
                    "mixed_quality_records": True,
                    "product_catalog_is_static_and_clean": True,
                    "postgres_seed_files_are_clean": True,
                    "geoip_policy": "Source records contain ip_address only; country/city are produced later by GeoLite2 enrichment",
                    "geoip_validated_ip_pool_size": len(self.locations),
                },
            }
            self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            checks, valid = validate_sources(self.project_root, write_report=True)
            checks.insert(0, _check("PASS", "Static product catalog", f"{catalog_action}; {len(catalog)} products"))
            return checks, valid
        except Exception as error:
            report = self.project_root / "reports" / "source_generation_report.json"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({"status": "FAILED", "error": f"{type(error).__name__}: {error}"}, indent=2) + "\n", encoding="utf-8")
            return [_check("FAIL", "Source generation", f"{type(error).__name__}: {error}")], False

    def _ensure_catalog(self) -> tuple[str, list[dict[str, str]]]:
        """Create the static catalog once and never overwrite it afterwards."""
        if self.catalog_path.exists():
            return "reused without modification", _read_csv(self.catalog_path)
        rows: list[dict[str, str]] = []
        categories = list(PRODUCT_CATEGORIES)
        for index in range(1, int(self.generation["product_catalog_count"]) + 1):
            category = categories[(index - 1) % len(categories)]
            name = PRODUCT_CATEGORIES[category][((index - 1) // len(categories)) % len(PRODUCT_CATEGORIES[category])]
            created = self.base_time - timedelta(days=90 - index % 25)
            rows.append({
                "product_id": f"PRD{index:06d}",
                "product_name": f"{name} {index:02d}",
                "category": category,
                "price": _money(Decimal("9.99") + Decimal((index * 7) % 50) + Decimal(index % 3) * Decimal("0.25")),
                "inventory": str(20 + (index * 13) % 180),
                "created_at": _timestamp(created),
                "updated_at": _timestamp(created + timedelta(days=index % 10)),
            })
        _write_csv(self.catalog_path, PRODUCT_FIELDS, rows)
        return "created once", rows

    def _users(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for index in range(1, int(self.generation["user_count"]) + 1):
            location = self.locations[(index - 1) % len(self.locations)]
            country = str(location["country_code"])
            city = str(location["city"])
            created = self.base_time - timedelta(days=180 - index)
            first = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
            last = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
            rows.append({
                "user_id": f"USR{index:06d}",
                "email": f"{first.lower()}.{last.lower()}.{index:03d}@example.test",
                "first_name": first,
                "last_name": last,
                "membership_type": ("guest", "standard", "premium")[index % 3],
                "account_status": "active" if index % 13 else "inactive",
                "country_code": country,
                "city": city,
                "created_at": _timestamp(created),
                "updated_at": _timestamp(created + timedelta(days=index % 21)),
            })
        return rows

    def _orders(self, catalog: list[dict[str, str]], users: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        orders: list[dict[str, str]] = []
        items: list[dict[str, str]] = []
        item_number = 1
        for index in range(1, int(self.generation["order_count"]) + 1):
            created = self.base_time + timedelta(hours=index * 3, minutes=index % 17)
            user = users[(index * 5) % len(users)]
            selected = self.random.sample(catalog, 1 + index % 3)
            subtotal = Decimal("0.00")
            for product in selected:
                quantity = 1 + (index + item_number) % 3
                unit_price = Decimal(product["price"])
                line_total = (unit_price * quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
                subtotal += line_total
                items.append({
                    "order_item_id": f"OIT{item_number:06d}",
                    "order_id": f"ORD{index:06d}",
                    "product_id": product["product_id"],
                    "quantity": str(quantity),
                    "unit_price": _money(unit_price),
                    "line_total": _money(line_total),
                    "created_at": _timestamp(created),
                    "updated_at": _timestamp(created),
                })
                item_number += 1
            discount = Decimal("5.00") if index % 5 == 0 else Decimal("0.00")
            discount = min(discount, subtotal)
            tax = ((subtotal - discount) * Decimal("0.05")).quantize(MONEY, rounding=ROUND_HALF_UP)
            shipping = Decimal("0.00") if subtotal >= Decimal("80.00") else Decimal("4.99")
            # A small number of non-revenue statuses prove business status handling.
            if index % 17 == 0:
                order_status, payment_status = "cancelled", "failed"
            elif index % 19 == 0:
                order_status, payment_status = "cancelled", "refunded"
            else:
                order_status, payment_status = ("delivered" if index % 3 == 0 else "shipped"), "paid"
            orders.append({
                "order_id": f"ORD{index:06d}",
                "user_id": user["user_id"],
                "checkout_id": f"CHK{index:06d}",
                "order_timestamp": _timestamp(created),
                "order_status": order_status,
                "payment_status": payment_status,
                "currency": "USD",
                "subtotal_amount": _money(subtotal),
                "discount_amount": _money(discount),
                "tax_amount": _money(tax),
                "shipping_amount": _money(shipping),
                "total_amount": _money(subtotal - discount + tax + shipping),
                "created_at": _timestamp(created),
                "updated_at": _timestamp(created + timedelta(minutes=10)),
            })
        return orders, items

    def _event(self, sequence: int, timestamp: datetime, session_id: str, user: dict[str, str], event_type: str, *, product_id: str = "", checkout_id: str = "", order_id: str = "", page_url: str = "", request_id: str | None = None, search_query: str = "") -> dict[str, Any]:
        """Build a valid event. Client-only scroll events intentionally omit request_id."""
        location = self.locations[(sequence - 1) % len(self.locations)]
        ip_address = str(location["ip_address"])
        browser, operating_system = BROWSERS[(sequence - 1) % len(BROWSERS)]
        is_http = event_type != "scroll"
        return {
            "contract_version": "1.0",
            "event_id": f"EVT{sequence:08d}",
            "event_timestamp": _timestamp(timestamp),
            "session_id": session_id,
            "visitor_id": f"VIS{user['user_id'][3:]}",
            "user_id": user["user_id"],
            "event_type": event_type,
            "page_url": page_url or (f"/products/{product_id}" if product_id else "/home"),
            "search_query": search_query,
            "product_id": product_id,
            "checkout_id": checkout_id,
            "order_id": order_id,
            "request_id": request_id if is_http else None,
            "ip_address": ip_address,
            "device_type": "mobile" if operating_system in {"Android", "iOS"} else "desktop",
            "browser": browser,
            "operating_system": operating_system,
            "traffic_source": TRAFFIC_SOURCES[(sequence - 1) % len(TRAFFIC_SOURCES)],
            "scroll_depth_pct": 0 if event_type != "scroll" else 70,
            "time_on_page_seconds": 10 + sequence % 80,
        }

    def _clickstream(self, orders: list[dict[str, str]], items: list[dict[str, str]], users: list[dict[str, str]]) -> tuple[list[str], dict[str, int]]:
        """Create one mixed JSONL source. Invalid and duplicate records stay in the same file."""
        order_products: dict[str, str] = {}
        for item in items:
            order_products.setdefault(item["order_id"], item["product_id"])
        lines: list[str] = []
        valid_events: list[dict[str, Any]] = []
        sequence = 1
        for order in orders:
            user = next(user for user in users if user["user_id"] == order["user_id"])
            product_id = order_products[order["order_id"]]
            start = _parse_timestamp(order["order_timestamp"]) - timedelta(minutes=8)
            session_id = f"SES_ORDER_{order['order_id'][3:]}"
            for event_type, minute, page in (
                ("page_view", 0, "/home"),
                ("product_view", 1, f"/products/{product_id}"),
                ("add_to_cart", 3, "/cart"),
                ("checkout_start", 5, "/checkout"),
                ("checkout_complete", 7, "/checkout/complete"),
            ):
                request_id = f"REQ{sequence:08d}"
                valid_events.append(self._event(sequence, start + timedelta(minutes=minute), session_id, user, event_type, product_id=product_id, checkout_id=order["checkout_id"], order_id=order["order_id"], page_url=page, request_id=request_id))
                sequence += 1
        for index in range(int(self.generation["abandoned_session_count"])):
            user = users[(index * 7) % len(users)]
            product = items[index % len(items)]["product_id"]
            start = self.base_time + timedelta(days=4, hours=index)
            session_id = f"SES_ABANDON_{index:03d}"
            for event_type, minute, page in (("page_view", 0, "/home"), ("product_view", 1, f"/products/{product}"), ("add_to_cart", 4, "/cart"), ("checkout_start", 6, "/checkout")):
                valid_events.append(self._event(sequence, start + timedelta(minutes=minute), session_id, user, event_type, product_id=product, checkout_id=f"ABN{index:06d}", page_url=page, request_id=f"REQ{sequence:08d}"))
                sequence += 1
        for index in range(int(self.generation["browsing_session_count"])):
            user = users[(index * 11) % len(users)]
            product = items[(index + 13) % len(items)]["product_id"]
            start = self.base_time + timedelta(days=5, hours=index)
            session_id = f"SES_BROWSE_{index:03d}"
            valid_events.append(self._event(sequence, start, session_id, user, "page_view", page_url="/home", request_id=f"REQ{sequence:08d}")); sequence += 1
            valid_events.append(self._event(sequence, start + timedelta(minutes=1), session_id, user, "search", page_url="/search", request_id=f"REQ{sequence:08d}", search_query="wireless")); sequence += 1
            valid_events.append(self._event(sequence, start + timedelta(minutes=2), session_id, user, "product_view", product_id=product, page_url=f"/products/{product}", request_id=f"REQ{sequence:08d}")); sequence += 1
            valid_events.append(self._event(sequence, start + timedelta(minutes=3), session_id, user, "scroll", product_id=product, page_url=f"/products/{product}", request_id=None)); sequence += 1
        # Add two valid late-arrival records. Their event times are old, but their file position is last.
        for index in range(int(self.generation["late_event_count"])):
            user = users[index]
            product = items[index]["product_id"]
            valid_events.append(self._event(sequence, self.base_time - timedelta(hours=1, minutes=index), f"SES_LATE_{index:03d}", user, "product_view", product_id=product, request_id=f"REQ{sequence:08d}"))
            sequence += 1

        # Keep valid events in natural event order then interleave quality records later.
        lines = [json.dumps(event, separators=(",", ":"), sort_keys=True) for event in valid_events]
        duplicate_lines = [lines[5], lines[20]]
        invalid_lines = [
            json.dumps({"contract_version": "1.0", "event_timestamp": _timestamp(self.base_time), "session_id": "SES_BAD_001", "visitor_id": "VIS_BAD", "event_type": "page_view"}),
            json.dumps({"contract_version": "1.0", "event_id": "EVT_BAD_TYPE", "event_timestamp": _timestamp(self.base_time), "session_id": "SES_BAD_002", "visitor_id": "VIS_BAD", "event_type": "unsupported_event", "page_url": "/home"}),
            "{this is deliberately malformed json",
            json.dumps({"contract_version": "9.9", "event_id": "EVT_BAD_VERSION", "event_timestamp": _timestamp(self.base_time), "session_id": "SES_BAD_003", "visitor_id": "VIS_BAD", "event_type": "page_view", "page_url": "/home"}),
            json.dumps({"contract_version": "1.0", "event_id": "EVT_BAD_CHECKOUT", "event_timestamp": _timestamp(self.base_time), "session_id": "SES_BAD_004", "visitor_id": "VIS_BAD", "event_type": "checkout_start", "page_url": "/checkout"}),
        ]
        # Mix all cases in the one source file. Spark must identify every rejected record.
        mixed = list(lines)
        insertion_points = [7, 31, 66, 101, 145]
        for position, bad in zip(insertion_points, invalid_lines):
            mixed.insert(min(position, len(mixed)), bad)
        for position, duplicate in zip([14, 88], duplicate_lines):
            mixed.insert(min(position, len(mixed)), duplicate)
        return mixed, {
            "clickstream_valid": len(valid_events),
            "clickstream_invalid": len(invalid_lines),
            "clickstream_duplicates": len(duplicate_lines),
            "clickstream_total": len(mixed),
            "clickstream_http_eligible": sum(1 for event in valid_events if event.get("request_id")),
        }

    def _web_logs(self, clickstream_lines: list[str]) -> tuple[list[str], dict[str, int]]:
        """Create one .log file with NDJSON records for Filebeat."""
        valid_events: list[dict[str, Any]] = []
        for line in clickstream_lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("request_id") and event.get("contract_version") == "1.0" and event.get("event_type") in VALID_EVENT_TYPES and event.get("event_id"):
                valid_events.append(event)
        seen: set[str] = set()
        unique_events = []
        for event in valid_events:
            request_id = str(event["request_id"])
            if request_id not in seen:
                seen.add(request_id)
                unique_events.append(event)
        lines: list[str] = []
        for index, event in enumerate(unique_events, start=1):
            lines.append(json.dumps({
                "contract_version": "1.0",
                "log_id": f"LOG{index:08d}",
                "request_id": event["request_id"],
                "timestamp": event["event_timestamp"],
                "ip_address": event.get("ip_address"),
                "http_method": "POST" if event["event_type"] in {"add_to_cart", "checkout_start", "checkout_complete"} else "GET",
                "endpoint": event["page_url"],
                "status_code": 500 if index % 41 == 0 else 200,
                "response_time_ms": 4000 if index % 37 == 0 else 80 + index % 450,
                "user_agent": f"SyntheticBrowser/{event.get('browser', 'Unknown')}",
                "bytes_sent": 1200 + index * 3,
            }, separators=(",", ":"), sort_keys=True))
        duplicate_lines = [lines[3], lines[13]]
        invalid_lines = [
            json.dumps({"contract_version": "1.0", "request_id": "REQ_BAD_001", "timestamp": _timestamp(self.base_time), "endpoint": "/home", "status_code": 200, "response_time_ms": 50}),
            json.dumps({"contract_version": "1.0", "log_id": "LOG_BAD_STATUS", "request_id": "REQ_BAD_002", "timestamp": _timestamp(self.base_time), "endpoint": "/home", "status_code": 900, "response_time_ms": 50}),
            "invalid web log line",
            json.dumps({"contract_version": "9.9", "log_id": "LOG_BAD_VERSION", "request_id": "REQ_BAD_003", "timestamp": _timestamp(self.base_time), "endpoint": "/home", "status_code": 200, "response_time_ms": 50}),
        ]
        mixed = list(lines)
        for position, bad in zip([11, 45, 90, 135], invalid_lines):
            mixed.insert(min(position, len(mixed)), bad)
        for position, duplicate in zip([19, 77], duplicate_lines):
            mixed.insert(min(position, len(mixed)), duplicate)
        return mixed, {
            "web_logs_valid": len(lines),
            "web_logs_invalid": len(invalid_lines),
            "web_logs_duplicates": len(duplicate_lines),
            "web_logs_total": len(mixed),
        }

    def _write_files(self, users: list[dict[str, str]], orders: list[dict[str, str]], items: list[dict[str, str]], clickstream: list[str], web_logs: list[str]) -> dict[str, dict[str, Any]]:
        """Write the four source groups and record small non-secret file metadata."""
        files: dict[str, dict[str, Any]] = {}
        targets = [
            (self.source_root / "postgres" / "users_seed.csv", lambda p: _write_csv(p, USER_FIELDS, users), "csv"),
            (self.source_root / "postgres" / "orders_seed.csv", lambda p: _write_csv(p, ORDER_FIELDS, orders), "csv"),
            (self.source_root / "postgres" / "order_items_seed.csv", lambda p: _write_csv(p, ORDER_ITEM_FIELDS, items), "csv"),
            (self.source_root / "clickstream" / "clickstream_events.jsonl", lambda p: _write_lines(p, clickstream), "jsonl"),
            (self.source_root / "web_logs" / "webserver_access.log", lambda p: _write_lines(p, web_logs), "ndjson_log"),
        ]
        for path, writer, kind in targets:
            count = writer(path)
            files[str(path.relative_to(self.project_root))] = {"record_count": count, "kind": kind, "sha256": _sha256(path)}
        return files


def _validate_catalog(path: Path, expected_count: int) -> SourceCheck:
    rows = _read_csv(path)
    if not rows or list(rows[0]) != PRODUCT_FIELDS:
        raise SourceValidationError("Product Catalog header does not match the approved contract")
    ids = [row["product_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise SourceValidationError("Product Catalog contains duplicate product_id values")
    if len(rows) != expected_count:
        raise SourceValidationError(f"Product Catalog expected {expected_count} rows but found {len(rows)}")
    for row in rows:
        if not row["product_name"].strip() or not row["category"].strip() or Decimal(row["price"]) < 0 or int(row["inventory"]) < 0:
            raise SourceValidationError(f"Invalid Product Catalog record: {row.get('product_id')}")
    return _check("PASS", "Product Catalog", f"{len(rows)} static valid products")


def _validate_seed(path: Path, fields: list[str], identity: str, label: str) -> SourceCheck:
    rows = _read_csv(path)
    if not rows or list(rows[0]) != fields:
        raise SourceValidationError(f"{label} header does not match the approved contract")
    values = [row[identity] for row in rows]
    if len(values) != len(set(values)):
        raise SourceValidationError(f"{label} contains duplicate {identity} values")
    return _check("PASS", label, f"{len(rows)} clean seed rows")


def _source_line_counts(lines: list[str], source: str) -> tuple[int, int, int]:
    """Classify only for generator validation; streaming repeats this independently."""
    valid = invalid = duplicate = 0
    key = "event_id" if source == "clickstream" else "log_id"
    seen: set[str] = set()
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            invalid += 1
            continue
        if not isinstance(payload, dict) or payload.get("contract_version") != "1.0" or not payload.get(key):
            invalid += 1
            continue
        if source == "clickstream":
            if "generator_country" in payload or "generator_city" in payload:
                invalid += 1
                continue
            if payload.get("event_type") not in VALID_EVENT_TYPES:
                invalid += 1
                continue
            if payload.get("event_type") in PRODUCT_EVENTS and not payload.get("product_id"):
                invalid += 1
                continue
            if payload.get("event_type") in CHECKOUT_EVENTS and not payload.get("checkout_id"):
                invalid += 1
                continue
            
        if source == "web_logs" and not (100 <= int(payload.get("status_code", -1)) <= 599):
            invalid += 1
            continue
        value = str(payload[key])
        if value in seen:
            duplicate += 1
            continue
        seen.add(value)
        valid += 1
    return valid, invalid, duplicate


def validate_sources(project_root: Path, *, write_report: bool = True) -> tuple[list[SourceCheck], bool]:
    """Validate files without requiring that mixed stream files are clean."""
    settings = load_settings(project_root)
    source_root = project_root / settings["paths"]["source"]
    manifest_path = source_root / "generation_manifest.json"
    checks: list[SourceCheck] = []
    try:
        if not manifest_path.is_file():
            raise SourceValidationError("Missing data/source/generation_manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks.append(_validate_catalog(project_root / settings["paths"]["product_catalog"], int(settings["source_generation"]["product_catalog_count"])))
        checks.append(_validate_seed(source_root / "postgres" / "users_seed.csv", USER_FIELDS, "user_id", "Users seed"))
        checks.append(_validate_seed(source_root / "postgres" / "orders_seed.csv", ORDER_FIELDS, "order_id", "Orders seed"))
        checks.append(_validate_seed(source_root / "postgres" / "order_items_seed.csv", ORDER_ITEM_FIELDS, "order_item_id", "Order items seed"))
        click_lines = _read_lines(source_root / "clickstream" / "clickstream_events.jsonl")
        log_lines = _read_lines(source_root / "web_logs" / "webserver_access.log")
        click_counts = _source_line_counts(click_lines, "clickstream")
        log_counts = _source_line_counts(log_lines, "web_logs")
        expected = manifest["counts"]
        if click_counts != (expected["clickstream_valid"], expected["clickstream_invalid"], expected["clickstream_duplicates"]):
            raise SourceValidationError(f"Clickstream mixed-source count mismatch: {click_counts}")
        if log_counts != (expected["web_logs_valid"], expected["web_logs_invalid"], expected["web_logs_duplicates"]):
            raise SourceValidationError(f"Web Log mixed-source count mismatch: {log_counts}")
        checks.append(_check("PASS", "Mixed Clickstream source", f"{len(click_lines)} lines: {click_counts[0]} valid, {click_counts[1]} invalid, {click_counts[2]} duplicate"))
        checks.append(_check("PASS", "Mixed Web Log source", f"{len(log_lines)} .log lines: {log_counts[0]} valid, {log_counts[1]} invalid, {log_counts[2]} duplicate"))
        checks.append(_check("PASS", "Source layout", "Clickstream and Web Logs each use one independent source file"))
        passed = True
    except Exception as error:
        checks.append(_check("FAIL", "Source validation", f"{type(error).__name__}: {error}"))
        passed = False
    if write_report:
        report = project_root / "reports" / "source_generation_report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"status": "PASSED" if passed else "FAILED", "checks": [asdict(item) for item in checks]}, indent=2) + "\n", encoding="utf-8")
    return checks, passed
