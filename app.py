import os
import secrets
from datetime import datetime, timezone
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from scraper import scrape_server, ScrapeError

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ["DATABASE_URL"]
DASH_USER = os.environ["DASHBOARD_USERNAME"]
DASH_PASS = os.environ["DASHBOARD_PASSWORD"]
security = HTTPBasic()
app = FastAPI(title="Last Asylum Private Ranking Tracker")

def auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, DASH_USER) and secrets.compare_digest(credentials.password, DASH_PASS)
    if not ok:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": 'Basic realm="Last Asylum Tracker"'})
    return credentials.username

def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)

def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            id BIGSERIAL PRIMARY KEY, captured_at TIMESTAMPTZ NOT NULL,
            server_id INTEGER NOT NULL, rank INTEGER NOT NULL, player_name TEXT NOT NULL,
            alliance_tag TEXT NOT NULL DEFAULT '', power BIGINT NOT NULL,
            power_delta BIGINT, rank_change INTEGER)""")
        conn.execute("CREATE INDEX IF NOT EXISTS snapshots_server_time_idx ON snapshots(server_id, captured_at DESC)")

@app.on_event("startup")
def startup():
    init_db()

app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static")

@app.get("/")
def home(_: str = Depends(auth)):
    return FileResponse(os.path.join(APP_DIR, "static", "index.html"))

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/data")
def data(server_id: int = 149, _: str = Depends(auth)):
    if not 1 <= server_id <= 9999:
        raise HTTPException(400, "Invalid server number")
    with connect() as conn:
        latest = conn.execute("SELECT MAX(captured_at) AS ts FROM snapshots WHERE server_id=%s", (server_id,)).fetchone()["ts"]
        count = conn.execute("SELECT COUNT(*) AS n FROM snapshots WHERE server_id=%s", (server_id,)).fetchone()["n"]
        if latest is None:
            return {"server_id": server_id, "captured_at": None, "history_count": count, "rows": [], "message": "아직 수집 기록이 없습니다. ‘지금 수집’을 눌러 첫 기록을 만드세요."}
        rows = conn.execute("""SELECT rank, player_name, alliance_tag, power, power_delta, rank_change
            FROM snapshots WHERE server_id=%s AND captured_at=%s ORDER BY rank""", (server_id, latest)).fetchall()
    return {"server_id": server_id, "captured_at": latest.isoformat(), "history_count": count,
            "rows": [{"rank": r["rank"], "player": r["player_name"], "tag": r["alliance_tag"], "power": r["power"], "power_delta": r["power_delta"], "rank_change": r["rank_change"]} for r in rows],
            "message": "출처: LastAsylum.gg 공개 서버 랭킹 HTML. 증감은 직전 스냅샷과 비교합니다."}

@app.get("/api/history")
def history(server_id: int = 149, days: int = 30, _: str = Depends(auth)):
    if not 1 <= server_id <= 9999 or not 1 <= days <= 365:
        raise HTTPException(400, "Invalid server_id or days")
    with connect() as conn:
        rows = conn.execute("""WITH per_day AS (
            SELECT date_trunc('day', captured_at) AS day, COUNT(*) AS players,
            SUM(power) AS top_power, AVG(power)::BIGINT AS avg_power
            FROM snapshots WHERE server_id=%s AND captured_at >= now() - (%s * interval '1 day')
            GROUP BY date_trunc('day', captured_at))
            SELECT day, players, top_power, avg_power FROM per_day ORDER BY day""", (server_id, days)).fetchall()
    return [{"day": r["day"].isoformat(), "players": r["players"], "top_power": r["top_power"], "avg_power": r["avg_power"]} for r in rows]

@app.post("/api/collect")
def collect(server_id: int = 149, _: str = Depends(auth)):
    if not 1 <= server_id <= 9999:
        raise HTTPException(400, "Invalid server number")
    try:
        players, source_url = scrape_server(server_id)
    except ScrapeError as e:
        raise HTTPException(502, f"공개 페이지 수집 실패: {e}")
    if not players:
        raise HTTPException(502, "랭킹 결과가 비어 있어 저장하지 않았습니다.")
    captured_at = datetime.now(timezone.utc)
    with connect() as conn:
        prev = conn.execute("SELECT MAX(captured_at) AS ts FROM snapshots WHERE server_id=%s", (server_id,)).fetchone()["ts"]
        old_map = {}
        if prev:
            old_rows = conn.execute("SELECT player_name, alliance_tag, rank, power FROM snapshots WHERE server_id=%s AND captured_at=%s", (server_id, prev)).fetchall()
            old_map = {(r["player_name"], r["alliance_tag"]): (r["rank"], r["power"]) for r in old_rows}
        for p in players:
            old = old_map.get((p["player"], p["tag"]))
            conn.execute("""INSERT INTO snapshots(captured_at,server_id,rank,player_name,alliance_tag,power,power_delta,rank_change)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (captured_at, server_id, p["rank"], p["player"], p["tag"], p["power"],
                 p["power"]-old[1] if old else None, old[0]-p["rank"] if old else None))
    return {"ok": True, "server_id": server_id, "captured_at": captured_at.isoformat(), "count": len(players), "source_url": source_url, "message": f"서버 {server_id}: {len(players)}명 수집 완료"}

@app.get("/api/export")
def export(server_id: int = 149, _: str = Depends(auth)):
    import csv, io
    if not 1 <= server_id <= 9999:
        raise HTTPException(400, "Invalid server number")
    with connect() as conn:
        rows = conn.execute("""SELECT captured_at, server_id, rank, player_name, alliance_tag, power, power_delta, rank_change
            FROM snapshots WHERE server_id=%s ORDER BY captured_at, rank""", (server_id,)).fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["captured_at","server_id","rank","player","alliance_tag","power","power_delta","rank_change"])
    for r in rows:
        writer.writerow([r["captured_at"].isoformat(), r["server_id"], r["rank"], r["player_name"], r["alliance_tag"], r["power"], r["power_delta"], r["rank_change"]])
    content = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="server_{server_id}_ranking_history.csv"'})
