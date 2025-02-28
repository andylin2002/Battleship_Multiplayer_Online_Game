import tkinter as tk
from tkinter import scrolledtext
import socket
import threading

# 初始化遊戲變數
BOARD_ROWS = 7
BOARD_COLS = 8
ships_positions = set()
buttons = []
ship_types = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2),
]
current_ship_index = 0
current_ship_cells = []
is_my_turn = False  # 是否為本方回合

# 更新文字區域
def update_text_area(message):
    text_area.config(state=tk.NORMAL)
    text_area.insert(tk.END, message + "\n")
    text_area.see(tk.END)
    text_area.config(state=tk.DISABLED)

# 客戶端連線處理
def connect_to_server():
    global conn
    HOST = '127.0.0.1'
    PORT = 65432
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((HOST, PORT))
    update_text_area("已連接到伺服器！")
    threading.Thread(target=client_listener, daemon=True).start()

# 監聽伺服器訊息
def client_listener():
    global waiting_for_input, row, col
    conn.settimeout(1.0)
    while True:
        try:
            data = conn.recv(1024).decode('utf-8')
            if data.startswith("BOTHREADY"):
                update_text_area("雙方部署完成！")
                break

        except socket.timeout:
            # 處理超時情況：若超過1秒沒有資料來，則繼續輪詢
            continue
        
    while True:
        try:
            data = conn.recv(1024).decode('utf-8')
            print(data)

            if data.startswith("CLIENT_LOSE"):
                update_text_area("YOU LOSE!")
                break

            if data.startswith("TEST"):
                update_text_area("YOU WIN!")
                break

            elif data.startswith("ATTACK"):
                _, row, col = data.split()
                row, col = int(row), int(col)

                # 移除被攻擊的位置
                if (row, col) in ships_positions:
                    ships_positions.remove((row, col))
                    current_text = buttons[row][col].cget("text")  # 獲取當前按鈕上的文字
                    updated_text = current_text.replace("🚢", "💥")
                    buttons[row][col].config(text=updated_text, bg="red")  # 添加未命中符號
                    update_text_area(f"在 {chr(row + 65)}{col + 1} 的我方戰艦被摧毀！")
                    conn.sendall(b"HIT")
                else:
                    update_text_area(f"對手的導彈落入 {chr(row + 65)}{col + 1}海域，未命中任何我方戰艦")
                    conn.sendall(b"MISS")

            elif data.startswith("CLIENT TURN"):
                update_text_area("填入想要攻擊的位置：")
                input_field.config(state=tk.NORMAL)
                submit_button.config(state=tk.NORMAL)

                # 等待用戶輸入
                waiting_for_input = True
                while waiting_for_input:
                    input_field.update()  # tkinter 主事件處理
                    submit_button.update()
                
                conn.settimeout(1.0)
                while True:
                    try:
                        data = conn.recv(1024).decode('utf-8')

                        if data.startswith("HIT"):
                            update_text_area("🎯導彈已命中！")
                            current_text = buttons[row][col].cget("text")  # 獲取當前按鈕上的文字
                            buttons[row][col].config(text=current_text + "🎯", bg="green")  # 添加命中符號
                            break
                        elif data.startswith("MISS"):
                            update_text_area("🫧導彈未命中！")
                            current_text = buttons[row][col].cget("text")  # 獲取當前按鈕上的文字
                            buttons[row][col].config(text=current_text + "🫧", bg="red")  # 添加未命中符號
                            break

                    except socket.timeout:
                        # 處理超時情況：若超過1秒沒有資料來，則繼續輪詢
                        continue

        except socket.timeout:
            # 處理超時情況：若超過1秒沒有資料來，則繼續輪詢
            continue

# 禁用所有輸入
def disable_all_inputs():
    input_field.config(state=tk.DISABLED)
    submit_button.config(state=tk.DISABLED)
    for row in buttons:
        for btn in row:
            btn.config(state=tk.DISABLED)

# 檢查選擇的格子是否形成直線
def is_valid_ship_placement(cells):
    rows = [cell[0] for cell in cells]
    cols = [cell[1] for cell in cells]

    if len(set(rows)) == 1:
        cols.sort()
        return all(cols[i] == cols[i - 1] + 1 for i in range(1, len(cols)))

    if len(set(cols)) == 1:
        rows.sort()
        return all(rows[i] == rows[i - 1] + 1 for i in range(1, len(rows)))

    return False

# 處理玩家選擇戰艦位置
def select_ship(row, col):
    global current_ship_cells, ships_positions

    if (row, col) in ships_positions:
        update_text_area(f"位置 {chr(row + 65)}{col + 1} 已被選擇！")
        return

    current_ship_cells.append((row, col))
    buttons[row][col].config(text="🚢", bg="lightblue")

    ship_name, ship_size = ship_types[current_ship_index]
    if len(current_ship_cells) > ship_size:
        for r, c in current_ship_cells:
            buttons[r][c].config(text="", bg="SystemButtonFace")
        current_ship_cells = []

# 確認當前船的位置
def confirm_ship():
    global current_ship_index, current_ship_cells, ships_positions

    ship_name, ship_size = ship_types[current_ship_index]
    if len(current_ship_cells) != ship_size:
        update_text_area(f"尚未選滿 {ship_size} 格，請繼續選擇 {ship_name}！")
        return

    if not is_valid_ship_placement(current_ship_cells):
        update_text_area(f"選擇的格子必須是連接的直線（橫向或縱向），請重新選擇！")
        return

    ships_positions.update(current_ship_cells)
    current_ship_cells = []
    current_ship_index += 1

    if current_ship_index >= len(ship_types):
        update_text_area("所有船隻已部署完畢！等待對手完成部署...")
        conn.sendall(b"READY")
        disable_all_inputs()

        # 鎖定棋盤按鈕，防止再點選
        for row_buttons in buttons:
            for btn in row_buttons:
                btn.config(state=tk.DISABLED)

        return

    next_ship_name, next_ship_size = ship_types[current_ship_index]
    update_text_area(f"請選擇 {next_ship_name}（大小：{next_ship_size} 格）的位置！")

# 處理玩家攻擊
def attack():
    global waiting_for_input, row, col

    position = input_field.get().strip().upper()
    if len(position) < 2 or position[0] < 'A' or position[0] > 'G' or not position[1:].isdigit():
        update_text_area("輸入無效！請輸入有效位置，例如 A3 或 B4。")
        return

    row = ord(position[0]) - 65
    col = int(position[1:]) - 1

    if row < 0 or row >= BOARD_ROWS or col < 0 or col >= BOARD_COLS:
        update_text_area("輸入位置超出範圍！")
        return

    input_field.delete(0, tk.END)
    input_field.config(state=tk.DISABLED)
    submit_button.config(state=tk.DISABLED)
    conn.sendall(f"ATTACK {row} {col}".encode('utf-8'))
    update_text_area(f"你攻擊了 {position}")
    waiting_for_input = False

# 初始化界面
root = tk.Tk()
root.title("BattleShip - Player2")

# 滾動文字區域
text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, state=tk.DISABLED, width=50, height=10)
text_area.pack(padx=10, pady=10)

input_frame = tk.Frame(root)
input_frame.pack(pady=5)
input_field = tk.Entry(input_frame, width=30, state=tk.DISABLED)
input_field.grid(row=0, column=0, padx=5)
submit_button = tk.Button(input_frame, text="Attack", command=attack, state=tk.DISABLED)
submit_button.grid(row=0, column=1)

# 確認按鈕
confirm_button = tk.Button(root, text="Confirm", command=confirm_ship)
confirm_button.pack(pady=10)

# 棋盤按鈕
frame = tk.Frame(root)
frame.pack(pady=10)

# 上方座標（1~8）
for c in range(BOARD_COLS):
    tk.Label(frame, text=str(c + 1), width=2, height=2).grid(row=0, column=c + 1, padx=2, pady=2)

# 左側座標（A~G）
for r in range(BOARD_ROWS):
    tk.Label(frame, text=chr(r + 65), width=2, height=2).grid(row=r + 1, column=0, padx=2, pady=2)

# 棋盤按鈕
for r in range(BOARD_ROWS):
    row_buttons = []
    for c in range(BOARD_COLS):
        btn = tk.Button(frame, text="", width=3, height=3, command=lambda r=r, c=c: select_ship(r, c))
        btn.grid(row=r + 1, column=c + 1, padx=2, pady=2)
        row_buttons.append(btn)
    buttons.append(row_buttons)

# 初始化遊戲提示
update_text_area(f"請選擇 {ship_types[current_ship_index][0]}（大小：{ship_types[current_ship_index][1]} 格）的位置！")

threading.Thread(target=connect_to_server, daemon=True).start()

root.mainloop()
