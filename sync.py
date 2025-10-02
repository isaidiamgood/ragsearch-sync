import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import time

BASE_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"

# DB 준비 (기존 테이블 지우고 새로 생성)
conn = sqlite3.connect("items.db")
c = conn.cursor()
c.execute("DROP TABLE IF EXISTS items")
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

def fetch_page(page=1, keyword="의상"):
    url = f"{BASE_URL}?svrID=129&itemFullName={keyword}&inclusion=&sortType=DESC&curpage={page}"
    res = requests.get(url)
    res.encoding = "utf-8"
    return BeautifulSoup(res.text, "html.parser")

def fetch_detail(detail_url):
    res = requests.get(detail_url)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    # 슬롯 정보
    slot_info_list = soup.select("th:contains('슬롯정보') + td.listCell ul li")
    slot_text = ", ".join(li.get_text(strip=True) for li in slot_info_list) if slot_info_list else ""

    # 랜덤 옵션
    random_options_list = soup.select("th:contains('랜덤옵션') + td.listCell ul li")
    random_options = ", ".join(li.get_text(strip=True) for li in random_options_list) if random_options_list else ""

    options = ", ".join(filter(None, [slot_text, random_options]))
    return options

def scrape_items():
    total_inserted = 0
    for page in range(1, 200):  # 페이지 넉넉히
        soup = fetch_page(page)
        rows = soup.select("table.dealList tbody tr")
        if not rows:
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name = cols[1].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            shop = cols[4].get_text(strip=True)

            # detail 링크 추출
            detail_link = cols[1].select_one("a")
            if detail_link and "onclick" in detail_link.attrs:
                onclick = detail_link["onclick"]
                try:
                    params = onclick.split("(")[1].split(")")[0].split(",")
                    svrID, mapID, ssi, curpage = [p.strip().strip("'") for p in params]
                    detail_url = f"https://ro.gnjoy.com/itemdeal/itemDealView.asp?svrID={svrID}&mapID={mapID}&ssi={ssi}&curpage={curpage}"
                    options = fetch_detail(detail_url)
                except Exception:
                    options = ""
            else:
                options = ""

            c.execute("INSERT INTO items (name, price, shop, options, last_update) VALUES (?,?,?,?,?)",
                      (name, price, shop, options, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            total_inserted += 1

        print(f"[page={page}] inserted {len(rows)} items")
        time.sleep(1.5)

    conn.commit()
    print(f"[done] total items inserted: {total_inserted}")

if __name__ == "__main__":
    scrape_items()
    with open("last_sync.txt", "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
