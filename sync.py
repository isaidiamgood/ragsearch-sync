import requests
import sqlite3
import time
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://ro.gnjoy.com/itemdeal/dealSearch.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DB_FILE = "items.db"

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

# 옵션/슬롯 정보 추출
def fetch_options(map_id, ssi, page):
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    # 슬롯정보
    slot_th = soup.find("th", string=lambda x: x and "슬롯정보" in x)
    if slot_th:
        td = slot_th.find_next("td")
        if td:
            for img in td.find_all("img"):
                alt = img.get("alt", "").strip()
                if alt and alt != "없음":
                    options.append(alt)
            for txt in td.stripped_strings:
                if txt and txt != "없음" and not txt.endswith(": 0"):
                    options.append(txt)

    # 랜덤옵션
    rand_th = soup.find("th", string=lambda x: x and "랜덤옵션" in x)
    if rand_th:
        td = rand_th.find_next("td")
        if td:
            for img in td.find_all("img"):
                alt = img.get("alt", "").strip()
                if alt and alt != "없음":
                    options.append(alt)
            for txt in td.stripped_strings:
                if txt and txt != "없음":
                    options.append(txt)

    # 중복 제거
    options = list(dict.fromkeys(options))
    return options

# 아이템 데이터 크롤링
def scrape_items(max_pages=250):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    total_inserted = 0

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}?svrID=129&itemFullName=의상&inclusion=&orderby=DESC&curpage={page}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("table.dealList tbody tr")
        if not rows:
            print(f"[page={page}] no more items => 종료")
            break

        found = 0
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            server = cols[0].get_text(strip=True)
            item_link = cols[1].find("a")
            if not item_link:
                continue

            item_name = cols[1].get_text(strip=True)
            qty = cols[2].get_text(strip=True)
            price_text = cols[3].get_text(strip=True).replace(",", "")
            try:
                price = int(price_text)
            except:
                price = 0
            shop = cols[4].get_text(strip=True)

            # itemDealView용 파라미터
            onclick = item_link.get("onclick", "")
            try:
                parts = onclick.split("(")[1].split(")")[0].split(",")
                map_id = parts[1].strip()
                ssi = parts[2].strip().strip("'")
            except:
                continue

            options = fetch_options(map_id, ssi, page)
            options_str = ", ".join(options) if options else ""

            c.execute(
                "INSERT INTO items (name, price, shop, options, last_update) VALUES (?, ?, ?, ?, ?)",
                (item_name, price, shop, options_str, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            found += 1
            total_inserted += 1

        conn.commit()
        print(f"[page={page}] found {found} items")

        time.sleep(1)  # 서버 부담 줄이기

    conn.close()
    print(f"[done] total items inserted: {total_inserted}")

if __name__ == "__main__":
    init_db()
    scrape_items()
