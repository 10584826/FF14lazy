import os
import sys
import time
import requests
import pyperclip
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageGrab

# ==================== Azure 設定 (優先讀取 config.txt，其次讀取環境變數) ====================
AZURE_KEY = None
AZURE_ENDPOINT = None

# 1. 嘗試從同資料夾下的 config.txt 讀取
config_file = "config.txt"
if os.path.exists(config_file):
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("AZURE_KEY="):
                    AZURE_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("AZURE_ENDPOINT="):
                    AZURE_ENDPOINT = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"讀取 config.txt 失敗: {e}")

# 2. 如果 config.txt 沒拿到，再嘗試從系統環境變數讀取
if not AZURE_KEY:
    AZURE_KEY = os.getenv("AZURE_KEY")
if not AZURE_ENDPOINT:
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")

# ==================== 1. Azure Vision OCR 核心 ====================
def ocr_japanese_image(image_path):
    """呼叫 Azure Computer Vision Read API 進行日文 OCR"""
    if not AZURE_KEY or not AZURE_ENDPOINT:
        return "錯誤：未設定 AZURE_KEY 或 AZURE_ENDPOINT 環境變數。"

    read_url = f"{AZURE_ENDPOINT.rstrip('/')}/vision/v3.2/read/analyze"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Content-Type': 'application/octet-stream'
    }
    
    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(read_url, headers=headers, data=image_file)
            
        if response.status_code != 202:
            return f"OCR 請求失敗 (Status: {response.status_code})，請檢查 Key 或 Endpoint。"

        # Read API 是非同步的，需要輪詢取得結果
        operation_url = response.headers.get("Operation-Location")
        if not operation_url:
            return "無法取得 Operation-Location 標頭。"

        while True:
            result_response = requests.get(operation_url, headers={'Ocp-Apim-Subscription-Key': AZURE_KEY})
            result_json = result_response.json()
            if result_json.get("status") not in ["notStarted", "running"]:
                break
            time.sleep(0.5)

        extracted_lines = []
        if result_json.get("status") == "succeeded":
            read_results = result_json["analyzeResult"]["readResults"]
            for page in read_results:
                for line in page["lines"]:
                    extracted_lines.append(line["text"])
                    
        return "\n".join(extracted_lines) if extracted_lines else "未辨識到日文文字。"

    except Exception as e:
        return f"發生錯誤: {str(e)}"

# ==================== 2. FF14 常用情境與生成回覆引擎 ====================
def generate_ff14_replies(text):
    """根據辨識出的日文，提供中文理解與 3 個常用 FF14 日文回覆"""
    
    # 預設通用回覆
    replies = [
        "よろしくお願いします！ (請多指教！)",
        "お疲れ様でした！ (辛苦了！)",
        "ありがとうございます！ (非常感謝！)"
    ]
    
    # 情境判斷
    if "おつ" in text or "疲" in text or "おつかれ" in text:
        replies = [
            "お疲れ様でした！ありがとうございました！ (辛苦了！非常感謝！)",
            "お疲れ様でした～！またよろしくお願いします！ (辛苦了~ 下次也請多指教！)",
            "おつです！ (辛苦囉！ - 簡短版)"
        ]
    elif "よろしく" in text or "初" in text:
        replies = [
            "よろしくお願いします！ (請多指教！)",
            "初見です、よろしくお願いします！ (第一次打/初見，請多指教！)",
            "不慣れですがよろしくお願いします！ (不太熟練但請多指教！)"
        ]
    elif "行" in text or "どこ" in text or "次" in text:
        replies = [
            "どこでも大丈夫ですよ！ (去哪裡都可以喔！)",
            "ルードレット行きたいです！ (想去隨機副本！)",
            "すみません、今日はこれで落ちます！ (不好意思，我今天先下了！)"
        ]
    elif "どんまい" in text or "donmai" in text or "大丈夫" in text:
        replies = [
            "どんまいです！次行きましょう！ (別介意！繼續下一把吧！)",
            "大丈夫ですよ！気になさらないでください！ (沒關係的！請別介意！)",
            "次頑張りましょう！ (下次加油！)"
        ]

    return replies

# ==================== 3. Tkinter 半透明懸浮 GUI 介面 ====================
class FF14TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FF14 對話助手")
        self.root.geometry("420x460+100+100")
        self.root.attributes("-topmost", True)  # 保持在最上層
        self.root.attributes("-alpha", 0.92)    # 微透明
        self.root.configure(bg="#1e1e2e")

        # 標題欄
        lbl_title = tk.Label(root, text="⚔️ FF14 日文對話翻譯助手", font=("Microsoft JhengHei", 12, "bold"), fg="#cdd6f4", bg="#1e1e2e")
        lbl_title.pack(pady=8)

        # 環境變數狀態提示
        env_status_text = "✅ Azure 金鑰狀態：已載入" if (AZURE_KEY and AZURE_ENDPOINT) else "❌ Azure 金鑰狀態：未設定"
        env_status_color = "#a6e3a1" if (AZURE_KEY and AZURE_ENDPOINT) else "#f38ba8"
        lbl_env = tk.Label(root, text=env_status_text, font=("Microsoft JhengHei", 8), fg=env_status_color, bg="#1e1e2e")
        lbl_env.pack(pady=(0, 5))

        # 按鈕區
        btn_frame = tk.Frame(root, bg="#1e1e2e")
        btn_frame.pack(pady=5)

        self.btn_capture = tk.Button(btn_frame, text="📸 選擇區域並翻譯", font=("Microsoft JhengHei", 10, "bold"), 
                                     bg="#89b4fa", fg="#11111b", command=self.start_crop)
        self.btn_capture.pack(side=tk.LEFT, padx=5)

        # 顯示 OCR 擷取到的日文
        tk.Label(root, text="【辨識到的日文】", font=("Microsoft JhengHei", 9, "bold"), fg="#a6adc8", bg="#1e1e2e").pack(anchor="w", padx=15)
        self.txt_jp = tk.Text(root, height=3, width=48, font=("Yu Gothic", 9), bg="#313244", fg="#a6e3a1", wrap=tk.WORD)
        self.txt_jp.pack(padx=15, pady=2)

        # 顯示建議回覆區
        tk.Label(root, text="【點擊按鈕自動複製日文回覆】", font=("Microsoft JhengHei", 9, "bold"), fg="#a6adc8", bg="#1e1e2e").pack(anchor="w", padx=15, pady=(8, 0))
        
        self.reply_buttons = []
        for i in range(3):
            btn = tk.Button(root, text=f"回覆 {i+1}", font=("Microsoft JhengHei", 9), bg="#45475a", fg="#cdd6f4", 
                            anchor="w", justify=tk.LEFT, command=lambda idx=i: self.copy_reply(idx))
            btn.pack(fill=tk.X, padx=15, pady=3)
            self.reply_buttons.append(btn)

        # 狀態欄
        self.lbl_status = tk.Label(root, text="準備就緒，點擊上方按鈕開始", font=("Microsoft JhengHei", 8), fg="#9399b2", bg="#1e1e2e")
        self.lbl_status.pack(side=tk.BOTTOM, pady=5)

        self.current_replies = []

    def start_crop(self):
        if not AZURE_KEY or not AZURE_ENDPOINT:
            messagebox.showerror("錯誤", "找不到 Azure 環境變數！請設定 AZURE_KEY 與 AZURE_ENDPOINT 後再執行。")
            return

        self.root.iconify()
        time.sleep(0.2)
        
        self.crop_win = tk.Toplevel()
        self.crop_win.attributes("-fullscreen", True)
        self.crop_win.attributes("-alpha", 0.3)
        self.crop_win.configure(cursor="cross")

        self.canvas = tk.Canvas(self.crop_win, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2)

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.crop_win.destroy()
        self.root.deiconify()

        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 < 10 or y2 - y1 < 10:
            self.lbl_status.config(text="選取區域過小，已取消。")
            return

        self.lbl_status.config(text="正在分析日文文字...")
        self.root.update()

        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        temp_path = "ff14_chat_temp.png"
        img.save(temp_path)

        jp_text = ocr_japanese_image(temp_path)
        self.txt_jp.delete("1.0", tk.END)
        self.txt_jp.insert(tk.END, jp_text)

        self.current_replies = generate_ff14_replies(jp_text)
        for i, reply in enumerate(self.current_replies):
            self.reply_buttons[i].config(text=reply, bg="#313244", fg="#f5e0dc")

        self.lbl_status.config(text="分析完成！點擊按鈕即可複製回覆。")

    def copy_reply(self, idx):
        if idx < len(self.current_replies):
            full_text = self.current_replies[idx]
            jp_only = full_text.split(" (")[0]
            pyperclip.copy(jp_only)
            self.lbl_status.config(text=f"已複製: {jp_only} （可在 FF14 貼上）")

# ==================== 主程式啟動 ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = FF14TranslatorApp(root)
    root.mainloop()