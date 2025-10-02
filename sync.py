import sqlite3, os, time, requests, re
from bs4 import BeautifulSoup

LIST_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"


def init_db():
    # 매번 새 DB로 초기화
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
    params = {
        "svrID": "129",          # 바포메트 서버 고정
        "itemFullName": "의상",  # 검색어 고정
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
        return False

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

        options = ""
        if item_tag:
            onclick = item_tag.get("onclick", "")
            if "CallItemDealView" in onclick:
                try:
                    parts = onclick.split("(")[1].split(")")[0].split(",")
                    map_id, ssi = parts[1].strip(), parts[2].strip().strip("'")
                    opt_list = fetch_options(map_id, ssi, page)
                    options = " | ".join(opt_list)
                except Exception as e:
                    print(f"[warn] 옵션 파싱 실패: {e}")

        cur.execute("""
            INSERT INTO items (name, server, quantity, price, shop, options, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, server, quantity, price, shop, options, time.strftime("%Y-%m-%d %H:%M:%S")))

    print(f"[page={page}] {len(rows)} items processed")
    return True


def main():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # 1페이지에서 총 검색결과 파싱
    r = requests.get(LIST_URL, params={
        "svrID": "129",
        "itemFullName": "의상",
        "itemOrder": "",
        "inclusion": "",
        "curpage": 1,
    }, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    total_items, total_pages = 0, 1
    result_div = soup.find("div", class_="searchResult")
    if result_div:
        m = re.search(r"([\d,]+)건", result_div.get_text())
        if m:
            total_items = int(m.group(1).replace(",", ""))
            total_pages = (total_items // 10) + (1 if total_items % 10 else 0)
    print(f"[info] total_items={total_items}, total_pages={total_pages}")

    # 첫 페이지 수집
    fetch_page(cur, 1)

    # 2페이지 이후 순회
    for page in range(2, total_pages + 1):
        ok = fetch_page(cur, page)
        if not ok:
            break

    conn.commit()
    conn.close()
    update_last_sync_time()
    print("[done] items.db 새로 생성 완료")


if __name__ == "__main__":
    main()
