import requests, sqlite3, time
from bs4 import BeautifulSoup

BASE_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
DETAIL_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
DB_FILE = "items.db"
SEARCH_KEYWORD = "의상"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS items")
    cur.execute("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price TEXT,
            shop TEXT,
            options TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS meta")
    cur.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    conn.commit()
    conn.close()

def save_meta(key, value):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def fetch_detail(map_id, ssi, page):
    url = f"{DETAIL_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    try:
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        options = [span.get_text(strip=True) for span in soup.select(".item_detail_option span") if span.get_text(strip=True)]
        return " | ".join(options) if options else "-"
    except Exception as e:
        print(f"[warn] 상세페이지 파싱 실패: {e}")
        return "-"

def fetch_all():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    total_saved = 0
    page = 1

    while True:
        url = f"{BASE_URL}?itemFullName={SEARCH_KEYWORD}&curpage={page}"
        r = requests.get(url, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select(".item_list tbody tr")

        if not items:
            print(f"[stop] page={page} 아이템 없음. 종료.")
            break

        # 10개보다 적으면 마지막 페이지 처리
        if len(items) < 10:
            print(f"[stop] page={page} ({len(items)} items) 마지막 페이지 감지.")
            stop_next = True
        else:
            stop_next = False

        for row in items:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            name = cols[0].get_text(strip=True)
            price = cols[1].get_text(strip=True)
            shop = cols[2].get_text(strip=True)

            options = "-"
            link = cols[0].select_one("a")
            if link and "onclick" in link.attrs:
                try:
                    onclick = link["onclick"]
                    map_id = onclick.split("mapID=")[1].split("&")[0]
                    ssi = onclick.split("ssi=")[1].split("&")[0]
                    options = fetch_detail(map_id, ssi, page)
                except Exception as e:
                    print(f"[warn] onclick 파싱 실패: {e}")

            cur.execute(
                "INSERT INTO items (name, price, shop, options) VALUES (?, ?, ?, ?)",
                (name, price, shop, options),
            )
            total_saved += 1

        conn.commit()
        print(f"[page={page}] {len(items)} items processed (총 {total_saved} 개)")

        if stop_next:
            break
        page += 1

    conn.close()
    return total_saved

def main():
    init_db()
    total = fetch_all()
    save_meta("last_sync", time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"[done] items.db 생성 완료. 총 {total} 개 아이템 저장")

if __name__ == "__main__":
    main()

