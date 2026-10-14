import re
import requests
from bs4 import BeautifulSoup

USER_AGENT = "LastAsylumPersonalRankingTracker/1.0 (public leaderboard reader; low frequency)"

class ScrapeError(Exception):
    pass

def source_url(server_id: int) -> str:
    return f"https://lastasylum.gg/en/leaderboard/servers/{server_id}"

def clean(value):
    return " ".join((value or "").replace("\xa0", " ").split())

def parse_int(value):
    digits = re.sub(r"[^\d]", "", clean(value).replace(",", ""))
    return int(digits) if digits else None

def scrape_server(server_id: int):
    url = source_url(server_id)
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    except requests.RequestException as e:
        raise ScrapeError(f"네트워크 오류: {e}") from e
    if response.status_code in (403, 429):
        raise ScrapeError(f"HTTP {response.status_code}: 사이트 접근 정책 또는 요청 제한일 수 있습니다. 재시도/우회를 반복하지 마세요.")
    if response.status_code != 200:
        raise ScrapeError(f"HTTP {response.status_code}")
    soup = BeautifulSoup(response.text, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_idx = None
        header_cells = []
        for idx, row in enumerate(rows):
            cells = [clean(c.get_text(" ", strip=True)).lower() for c in row.find_all(["th", "td"], recursive=False)]
            if "player" in " ".join(cells) and "power" in " ".join(cells):
                header_idx, header_cells = idx, cells
                break
        if header_idx is None:
            continue
        def find_col(words):
            for i, h in enumerate(header_cells):
                if any(word in h for word in words):
                    return i
            return None
        player_i = find_col(["player"])
        tag_i = find_col(["tag", "alliance"])
        power_i = find_col(["power"])
        rank_i = find_col(["#", "rank"])
        if player_i is None or power_i is None:
            continue
        result = []
        for row in rows[header_idx + 1:]:
            texts = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"], recursive=False)]
            if not texts:
                continue
            ri = rank_i if rank_i is not None else 0
            if ri >= len(texts):
                continue
            rank_match = re.search(r"\d+", texts[ri])
            if not rank_match or player_i >= len(texts) or power_i >= len(texts):
                continue
            player = texts[player_i]
            power = parse_int(texts[power_i])
            tag = texts[tag_i] if tag_i is not None and tag_i < len(texts) else ""
            if player and power is not None:
                result.append({"rank": int(rank_match.group()), "player": player, "tag": tag, "power": power})
        if result:
            return result, url
    raise ScrapeError("공개 HTML에서 랭킹 표를 찾지 못했습니다. 사이트 HTML 구조가 바뀌었을 수 있습니다.")
