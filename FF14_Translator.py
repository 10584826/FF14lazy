import os
import sys
import time
import re
import requests
import uuid
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageGrab
import pyperclip
import google.generativeai as genai

# ==================== 設定載入 (config.txt / 環境變數) ====================
AZURE_KEY = None
AZURE_ENDPOINT = None
AZURE_TRANSLATOR_KEY = None
AZURE_TRANSLATOR_REGION = None
GEMINI_API_KEY = None

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
                elif line.startswith("AZURE_TRANSLATOR_KEY="):
                    AZURE_TRANSLATOR_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("AZURE_TRANSLATOR_REGION="):
                    AZURE_TRANSLATOR_REGION = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"讀取 config.txt 失敗: {e}")

# 備用設定補齊
AZURE_KEY = AZURE_KEY or os.getenv("AZURE_KEY")
AZURE_ENDPOINT = AZURE_ENDPOINT or os.getenv("AZURE_ENDPOINT")
AZURE_TRANSLATOR_KEY = AZURE_TRANSLATOR_KEY or os.getenv("AZURE_TRANSLATOR_KEY", AZURE_KEY)
AZURE_TRANSLATOR_REGION = AZURE_TRANSLATOR_REGION or os.getenv("AZURE_TRANSLATOR_REGION", "global")
GEMINI_API_KEY = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")

# 初始化 Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ==================== Gemini 動態生成日文回覆 ====================
def generate_gemini_replies(chat_text):
    """利用 Gemini API 根據當前對話生成 3 個適當的日文簡短回覆"""
    if not GEMINI_API_KEY:
        return [("請在 config.txt 設定 GEMINI_API_KEY", "")]
    
    if not chat_text or not chat_text.strip():
        return [("無日文對話內容", "")]

    prompt = f"""
    你是一個 Final Fantasy XIV (FF14) 日本伺服器的遊戲助手。
    請根據以下隊友/玩家發送的對話內容，生成 3 個適合玩家發送的【簡短、自然且常用】的日文回覆。

    玩家對話內容：
    {chat_text}

    請**嚴格按照**以下格式輸出 3 行，不要添加任何其他說明文字、標號或引號：
    日文回覆1|中文翻譯1
    日文回覆2|中文翻譯2
    日文回覆3|中文翻譯3

    例如：
    大丈夫ですよ！|沒事的！
    どんまいです！|Don't mind / 沒關係！
    気にしないでください！|請別放在心上！
    """

    try:
        model = genai.GenerativeModel('gemini-3.5-flash-lite')
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        replies = []
        for line in raw_text.split("\n"):
            line = line.strip()
            if "|" in line:
                parts = line.split("|", 1)
                ja = parts[0].strip()
                zh = parts[1].strip()
                display = f"{ja} ({zh})"
                replies.append((display, ja))
        
        # 確保回覆數量符合介面要求
        while len(replies) < 3:
            replies.append(("よろしくお願いします！ (請多指教！)", "よろしくお願いします！"))
            
        return replies[:3]

    except Exception as e:
        return [
            (f"Gemini 生成失敗: {str(e)}", ""),
            ("よろしくお願いします！ (請多指教！)", "よろしくお願いします！"),
            ("お疲れ様でした！ (辛苦了！)", "お疲れ様でした！")
        ]


# ==================== Azure Translator 功能 ====================
def translate_ja_to_zh_azure(text):
    if not text or not text.strip():
        return ""
    
    if not AZURE_TRANSLATOR_KEY:
        return "（錯誤：未設定 AZURE_TRANSLATOR_KEY）"

    endpoint = "https://api.cognitive.microsofttranslator.com"
    constructed_url = endpoint + '/translate'

    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_TRANSLATOR_KEY.strip(),
        'Ocp-Apim-Subscription-Region': AZURE_TRANSLATOR_REGION.strip(),
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]

    try:
        response = requests.post(constructed_url, params=params, headers=headers, json=body, timeout=5)
        if response.status_code == 200:
            result = response.json()
            return "\n".join([t['text'] for t in result[0]['translations']])
        else:
            return f"（Azure 翻譯失敗 Status: {response.status_code}）"
    except Exception as e:
        return f"（Azure 翻譯異常: {str(e)}）"


# ==================== Azure OCR 辨識功能 ====================
def ocr_japanese_image(image_path):
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
            response = requests.post(ocr_url, headers=headers, data=image_file.read())
            
        if response.status_code != 200:
            return f"OCR 請求失敗 (Status: {response.status_code})"

        result = response.json()
        extracted_lines = []
        for region in result.get("regions", []):
            for line in region.get("lines", []):
                extracted_lines.append("".join([w.get("text", "") for w in line.get("words", [])]))
                    
        return "\n".join(extracted_lines) if extracted_lines else "未辨識到日文文字。"
    except Exception as e:
        return f"發生錯誤: {str(e)}"


# ==================== GUI 截圖區域選擇 ====================
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
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        self.sniper_win.destroy()
        
        x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
        y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)

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
        self.root.geometry("460x640")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2d2d2d")

        # 標題
        title_label = tk.Label(root, text="⚔️ FF14 日文對話翻譯助手", font=("Microsoft JhengHei", 14, "bold"), fg="#ffffff", bg="#2d2d2d")
        title_label.pack(pady=8)

        # 狀態標示
        ocr_ok = bool(AZURE_KEY and AZURE_ENDPOINT)
        trans_ok = bool(AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION)
        gemini_ok = bool(GEMINI_API_KEY)
        
        status_text = f"OCR: {'✅' if ocr_ok else '❌'} | 翻譯: {'✅' if trans_ok else '❌'} | Gemini AI: {'✅' if gemini_ok else '❌'}"
        status_color = "#55ff55" if (ocr_ok and trans_ok and gemini_ok) else "#ffaa55"
        self.status_label = tk.Label(root, text=status_text, font=("Microsoft JhengHei", 9), fg=status_color, bg="#2d2d2d")
        self.status_label.pack(pady=2)

        # 截圖按鈕
        self.btn_snip = tk.Button(root, text="📷 選擇區域並翻譯", font=("Microsoft JhengHei", 11, "bold"), bg="#3a7bd5", fg="white", activebackground="#2a5ea5", command=self.start_snipping)
        self.btn_snip.pack(pady=10, ipadx=10, ipady=3)

        # 日文文字框
        lbl_ja = tk.Label(root, text="【辨識到的日文】", font=("Microsoft JhengHei", 9, "bold"), fg="#aaa", bg="#2d2d2d")
        lbl_ja.pack(anchor="w", padx=15)
        self.txt_ja = tk.Text(root, height=3, font=("Microsoft JhengHei", 9), bg="#1e1e1e", fg="#55ff55", insertbackground="white")
        self.txt_ja.pack(fill="x", padx=15, pady=2)

        # 中文文字框
        lbl_zh = tk.Label(root, text="【Azure 中文翻譯】", font=("Microsoft JhengHei", 9, "bold"), fg="#aaa", bg="#2d2d2d")
        lbl_zh.pack(anchor="w", padx=15, pady=(5, 0))
        self.txt_zh = tk.Text(root, height=3, font=("Microsoft JhengHei", 10), bg="#1e1e1e", fg="#ffff55", insertbackground="white")
        self.txt_zh.pack(fill="x", padx=15, pady=2)

        # 🤖 AI 動態建議回覆區
        lbl_reply = tk.Label(root, text="【🤖 Gemini AI 推薦日文回覆 (點擊複製)】", font=("Microsoft JhengHei", 9, "bold"), fg="#88d8ff", bg="#2d2d2d")
        lbl_reply.pack(anchor="w", padx=15, pady=(10, 0))

        self.reply_buttons = []
        default_replies = [
            ("よろしくお願いします！ (請多指教！)", "よろしくお願いします！"),
            ("初見です、よろしくお願いします！ (初見，請多指教！)", "初見です、よろしくお願いします！"),
            ("お疲れ様でした！ (辛苦了！)", "お疲れ様でした！")
        ]

        for label_text, copy_text in default_replies:
            btn = tk.Button(root, text=label_text, font=("Microsoft JhengHei", 9), bg="#383838", fg="#e0e0e0", anchor="w")
            btn.config(command=lambda t=copy_text: self.copy_to_clipboard(t))
            btn.pack(fill="x", padx=15, pady=2)
            self.reply_buttons.append(btn)

        # 底部狀態列
        self.lbl_status = tk.Label(root, text="準備就緒，點擊上方按鈕開始截圖", font=("Microsoft JhengHei", 9), fg="#888", bg="#2d2d2d")
        self.lbl_status.pack(side="bottom", pady=8)

    def start_snipping(self):
        self.root.iconify()
        time.sleep(0.2)
        ScreenSnipper(self.process_image)

    def process_image(self, img_path):
        self.root.deiconify()
        self.lbl_status.config(text="正在進行 OCR 辨識、翻譯與 Gemini AI 回覆生成...")
        self.root.update()

        # 1. OCR 辨識
        raw_ja = ocr_japanese_image(img_path)
        self.txt_ja.delete("1.0", tk.END)
        self.txt_ja.insert(tk.END, raw_ja)

        # 2. 過濾玩家 ID 與頻道標記
        cleaned_lines = []
        for line in raw_ja.split("\n"):
            clean_line = re.sub(r'^[0-9A-Za-z\s%&\(\)\*≪≫<>]+\)\s*', '', line)
            if clean_line.strip():
                cleaned_lines.append(clean_line)

        text_for_trans = "\n".join(cleaned_lines) if cleaned_lines else raw_ja

        # 3. Azure 中文翻譯
        if "錯誤" not in raw_ja and "失敗" not in raw_ja and raw_ja != "未辨識到日文文字。":
            zh_text = translate_ja_to_zh_azure(text_for_trans)
        else:
            zh_text = ""

        self.txt_zh.delete("1.0", tk.END)
        self.txt_zh.insert(tk.END, zh_text)

        # 4. 🤖 呼叫 Gemini 生成建議回覆並動態更新按鈕
        if zh_text and GEMINI_API_KEY:
            ai_replies = generate_gemini_replies(text_for_trans)
            for i, (display_text, copy_text) in enumerate(ai_replies):
                if i < len(self.reply_buttons):
                    self.reply_buttons[i].config(
                        text=display_text,
                        command=lambda t=copy_text: self.copy_to_clipboard(t)
                    )

        self.lbl_status.config(text="分析完成！已載入 Gemini AI 最佳回覆選項。")

    def copy_to_clipboard(self, text):
        if text:
            pyperclip.copy(text)
            self.lbl_status.config(text=f"已複製日文: '{text}' 到剪貼簿！")


# ==================== 主程式進入點 ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()