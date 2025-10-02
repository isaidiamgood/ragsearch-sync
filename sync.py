import requests
import sqlite3
import os
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

DB_FILE = "items.db"
SYNC_FILE = "last_sync.txt"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
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
    return conn


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


def fetch_page(cur, page):
    url = f"{BASE_URL}?svrID=&itemFullName=의상&itemOrder=&inclusion=&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("table.dealList tbody tr")
    if not rows:
        print(f"[page={page}] no more items -> 종료")
        return False

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        server = cols[0].get_text(strip=True)
        name = cols[1].get_text(strip=True)
        quantity = cols[2].get_text(strip=True)
        price = cols[3].get_text(strip=True)
        shop = cols[4].get_text(strip=True)

        # detail 링크 파라미터 추출
        link = cols[1].find("a")
        options = []
        if link and "CallItemDealView" in link.get("onclick", ""):
            try:
                args = link["onclick"].split("(")[1].split(")")[0].split(",")
                map_id = args[1].strip()
                ssi = args[2].strip().strip("'")
                options = fetch_options(map_id, ssi, page)
            except Exception as e:
                print("option fetch error:", e)

        cur.execute("""
            INSERT INTO items (name, server, quantity, price, shop, options, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, server, quantity, price, shop, "\n".join(options), datetime.now().isoformat()))

    return True


def main():
    conn = init_db()
    cur = conn.cursor()

    page = 1
    total = 0
    while True:
        ok = fetch_page(cur, page)
        if not ok:
            break
        conn.commit()
        total += 1
        page += 1

    conn.close()

    # 마지막 동기화 시간 기록
    with open(SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    print(f"[done] total pages parsed: {total}")


if __name__ == "__main__":
    main()
