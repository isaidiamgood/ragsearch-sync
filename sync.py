import sqlite3, os, time, requests
from bs4 import BeautifulSoup

LIST_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
CLOTHES_URL = "https://ro.gnjoy.com/guide/runemidgarts/itemclotheslist.asp"

HEADERS = {"User-Agent": "Mozilla/5.0"}

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"


# -------------------- DB 초기화 --------------------
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
        part TEXT,
        options TEXT,
        last_updated TEXT
    )
    """)
    conn.commit()
    conn.close()


# -------------------- 마지막 동기화 시간 기록 --------------------
def update_last_sync_time():
    with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))


# -------------------- 의상 아이템 부위 마스터 목록 생성 --------------------
def build_part_dict():
    part_dict = {}
    page = 1
    while True:
        url = f"{CLOTHES_URL}?ordername=Seq&ordertype=ASC&curpage={page}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        rows = soup.select("table.guidelist tbody tr")
        if not rows:
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            name = cols[1].get_text(strip=True)
            part = cols[2].get_text(strip=True)
            if name and part:
                part_dict[name] = part

        page += 1

    print(f"[part_dict] {len(part_dict)}개 의상 아이템 부위 정보 로드 완료")
    return part_dict


# -------------------- 옵션 파싱 --------------------
def fetch_options(map_id, ssi, page):
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []

    for th in soup.find_all("th"):
        if not th.string:
            continue
        if any(key in th.string for key in ["슬롯정보", "랜덤옵션"]):
            td = th.find_next("td")
            if td:
                # 이미지 ALT
                for img in td.find_all("img"):
                    alt = img.get("alt", "").strip()
                    if alt and alt != "없음":
                        options.append(alt)
                # 텍스트 값
                for txt in td.stripped_strings:
                    if txt and txt != "없음" and not txt.endswith(": 0"):
                        options.append(txt)

    # 중복 제거
    options = list(dict.fromkeys(options))
    return options


# -------------------- 한 페이지 크롤링 --------------------
def fetch_page(cur, page, part_dict, total_saved):
    params = {
        "svrID": "129",   # 바포메트 서버 고정
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

        # 부위 매칭 (없으면 미분류)
        part = part_dict.get(name, "미분류")

        options = []
        if item_tag:
            onclick = item_tag.get("onclick", "")
            if "CallItemDealView" in onclick:
                try:
                    parts = onclick.split("(")[1].split(")")[0].split(",")
                    map_id, ssi = parts[1].strip(), parts[2].strip().strip("'")
                    options = fetch_options(map_id, ssi, page)
                except Exception as e:
                    print(f"[warn] 옵션 파싱 실패: {e}")

        options_str = " | ".join(options) if options else "-"
        total_saved += 1
        print(f"[save] {name} | {price} | {part} | {shop} | {options_str} (누적 {total_saved}개 저장)")

        cur.execute("""
            INSERT INTO items (name, server, quantity, price, shop, part, options, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, server, quantity, price, shop, part, options_str, time.strftime("%Y-%m-%d %H:%M:%S")))

        count += 1

    print(f"[page={page}] {count} items processed (누적 {total_saved}개)")

    # 마지막 페이지 감지 (10개 미만)
    if count < 10:
        print(f"[page={page}] 마지막 페이지 감지 (10개 미만) -> 종료")
        return False, total_saved

    return True, total_saved


# -------------------- 메인 실행 --------------------
def main():
    init_db()
    part_dict = build_part_dict()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    page = 1
    total_saved = 0
    while True:
        ok, total_saved = fetch_page(cur, page, part_dict, total_saved)
        if not ok:
            break
        page += 1

    conn.commit()
    conn.close()
    update_last_sync_time()
    print(f"[done] items.db 새로 생성 완료. 총 {total_saved}개 아이템 저장됨")


if __name__ == "__main__":
    main()
