import re
import requests
from bs4 import BeautifulSoup

USER_AGENT = "LastAsylumPersonalRankingTracker/1.0 (public leaderboard reader; low frequency)"

class ScrapeError(Exception):
    pass

def source_url(server_id: int) -> str:
    return f"https://lastasylum.gg/en/leaderboard/servers/{server_id}/heroes"

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
            joined = " ".join(cells)
            # The leaderboard labels this metric as "Hero Might" on some views
            # and "Hero Total Power" on others. Do not require the word "total".
            if "player" in joined and any(
                ("hero" in h and ("might" in h or "power" in h))
                for h in cells
            ):
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
        # Accept the hero-specific metric labels used by the source. Never
        # fall back to a generic account "Power" column.
        power_i = next((i for i, h in enumerate(header_cells)
                        if "hero" in h and "might" in h), None)
        if power_i is None:
            power_i = next((i for i, h in enumerate(header_cells)
                            if "hero" in h and "power" in h), None)
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
    # Include the page title and candidate table headers to make future site
    # markup changes diagnosable from the Actions log.
    title = clean(soup.title.get_text(" ", strip=True)) if soup.title else "(제목 없음)"
    headers = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr")[:5]:
            cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if cells:
                headers.append(" | ".join(cells))
    detail = " / ".join(headers[:8]) if headers else "(HTML에 table 요소 없음)"
    raise ScrapeError(
        f"영웅 전투력 열을 찾지 못했습니다. page_title={title!r}; "
        f"table_headers={detail!r}. 일반 계정 Power 열로 대체하지 않았습니다."
    )
