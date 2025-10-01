import sqlite3
import os
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QListWidget, QLabel

DB_FILE = "items.db"
LAST_SYNC_FILE = "last_sync.txt"

def get_last_sync_time():
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, 'r') as file:
            return file.read().strip()
    return "동기화 기록 없음"

class SearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("라그 의상 검색기 (이름+옵션)")
        self.resize(680, 480)

        layout = QVBoxLayout()

        self.label_name = QLabel("아이템 이름:")
        layout.addWidget(self.label_name)
        self.input_name = QLineEdit()
        layout.addWidget(self.input_name)

        self.label_opt = QLabel("옵션(슬롯정보):")
        layout.addWidget(self.label_opt)
        self.input_opt = QLineEdit()
        layout.addWidget(self.input_opt)

        self.label_last_sync = QLabel(f"마지막 동기화 시간: {get_last_sync_time()}")
        layout.addWidget(self.label_last_sync)

        self.btn_refresh = QPushButton("리프레시")
        self.btn_refresh.clicked.connect(self.refresh_data)
        layout.addWidget(self.btn_refresh)

        self.btn = QPushButton("검색")
        self.btn.clicked.connect(self.search)
        layout.addWidget(self.btn)

        self.result = QListWidget()
        layout.addWidget(self.result)

        self.setLayout(layout)

    def refresh_data(self):
        # GitHub에서 최신 데이터 다운로드하여 덮어씌우기
        print("다운로드 시작...")
        self.label_last_sync.setText("동기화 중...")
        time.sleep(2)  # Simulating downloading data
        # 다운로드 완료 후 동기화 시간 갱신
        self.update_last_sync_time()
        self.label_last_sync.setText(f"마지막 동기화 시간: {get_last_sync_time()}")

    def update_last_sync_time(self):
        # 마지막 동기화 시간을 기록
        with open(LAST_SYNC_FILE, 'w') as file:
            file.write(time.strftime("%Y-%m-%d %H:%M:%S"))

    def search(self):
        name = self.input_name.text().strip()
        opt = self.input_opt.text().strip()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        q = """
        SELECT DISTINCT i.id, i.name, i.price,
               COALESCE((
                   SELECT group_concat(option_text, ' | ')
                   FROM item_options io2
                   WHERE io2.item_id = i.id
               ), '') AS opts
        FROM items i
        LEFT JOIN item_options io ON io.item_id = i.id
        WHERE 1=1
        """
        params = []

        if name:
            q += " AND i.name LIKE ?"
            params.append(f"%{name}%")
        if opt:
            q += " AND EXISTS (SELECT 1 FROM item_options io3 WHERE io3.item_id = i.id AND io3.option_text LIKE ?)"
            params.append(f"%{opt}%")

        q += " ORDER BY i.name LIMIT 500"

        cur.execute(q, params)
        rows = cur.fetchall()
        conn.close()

        self.result.clear()
        if not rows:
            self.result.addItem("검색 결과 없음")
            return

        for _, nm, price, opts in rows:
            preview = (opts[:120] + "…") if len(opts) > 120 else opts
            self.result.addItem(f"{nm} | {price} | {preview}")

def main():
    app = QApplication([])
    win = SearchApp()
    win.show()
    app.exec_()

if __name__ == "__main__":
    main()
