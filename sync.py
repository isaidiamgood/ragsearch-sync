import requests
import sqlite3
import os
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://ro.gnjoy.com/itemdeal/dealSearch.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
DB_FILE = "items.db"
SYNC_FILE = "last_sync.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://ro.gnjoy.com/itemdeal/dealSearch.asp"
}

# DB 초기화
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price TEXT,
            shop TEXT,
            options TEXT,
            last_update TEXT
        )
    """)
    conn.commit()
    conn.close()

# 상세 페이지에서 슬롯/옵션 추출
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
            # 이미지 alt
            for img in td.find_all("img"):
                alt = img.get("alt", "").strip()
                if alt and alt != "없음":
                    options.append(alt)
            # 텍스트
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

# 메인 크롤링
def scrape_items():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    total_inserted = 0
    max_pages = 250  # 페이지 넉넉하게 설정

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}?svrID=129&itemFullName=의상&inclusion=&sortDESC=&curpage={page}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("table.dealList tr")
        if not rows or len(rows) < 2:
            print(f"[page={page}] no more items -> 종료")
            break

        inserted = 0
        for row in rows[1:]:  # 헤더 스킵
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            server = cols[0].get_text(strip=True)
            name = cols[1].get_text(strip=True)
            quantity = cols[2].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            shop = cols[4].get_text(strip=True)

            # 상세 링크 (옵션 가져오기)
            detail_a = cols[1].find("a")
            options = []
            if detail_a and "CallItemDealView" in detail_a.get("onclick", ""):
                onclick = detail_a["onclick"]
                parts = onclick.replace("CallItemDealView(", "").replace(")", "").split(",")
                if len(parts) >= 3:
                    map_id = parts[1].strip()
                    ssi = parts[2].strip().strip("'")
                    options = fetch_options(map_id, ssi, page)

            # DB 저장
            c.execute(
                "INSERT INTO items (name, price, shop, options, last_update) VALUES (?,?,?,?,?)",
                (name, price, shop, ", ".join(options), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            inserted += 1

        conn.commit()
        total_inserted += inserted
        print(f"[page={page}] found {inserted} items")

    conn.close()
    print(f"[done] total items inserted: {total_inserted}")

    # last_sync.txt 업데이트
    with open(SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == "__main__":
    init_db()
    scrape_items()
