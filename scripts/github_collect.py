import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper import scrape_server, ScrapeError  # noqa: E402

DATA_FILE = ROOT / "data" / "snapshots.json"


def main(server_id: int) -> None:
    try:
        players, source_url = scrape_server(server_id)
    except ScrapeError as exc:
        raise SystemExit(f"Collection failed: {exc}") from exc

    if not players:
        raise SystemExit("No leaderboard rows found; refusing to overwrite history.")

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"Cannot read {DATA_FILE}: {exc}") from exc
    else:
        data = {"version": 1, "servers": {}}

    servers = data.setdefault("servers", {})
    history = servers.setdefault(str(server_id), [])
    previous = history[-1] if history else None
    old_map = {
        (str(row.get("player", "")), str(row.get("tag", ""))): row
        for row in (previous or {}).get("rows", [])
    }

    rows = []
    for player in players:
        old = old_map.get((player["player"], player["tag"]))
        rows.append({
            "rank": player["rank"],
            "player": player["player"],
            "tag": player["tag"],
            "power": player["power"],
            "power_delta": player["power"] - old["power"] if old else None,
            "rank_change": old["rank"] - player["rank"] if old else None,
        })

    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "server_id": server_id,
        "source_url": source_url,
        "rows": rows,
    }

    # A single scheduled run per day; if manually rerun on the same Korea date,
    # replace today's snapshot rather than accumulating duplicates.
    korea_date = datetime.now(timezone.utc).astimezone(
        __import__("zoneinfo").ZoneInfo("Asia/Seoul")
    ).date().isoformat()
    if history:
        last_date = datetime.fromisoformat(history[-1]["captured_at"].replace("Z", "+00:00")).astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ).date().isoformat()
        if last_date == korea_date:
            history[-1] = snapshot
        else:
            history.append(snapshot)
    else:
        history.append(snapshot)

    data["version"] = 1
    data["updated_at"] = snapshot["captured_at"]
    # Keep a rolling 365 snapshots per server to keep the repository small.
    servers[str(server_id)] = history[-365:]
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {len(rows)} players for server {server_id} from {source_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=int, default=149)
    args = parser.parse_args()
    main(args.server)
