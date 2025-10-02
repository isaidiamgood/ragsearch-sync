import requests
import sqlite3
import time
from bs4 import BeautifulSoup

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"

BASE_URL = "https://ro.gnjoy.com/itemdeal/dealSearch.asp"

def fetch_page(page):
    """해당 페이지 HTML 가져오기"""
    url = f"{BASE_URL}?itemFullName=의상&page={page}"
    res = requests.get(url, timeout=10)
    res.encoding = "utf-8"
    return BeautifulSoup(res.text, "html.parser")


def scrape_items():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # items 테이블 생성
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

    # 매번 실행 시 기존 데이터 삭제 후 다시 넣기
    c.execute("DELETE FROM items")

    total_inserted = 0

    for page in range(1, 300):  # 넉넉히 300페이지까지
        soup = fetch_page(page)
        rows = soup.select("table.dealList tbody tr")

        # --- 탈출 조건 ---
        if not rows or "검색결과 없음" in soup.text:
            print(f"[page={page}] no more items → 종료")
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name = cols[1].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            shop = cols[4].get_text(strip=True)

            # 아이템 상세 페이지 들어가서 옵션 정보 가져오기
            link_tag = cols[1].find("a")
            options = ""
            if link_tag and "CallItemDealView" in link_tag.get("onclick", ""):
                try:
                    # 파라미터 추출
                    onclick = link_tag["onclick"]
                    parts = onclick.split(",")
                    svrID, mapID, ssi = parts[0].split("(")[1], parts[1], parts[2]
                    detail_url = f"https://ro.gnjoy.com/itemdeal/itemDealView.asp?svrID={svrID.strip()}&mapID={mapID.strip()}&ssi={ssi.strip()}&curpage={page}"

                    detail_res = requests.get(detail_url, timeout=10)
                    detail_res.encoding = "utf-8"
                    detail_soup = BeautifulSoup(detail_res.text, "html.parser")

                    slot_info = detail_soup.select("th:contains('슬롯정보') + td ul li")
                    opts = [li.get_text(" ", strip=True) for li in slot_info]
                    options = " | ".join(opts) if opts else ""
                except Exception as e:
                    print(f"옵션 파싱 오류: {e}")

            # None 또는 빈 값이면 "없음" 대신 "" 저장 (안 보이게 처리)
            options = options if options else ""

            c.execute(
                "INSERT INTO items (name, price, shop, options, last_update) VALUES (?,?,?,?,datetime('now','localtime'))",
                (name, price, shop, options)
            )

        conn.commit()
        total_inserted += len(rows)
        print(f"[page={page}] inserted {len(rows)} items")

        time.sleep(1.5)  # 서버 과부하 방지

    conn.close()
    print(f"[done] total items inserted: {total_inserted}")

    # 동기화 시간 기록
    with open(LAST_SYNC_FILE, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    scrape_items()
