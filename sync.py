import sqlite3, os, time, requests
from bs4 import BeautifulSoup

LIST_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"


def init_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        server TEXT,
        quantity TEXT,
        price TEXT,
        shop TEXT,
        options TEXT,
        last_updated TEXT
    )
    """)
    conn.commit()
    conn.close()


def update_last_sync_time():
    with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))


def fetch_options(map_id, ssi, page):
    """상세 페이지에서 슬롯/랜덤옵션/추가 텍스트까지 전부 긁어오기"""
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    print(f"[debug] 상세페이지 요청: {url}")
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    # 옵션 테이블 전체 탐색
    for th in soup.find_all("th"):
        if any(key in th.get_text() for key in ["슬롯정보", "랜덤옵션"]):
            td = th.find_next("td")
            if td:
                # 이미지 alt
                for img in td.find_all("img"):
                    alt = img.get("alt", "").strip()
                    if alt and alt != "없음":
                        options.append(alt)
                # 텍스트
                for txt in td.stripped_strings:
                    if txt and txt != "없음" and not txt.endswith(": 0"):
                        options.append(txt)

    # 혹시 남아있는 다른 옵션 td들도 긁기
    etc_tds = soup.select("table tr td")
    for td in etc_tds:
        for txt in td.stripped_strings:
            if txt and txt != "없음" and not txt.endswith(": 0"):
                options.append(txt)

    # 중복 제거
    options = list(dict.fromkeys(options))

    if not options:
        print(f"[warn] 옵션 없음 -> url={url}")

    return options


def fetch_page(cur, page, total_saved):
    params = {
        "svrID": "129",
        "itemFullName": "의상",
        "itemOrder": "",
        "inclusion": "",
        "curpage": page,
    }
    r = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("table.dealList tbody tr")
    if not rows:
        print(f"[page={page}] no more items -> 종료")
        return False, total_saved

    count = 0
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        server = cols[0].get_text(strip=True)
        item_tag = cols[1].find("a")
        name = item_tag.get_text(strip=True) if item_tag else "?"
        quantity = cols[2].get_text(strip=True)
        price = cols[3].get_text(strip=True)
        shop = cols[4].get_text(strip=True)

        options = []
        if item_tag:
            onclick = item_tag.get("onclick", "")
            if "CallItemDealView" in onclick:
                try:
                    parts = onclick.split("(")[1].split(")")[0].split(",")
                    map_id, ssi = parts[1].strip(), parts[2].strip().strip("'")
                    print(f"[debug] onclick 파싱 성공: map_id={map_id}, ssi={ssi}")
                    options = fetch_options(map_id, ssi, page)
                except Exception as e:
                    print(f"[warn] 옵션 파싱 실패: {e}")

        options_str = " | ".join(options) if options else "-"
        total_saved += 1
        print(f"[save] {name} | {price} | {shop} | {options_str} (누적 {total_saved}개 저장)")

        cur.execute("""
            INSERT INTO items (name, server, quantity, price, shop, options, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, server, quantity, price, shop, options_str, time.strftime("%Y-%m-%d %H:%M:%S")))
        count += 1

    print(f"[page={page}] {count} items processed (누적 {total_saved}개)")

    # 마지막 페이지 감지
    if count < 10:
        print(f"[page={page}] 마지막 페이지 감지 (10개 미만) -> 종료")
        return False, total_saved

    return True, total_saved


def main():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    page = 1
    total_saved = 0
    while True:
        ok, total_saved = fetch_page(cur, page, total_saved)
        if not ok:
            break
        page += 1

    conn.commit()
    conn.close()
    update_last_sync_time()
    print(f"[done] items.db 새로 생성 완료. 총 {total_saved}개 아이템 저장됨")


if __name__ == "__main__":
    main()
