import sqlite3, os, time, requests
from bs4 import BeautifulSoup

LIST_URL = "https://ro.gnjoy.com/itemdeal/itemDealList.asp"
VIEW_URL = "https://ro.gnjoy.com/itemdeal/itemDealView.asp"
CLOTHES_URL = "https://ro.gnjoy.com/guide/runemidgarts/itemClothesList.asp"
HEADERS = {"User-Agent": "Mozilla/5.0"}

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"


# -------------------------
# DB 초기화
# -------------------------
def init_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price TEXT,
        part TEXT,
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


# -------------------------
# 이름 전처리 (normalize)
# -------------------------
def normalize_name(name: str) -> str:
    return name.replace("의상 ", "").replace(" ", "").lower()


# -------------------------
# 의상 아이템 부위 정보 로드
# -------------------------
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
                part_dict[normalize_name(name)] = part

        page += 1

    print(f"[part_dict] {len(part_dict)}개 의상 아이템 부위 정보 로드 완료")
    return part_dict


# -------------------------
# 상세 옵션 파싱
# -------------------------
def fetch_options(map_id, ssi, page):
    url = f"{VIEW_URL}?svrID=129&mapID={map_id}&ssi={ssi}&curpage={page}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    options = []
    for th in soup.find_all("th"):
        if th.get_text(strip=True) in ["슬롯정보", "랜덤옵션"]:
            td = th.find_next("td")
            if td:
                for img in td.find_all("img"):
                    alt = img.get("alt", "").strip()
                    if alt and alt != "없음":
                        options.append(alt)
                for txt in td.stripped_strings:
                    if txt and txt != "없음" and not txt.endswith(": 0"):
                        options.append(txt)

    options = list(dict.fromkeys(options))
    return options


# -------------------------
# 페이지별 아이템 파싱
# -------------------------
def fetch_page(cur, page, part_dict, total_count):
    params = {
        "svrID": "129",
        "itemFullName": "의상",
        "curpage": page,
    }
    r = requests.get(LIST_URL, params=params, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("table.dealList tbody tr")
    if not rows:
        print(f"[page={page}] no more items -> 종료")
        return False, total_count

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        item_tag = cols[1].find("a")
        name = item_tag.get_text(strip=True) if item_tag else "?"
        price = cols[3].get_text(strip=True)
        shop = cols[4].get_text(strip=True)

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

        # 부위 매칭 (normalize 적용)
        part = part_dict.get(normalize_name(name), "미분류")

        total_count += 1
        print(f"[save] {name} | {price} | {part} | {shop} | {options_str} (누적 {total_count}개 저장)")

        cur.execute("""
            INSERT INTO items (name, price, part, shop, options, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, price, part, shop, options_str, time.strftime("%Y-%m-%d %H:%M:%S")))

    print(f"[page={page}] {len(rows)} items processed (누적 {total_count}개)")
    if len(rows) < 10:
        print(f"[page={page}] 마지막 페이지 감지 (10개 미만) -> 종료")
        return False, total_count
    return True, total_count


# -------------------------
# 실행 메인
# -------------------------
def main():
    init_db()
    part_dict = build_part_dict()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    page, total_count = 1, 0
    while True:
        ok, total_count = fetch_page(cur, page, part_dict, total_count)
        if not ok:
            break
        page += 1

    conn.commit()
    conn.close()
    update_last_sync_time()
    print(f"[done] items.db 새로 생성 완료. 총 {total_count}개 아이템 저장됨")


if __name__ == "__main__":
    main()
