import argparse
from scraper import scrape_server
from app import connect, init_db
from datetime import datetime, timezone

def run(server_id):
    init_db()
    players, url = scrape_server(server_id)
    if not players:
        raise RuntimeError("랭킹 데이터가 비어 있어 저장하지 않았습니다.")
    stamp = datetime.now(timezone.utc)
    with connect() as conn:
        prev = conn.execute("SELECT MAX(captured_at) AS ts FROM snapshots WHERE server_id=%s", (server_id,)).fetchone()["ts"]
        old_map = {}
        if prev:
            old_rows = conn.execute("SELECT player_name, alliance_tag, rank, power FROM snapshots WHERE server_id=%s AND captured_at=%s", (server_id, prev)).fetchall()
            old_map = {(r["player_name"], r["alliance_tag"]): (r["rank"], r["power"]) for r in old_rows}
        for p in players:
            old = old_map.get((p["player"], p["tag"]))
            conn.execute("""INSERT INTO snapshots(captured_at,server_id,rank,player_name,alliance_tag,power,power_delta,rank_change) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", (stamp, server_id, p["rank"], p["player"], p["tag"], p["power"], p["power"]-old[1] if old else None, old[0]-p["rank"] if old else None))
    print(f"OK server={server_id} count={len(players)} url={url} at={stamp.isoformat()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=int, default=149)
    run(parser.parse_args().server)
