import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper import scrape_server, ScrapeError  # noqa: E402

HISTORY_FILE = ROOT / "data" / "guild_power_history.json"
GUILD_CSV = ROOT / "data" / "guild_power_daily.csv"
PLAYER_CSV = ROOT / "data" / "guild_power_players_daily.csv"
KST = ZoneInfo("Asia/Seoul")


def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read {path}: {exc}") from exc


def write_csv(path, fieldnames, rows, key_fields=()):
    existing = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            existing = list(csv.DictReader(f))
    keyed = {}
    for row in existing:
        key = tuple(row.get(k, "") for k in key_fields) if key_fields else None
        if key_fields:
            keyed[key] = row
        else:
            keyed[tuple(row.get(k, "") for k in fieldnames)] = row
    for row in rows:
        key = tuple(str(row.get(k, "")) for k in key_fields) if key_fields else tuple(str(row.get(k, "")) for k in fieldnames)
        keyed[key] = {k: row.get(k, "") for k in fieldnames}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(keyed.values())


def main(server_id=139):
    try:
        players, source_url = scrape_server(server_id)
    except ScrapeError as exc:
        raise SystemExit(f"Collection failed: {exc}") from exc
    if not players:
        raise SystemExit("No leaderboard rows found; refusing to overwrite history.")

    now = datetime.now(timezone.utc)
    captured_at = now.isoformat()
    day = now.astimezone(KST).date().isoformat()

    guilds = defaultdict(lambda: {"tag": "", "total_power": 0, "player_count": 0, "players": []})
    player_rows = []
    for p in players:
        tag = (p.get("tag") or "").strip() or "(무소속/태그 없음)"
        g = guilds[tag]
        g["tag"] = tag
        g["total_power"] += int(p["power"])
        g["player_count"] += 1
        g["players"].append({"rank": int(p["rank"]), "player": p["player"], "power": int(p["power"])})
        player_rows.append({
            "date": day, "server_id": server_id, "rank": int(p["rank"]),
            "player": p["player"], "guild_tag": tag, "power": int(p["power"])
        })

    total_power = sum(g["total_power"] for g in guilds.values())
    guild_rows = []
    for tag, g in guilds.items():
        guild_rows.append({
            "tag": tag, "total_power": g["total_power"], "player_count": g["player_count"],
            "share_percent": round((g["total_power"] / total_power * 100), 4) if total_power else 0,
            "players": sorted(g["players"], key=lambda x: x["rank"])
        })
    guild_rows.sort(key=lambda x: (-x["total_power"], x["tag"]))
    for rank, row in enumerate(guild_rows, start=1):
        row["rank"] = rank

    history = read_json(HISTORY_FILE, {"version": 1, "server_id": server_id, "snapshots": []})
    snapshots = history.setdefault("snapshots", [])
    snapshot = {
        "date": day, "captured_at": captured_at, "server_id": server_id,
        "source_url": source_url, "source_player_count": len(players),
        "tracked_total_power": total_power, "guild_count": len(guild_rows),
        "guilds": guild_rows
    }
    if snapshots and snapshots[-1].get("date") == day:
        snapshots[-1] = snapshot
    else:
        snapshots.append(snapshot)
    history.update({"version": 1, "server_id": server_id, "updated_at": captured_at,
                    "scope_note": "집계는 공개 랭킹 페이지에서 수집된 플레이어만 포함합니다. 전체 길드 전투력으로 단정할 수 없습니다."})
    history["snapshots"] = snapshots[-365:]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    guild_csv_rows = [{
        "date": day, "server_id": server_id, "rank": g["rank"], "guild_tag": g["tag"],
        "total_power": g["total_power"], "player_count": g["player_count"],
        "share_percent": g["share_percent"], "source_player_count": len(players)
    } for g in guild_rows]
    write_csv(GUILD_CSV,
              ["date", "server_id", "rank", "guild_tag", "total_power", "player_count", "share_percent", "source_player_count"],
              guild_csv_rows, key_fields=("date", "server_id", "guild_tag"))
    write_csv(PLAYER_CSV,
              ["date", "server_id", "rank", "player", "guild_tag", "power"],
              player_rows, key_fields=("date", "server_id", "player", "guild_tag"))

    print(f"Saved server {server_id}: {len(players)} ranked players, {len(guild_rows)} guild tags, date {day} ({source_url})")


if __name__ == "__main__":
    main()
