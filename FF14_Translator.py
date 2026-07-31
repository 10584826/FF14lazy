import os
import sys
import time
import re
import requests
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageGrab
import pyperclip

# ==================== Azure 設定 (優先讀取 config.txt，其次讀取環境變數) ====================
AZURE_KEY = None
AZURE_ENDPOINT = None

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

if not AZURE_KEY:
    AZURE_KEY = os.getenv("AZURE_KEY")
if not AZURE_ENDPOINT:
    AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")


# ==================== 翻譯功能 (使用免費 Google Translate API) ====================
def translate_ja_to_zh(text):
    """將日文翻譯成繁體中文"""
    if not text or not text.strip():
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "ja",
            "tl": "zh-TW",
            "dt": "t",
            "q": text
        }
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            result = res.json()
            translated_lines = [item[0] for item in result[0] if item[0]]
            return "".join(translated_lines)
        else:
            return "（翻譯失敗：網路請求錯誤）"
    except Exception as e:
        return f"（翻譯失敗：{str(e)}）"


# ==================== OCR 辨識功能 ====================
def ocr_japanese_image(image_path):
    """呼叫 Azure Computer Vision 標準同步 OCR 進行日文辨識"""
    if not AZURE_KEY or not AZURE_ENDPOINT:
        return "錯誤：未設定 AZURE_KEY 或 AZURE_ENDPOINT。"

    clean_endpoint = AZURE_ENDPOINT.rstrip('/')
    ocr_url = f"{clean_endpoint}/vision/v3.2/ocr?language=ja&detectOrientation=true"
    
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY.strip(),
        'Content-Type': 'application/octet-stream'
    }
    
    try:
        with open(image_path, "rb") as image_file:
            img_bytes = image_file.read()
            response = requests.post(ocr_url, headers=headers, data=img_bytes)
            
        if response.status_code != 200:
            return f"OCR 請求失敗 (Status: {response.status_code})\n回應內容: {response.text}"

        result = response.json()
        extracted_lines = []
        
        for region in result.get("regions", []):
            for line in region.get("lines", []):
                line_text = "".join([word.get("text", "") for word in line.get("words", [])])
                extracted_lines.append(line_text)
                    
        return "\n".join(extracted_lines) if extracted_lines else "未辨識到日文文字。"

    except Exception as e:
        return f"發生錯誤: {str(e)}"


# ==================== GUI 截圖與區域選擇 ====================
class ScreenSnipper:
    def __init__(self, callback):
        self.callback = callback
        self.sniper_win = tk.Toplevel()
        self.sniper_win.attributes("-alpha", 0.3)
        self.sniper_win.attributes("-fullscreen", True)
        self.sniper_win.attributes("-topmost", True)
        self.sniper_win.config(cursor="cross")

        self.canvas = tk.Canvas(self.sniper_win, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.start_x = None
        self.start_y = None
        self.rect = None

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, outline='red', width=2)

    @property
    def x(self): return self.start_x
    @property
    def y(self): return self.start_y

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.sniper_win.destroy()
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 > 10 and y2 - y1 > 10:
            time.sleep(0.2)
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            temp_path = "temp_ocr.png"
            img.save(temp_path)
            self.callback(temp_path)


# ==================== 主介面 App ====================
class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FF14 日文對話翻譯助手")
        self.root.geometry("450x620")
        self.root.attributes("-topmost", True)  # 保持視窗最上層，方便配搭遊戲
        self.root.configure(bg="#2d2d2d")

        # 標題
        title_label = tk.Label(root, text="⚔️ FF14 日文對話翻譯助手", font=("Microsoft JhengHei", 14, "bold"), fg="#ffffff", bg="#2d2d2d")
        title_label.pack(pady=8)

        # 狀態標示
        status_text = "✅ Azure 金鑰狀態：已載入" if (AZURE_KEY and AZURE_ENDPOINT) else "❌ 警告：未找到 Azure 金鑰/Endpoint"
        status_color = "#55ff55" if (AZURE_KEY and AZURE_ENDPOINT) else "#ff5555"
        self.status_label = tk.Label(root, text=status_text, font=("Microsoft JhengHei", 9), fg=status_color, bg="#2d2d2d")
        self.status_label.pack(pady=2)

        # 截圖按鈕
        self.btn_snip = tk.Button(root, text="📷 選擇區域並翻譯", font=("Microsoft JhengHei", 11, "bold"), bg="#3a7bd5", fg="white", activebackground="#2a5ea5", command=self.start_snipping)
        self.btn_snip.pack(pady=10, ipadx=10, ipady=3)

        # 辨識出的日文文字框
        lbl_ja = tk.Label(root, text="【辨識到的日文】", font=("Microsoft JhengHei", 9, "bold"), fg="#aaa", bg="#2d2d2d")
        lbl_ja.pack(anchor="w", padx=15)
        self.txt_ja = tk.Text(root, height=4, font=("Microsoft JhengHei", 9), bg="#1e1e1e", fg="#55ff55", insertbackground="white")
        self.txt_ja.pack(fill="x", padx=15, pady=2)

        # 翻譯後的中文文字框 (新增加！)
        lbl_zh = tk.Label(root, text="【中文翻譯】", font=("Microsoft JhengHei", 9, "bold"), fg="#aaa", bg="#2d2d2d")
        lbl_zh.pack(anchor="w", padx=15, pady=(5, 0))
        self.txt_zh = tk.Text(root, height=4, font=("Microsoft JhengHei", 10), bg="#1e1e1e", fg="#ffff55", insertbackground="white")
        self.txt_zh.pack(fill="x", padx=15, pady=2)

        # 快速回覆按鈕區
        lbl_reply = tk.Label(root, text="【點擊按鈕自動複製日文回覆】", font=("Microsoft JhengHei", 9, "bold"), fg="#aaa", bg="#2d2d2d")
        lbl_reply.pack(anchor="w", padx=15, pady=(10, 0))

        # 定義常用日文範本
        self.quick_replies = [
            ("よろしくお願いします！ (請多指教！)", "よろしくお願いします！"),
            ("初見です、よろしくお願いします！ (初見，請多指教！)", "初見です、よろしくお願いします！"),
            ("お疲れ様でした！ (辛苦了！)", "お疲れ様でした！"),
            ("どんまいです！ (Don't mind / 沒關係！)", "どんまいです！"),
            ("ありがとうございます！ (非常感謝！)", "ありがとうございます！")
        ]

        for label_text, copy_text in self.quick_replies:
            btn = tk.Button(root, text=label_text, font=("Microsoft JhengHei", 9), bg="#383838", fg="#e0e0e0", anchor="w", command=lambda t=copy_text: self.copy_to_clipboard(t))
            btn.pack(fill="x", padx=15, pady=2)

        # 底部狀態列
        self.lbl_status = tk.Label(root, text="準備就緒，點擊上方按鈕開始截圖", font=("Microsoft JhengHei", 9), fg="#888", bg="#2d2d2d")
        self.lbl_status.pack(side="bottom", pady=8)

    def start_snipping(self):
        self.root.iconify()  # 最小化視窗
        time.sleep(0.2)
        ScreenSnipper(self.process_image)

    def process_image(self, img_path):
        self.root.deiconify()  # 恢復視窗
        self.lbl_status.config(text="正在進行日文 OCR 辨識與翻譯...")
        self.root.update()

        # 1. OCR 辨識
        raw_ja = ocr_japanese_image(img_path)
        
        self.txt_ja.delete("1.0", tk.END)
        self.txt_ja.insert(tk.END, raw_ja)

        # 2. 清理 OCR 文字（移除 Channel 標記/玩家 ID，讓翻譯更準確）
        cleaned_lines = []
        for line in raw_ja.split("\n"):
            # 移除常見的 FF14 頻道符號與 ID (例如: 7Aruka Haru % Hades))
            clean_line = re.sub(r'^[0-9A-Za-z\s%&\(\)\*≪≫<>]+\)\s*', '', line)
            cleaned_lines.append(clean_line if clean_line.strip() else line)
        
        text_for_trans = "\n".join(cleaned_lines)

        # 3. 翻譯成中文
        if "錯誤" not in raw_ja and "失敗" not in raw_ja and raw_ja != "未辨識到日文文字。":
            zh_text = translate_ja_to_zh(text_for_trans)
        else:
            zh_text = ""

        self.txt_zh.delete("1.0", tk.END)
        self.txt_zh.insert(tk.END, zh_text)

        self.lbl_status.config(text="分析與翻譯完成！點擊按鈕即可複製回覆。")

    def copy_to_clipboard(self, text):
        pyperclip.copy(text)
        self.lbl_status.config(text=f"已複製: '{text}' 到剪貼簿！")


# ==================== 主程式進入點 ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()