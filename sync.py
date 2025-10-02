import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import os

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"

BASE_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0 Safari/537.36"
}

def create_tables():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price TEXT,
            shop_name TEXT,
            img_url TEXT,
            map_id TEXT,
            ssi TEXT,
            page_no INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS item_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            option_text TEXT,
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
    """)
    conn.commit()
    conn.close()

def fetch_list(page):
    url = f"{BASE_URL}?svrID=129&itemFullName=의상&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    rows = soup.select("table.dealList tbody tr")
    for row in rows:
        name_tag = row.select_one("td.item a span")
        link_tag = row.select_one("td.item a")
        price_tag = row.select_one("td.price span")
        shop_tag = row.select_one("td.shop")

        if not name_tag or not link_tag:
            continue

        name = name_tag.text.strip()
        price = price_tag.text.strip() if price_tag else ""
        shop = shop_tag.text.strip() if shop_tag else ""
        link = link_tag.get("onclick", "")

        # mapID, ssi 추출
        map_id, ssi = None, None
        if "CallItemDealView" in link:
            parts = link.replace("javascript:CallItemDealView(", "").replace(")", "").split(",")
            if len(parts) >= 3:
                map_id = parts[1].strip()
                ssi = parts[2].strip().strip("'")

        # 아이콘
        img_tag = row.select_one("td.item img")
        img_url = img_tag.get("src") if img_tag else None

        items.append((name, price, shop, img_url, map_id, ssi, page))
    return items

def fetch_options(map_id, ssi, page):
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    # 슬롯정보
    slot_th = soup.find("th", string=lambda x: x and "슬롯정보" in x)
    if slot_th:
        for li in slot_th.find_next("td").find_all("li"):
            txt = li.get_text(" ", strip=True)
            if txt and txt != "없음":
                options.append(txt)

    # 랜덤옵션
    rand_th = soup.find("th", string=lambda x: x and "랜덤옵션" in x)
    if rand_th:
        for li in rand_th.find_next("td").find_all("li"):
            txt = li.get_text(" ", strip=True)
            if txt and txt != "없음":
                options.append(txt)

    return options

def update_last_sync_time():
    with open(LAST_SYNC_FILE, 'w') as file:
        file.write(time.strftime("%Y-%m-%d %H:%M:%S"))

def get_last_sync_time():
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, 'r') as file:
            return file.read().strip()
    return "없음"

def main():
    create_tables()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    total = 0
    page = 1
    max_pages = 250  # 최대 페이지 수 늘림

    while page <= max_pages:
        items = fetch_list(page)
        if not items:
            print(f"[page={page}] no more items -> 종료")
            break

        print(f"[page={page}] found {len(items)} items")
        for name, price, shop, img_url, map_id, ssi, pageno in items:
            cur.execute("""
                INSERT INTO items (name, price, shop_name, img_url, map_id, ssi, page_no)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, price, shop, img_url, map_id, ssi, pageno))
            item_id = cur.lastrowid

            if map_id and ssi:
                opts = fetch_options(map_id, ssi, page)
                for opt in opts:
                    cur.execute("INSERT INTO item_options (item_id, option_text) VALUES (?, ?)", (item_id, opt))
                    print(f"     옵션: {opt}")

            print(f"  [+] {name} ({price}) | {shop}")
            total += 1

        conn.commit()
        page += 1
        time.sleep(0.5)

    conn.close()
    print(f"[done] total items inserted: {total}")
    update_last_sync_time()

if __name__ == "__main__":
    main()
