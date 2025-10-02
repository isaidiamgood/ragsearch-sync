import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
import time

BASE_URL = "https://ro.gnjoy.com/itemdeal/dealSearch.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"

# DB 초기화
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            shop TEXT,
            options TEXT,
            last_update TEXT
        )
    """)
    conn.commit()
    conn.close()

# 슬롯/랜덤옵션 파싱 함수
def fetch_options(map_id, ssi, page):
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    def parse_td(th_text):
        td_opts = []
        th = soup.find("th", string=lambda x: x and th_text in x)
        if th:
            td = th.find_next("td")
            if td:
                imgs = [img.get("alt", "").strip() for img in td.find_all("img")]
                texts = [txt.strip() for txt in td.stripped_strings if txt.strip() != "없음"]

                # alt와 text 병합 (쌍 맞추기)
                for i in range(max(len(imgs), len(texts))):
                    alt = imgs[i] if i < len(imgs) else ""
                    txt = texts[i] if i < len(texts) else ""
                    val = txt or alt
                    if val and val != "없음":
                        td_opts.append(val)
        return td_opts

    # 슬롯정보 + 랜덤옵션
    options.extend(parse_td("슬롯정보"))
    options.extend(parse_td("랜덤옵션"))

    # 중복 제거 (순서 유지)
    options = list(dict.fromkeys(options))
    return options

# 아이템 스크랩
def scrape_items():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    total_inserted = 0
    max_pages = 250  # 충분히 넉넉하게

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}?svrID=129&itemFullName=의상&inclusion=&sortDESC=&curpage={page}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("table.dealList tbody tr")
        if not rows:
            print(f"[page={page}] no more items -> 종료")
            break

        inserted = 0
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name_tag = cols[1].find("span")
            name = name_tag.get_text(strip=True) if name_tag else "?"

            price_tag = cols[3].find("span")
            price_text = price_tag.get_text(strip=True).replace(",", "") if price_tag else "0"
            try:
                price = int(price_text)
            except:
                price = 0

            shop = cols[4].get_text(strip=True)

            # mapID, ssi 추출 (onclick 파라미터)
            onclick = cols[1].find("a").get("onclick", "")
            parts = onclick.split(",")
            if len(parts) >= 3:
                map_id = parts[1].strip()
                ssi = parts[2].strip().strip("'")
            else:
                map_id = "0"
                ssi = "0"

            options = fetch_options(map_id, ssi, page)
            options_str = ", ".join(options) if options else ""

            last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            c.execute("""
                INSERT INTO items (name, price, shop, options, last_update)
                VALUES (?, ?, ?, ?, ?)
            """, (name, price, shop, options_str, last_update))
            inserted += 1

        conn.commit()
        total_inserted += inserted
        print(f"[page={page}] inserted {inserted} items")

        time.sleep(2)  # 속도조절 (밴 방지)

    conn.close()
    print(f"[done] total items inserted: {total_inserted}")

    # 마지막 동기화 시간 기록
    with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# 실행부
if __name__ == "__main__":
    init_db()
    scrape_items()
