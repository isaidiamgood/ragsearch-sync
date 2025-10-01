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
    """옵션 텍스트를 모두 긁어옴 (li뿐 아니라 td 내부 모든 태그 포함)"""
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    # 슬롯 정보
    slot_td = soup.select_one("th:contains('슬롯정보') + td")
    if slot_td:
        for txt in slot_td.stripped_strings:
            if txt and txt != "-":
                options.append(txt.strip())

    # 랜덤 옵션
    rand_td = soup.select_one("th:contains('랜덤옵션') + td")
    if rand_td:
        for txt in rand_td.stripped_strings:
            if txt and txt != "-":
                options.append(txt.strip())

    return options

def update_last_sync_time():
    with open(LAST_SYNC_FILE, 'w', encoding="utf-8") as file:
        file.write(time.strftime("%Y-%m-%d %H:%M:%S"))

def get_last_sync_time():
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, 'r', encoding="utf-8") as file:
            return file.read().strip()
    return "없음"

def main():
    create_tables()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    total = 0
    page = 1
    while True:
        items = fetch_list(page)
        if not items:
            print(f"[page={page}] found 0 items -> 종료")
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
