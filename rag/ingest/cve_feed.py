"""Utility to ingest NVD/CISA feeds into rag/corpus/raw/poc."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from xml.etree import ElementTree

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_repo_root

LOGGER = get_logger(__name__)
_CVE_PATTERN = re.compile(r"CVE-\d{4}-\d+")


@dataclass
class CveRecord:
    cve_id: str
    title: str
    description: str
    link: str
    published: str
    source: str
    tags: Sequence[str]

    def to_json(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


def _fetch_resource(path_or_url: str, timeout: int) -> str:
    path = Path(path_or_url)
    if path.exists():
        return path.read_text(encoding="utf-8")
    with urllib.request.urlopen(path_or_url, timeout=timeout) as handle:  # pragma: no cover - network
        data = handle.read()
        return data.decode("utf-8")


def _parse_nvd_rss(xml_text: str, limit: int) -> List[CveRecord]:
    root = ElementTree.fromstring(xml_text)
    items = root.findall(".//item")
    records: List[CveRecord] = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        match = _CVE_PATTERN.search(title) or _CVE_PATTERN.search(description)
        if not match:
            continue
        cve_id = match.group(0)
        records.append(
            CveRecord(
                cve_id=cve_id,
                title=title or cve_id,
                description=description,
                link=link or f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                published=pub_date or datetime.now(timezone.utc).isoformat(),
                source="nvd",
                tags=[],
            )
        )
        if len(records) >= limit:
            break
    return records


def _parse_cisa_json(payload: str, limit: int) -> List[CveRecord]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        LOGGER.warning("CISA feed is not valid JSON.")
        return []
    entries = data.get("vulnerabilities") or data.get("catalogItems") or []
    records: List[CveRecord] = []
    for entry in entries:
        cve_id = entry.get("cveID") or entry.get("cveId")
        if not cve_id:
            continue
        title = entry.get("vendorProject") or entry.get("product") or cve_id
        description = entry.get("shortDescription") or entry.get("description") or ""
        link = entry.get("notes") or entry.get("requiredAction") or ""
        published = entry.get("dateAdded") or entry.get("publicationDate") or ""
        tags = entry.get("vulnerabilityName") or entry.get("knownRansomwareCampaignUse")
        normalized_tags: List[str] = []
        if isinstance(tags, str) and tags:
            normalized_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        records.append(
            CveRecord(
                cve_id=cve_id,
                title=str(title),
                description=str(description),
                link=str(link or f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog"),
                published=str(published or datetime.now(timezone.utc).isoformat()),
                source="cisa",
                tags=normalized_tags,
            )
        )
        if len(records) >= limit:
            break
    return records


def _write_records(records: Iterable[CveRecord], output_dir: Path) -> List[Path]:
    ensure_dir(output_dir)
    written: List[Path] = []
    for record in records:
        filename = f"{record.cve_id.lower().replace(':', '-')}.json"
        path = output_dir / filename
        path.write_text(json.dumps(record.to_json(), indent=2), encoding="utf-8")
        written.append(path)
    return written


def _write_snapshot_metadata(snapshot_dir: Path, snapshot_id: str, count: int) -> None:
    metadata = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_layers": ["poc"],
        "count": count,
    }
    metadata_path = snapshot_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def ingest_feeds(args: argparse.Namespace) -> Path:
    repo_root = get_repo_root()
    base_output = ensure_dir(Path(args.output) if args.output else repo_root / "rag" / "corpus" / "raw" / "poc")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    batch_dir = ensure_dir(base_output / stamp)

    combined: Dict[str, CveRecord] = {}
    if args.nvd_rss:
        try:
            xml_text = _fetch_resource(args.nvd_rss, args.timeout)
            for record in _parse_nvd_rss(xml_text, args.limit):
                combined.setdefault(record.cve_id, record)
        except Exception as exc:  # pragma: no cover - network failure path
            LOGGER.warning("Failed to ingest NVD feed: %s", exc)

    if args.cisa_feed:
        try:
            json_text = _fetch_resource(args.cisa_feed, args.timeout)
            for record in _parse_cisa_json(json_text, args.limit):
                combined.setdefault(record.cve_id, record)
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("Failed to ingest CISA feed: %s", exc)

    if not combined:
        raise RuntimeError("No CVE entries were ingested. Check feed URLs or network access.")

    written_paths = _write_records(combined.values(), batch_dir)
    snapshot_id = f"rag-snap-{stamp}"
    snapshot_dir = ensure_dir(repo_root / "rag" / "index" / snapshot_id)
    _write_snapshot_metadata(snapshot_dir, snapshot_id, len(written_paths))
    LOGGER.info("Ingested %s CVE entries into %s", len(written_paths), batch_dir)
    return batch_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NVD/CISA feeds into rag/corpus/raw/poc")
    parser.add_argument("--nvd-rss", default="https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml")
    parser.add_argument(
        "--cisa-feed",
        default="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
    )
    parser.add_argument("--output", type=Path, help="Destination directory (default rag/corpus/raw/poc)")
    parser.add_argument("--limit", type=int, default=20, help="Maximum entries per feed")
    parser.add_argument("--timeout", type=int, default=15, help="Network timeout in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ingest_feeds(args)


if __name__ == "__main__":
    main()
