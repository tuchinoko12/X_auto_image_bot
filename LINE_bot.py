import os
import requests
import feedparser
import google.generativeai as genai
import json
from dotenv import load_dotenv

# ================= 設定 =================
load_dotenv()

LINE_TOKEN = os.getenv("LINE_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"
HISTORY_FILE = "sent_news.json" # 送信済みニュースのURLを保存するファイル

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 過去に送ったニュース履歴管理
# ==========================================
def load_history():
    """履歴ファイルをロードし、過去に送信したURLのリストを返す"""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # ファイル内容が壊れている場合は空リストを返す
        print(f"⚠️ 履歴ファイル ({HISTORY_FILE}) のJSON形式が不正です。新しく作成します。")
        return []

def save_history(url):
    """送信に成功したニュースのURLを履歴に追加し、ファイルを保存する"""
    history = load_history()
    
    # 重複を削除し、最新のURLを追加
    history = list(set(history))
    if url not in history:
        history.append(url)
    
    # ファイルが肥大化しないよう、最新の50件のみを保持
    history = history[-50:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ==========================================
# RSSニュース取得
# ==========================================
def fetch_latest_news(limit=10):
    """RSSフィードから最新のニュースを取得する"""
    try:
        feed = feedparser.parse(RSS_URL)
        return [{
            "title": entry.title,
            "summary": entry.summary,
            "url": entry.link
        } for entry in feed.entries[:limit]]
    except Exception as e:
        print(f"❌ RSSフィードの取得またはパースに失敗しました: {e}")
        return []


# ==========================================
# Gemini に JSON だけ返させる（安全版）
# ==========================================
def process_news_with_gemini(news_list):
    """ニュースリストから一つを選択し、要約とハッシュタグをJSON形式で生成させる"""
    
    # ニュースのタイトルとURLのみをプロンプトに含める（トークン節約のため）
    news_data_for_prompt = [{
        "title": n["title"],
        "url": n["url"]
    } for n in news_list]

    prompt = f"""
以下の未送信ニュース一覧から重要な 1 件を選び、以下の JSON 形式だけで返してください。
絶対に JSON の外に文章や説明を書かないこと。改行・補足禁止。
hashtagsは女子高生（JK）ぽい、少し皮肉の効いた言い回しでお願いします。

形式:
{{
    "selected_url": "選んだニュースのURL",
    "summary": "
    ・250文字以内のアイちゃん要約
    ・ニュース内容＋皮肉コメント
    ・SNS上の多数派の反応（平均的な意見）を元にコメントする
    ・文末は女子高生口語（〜だよね、〜じゃん、〜なの等）
    ・良い点と悪い点どちらも言及
    ",
    "hashtags": ["#タグ1", "#タグ2", "#タグ3"]
}}

ニュース一覧:
{json.dumps(news_data_for_prompt, ensure_ascii=False)}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    # APIコール
    response = model.generate_content(prompt)

    raw = response.text.strip()
    print("\n===== Gemini Raw Response =====")
    print(raw)
    print("===== END =====\n")

    # JSONだけ抽出（AIが文章混ぜても復旧できるパースロジック）
    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        json_str = raw[json_start:json_end]

        return json.loads(json_str)

    except Exception as e:
        print("❌ JSONパース失敗。Geminiの応答が不正な可能性があります:", e)
        print("Geminiの返答:", raw)
        raise e


# ==========================================
# LINE送信
# ==========================================
def send_line_message(message):
    """LINE Messaging APIを通じてメッセージを送信する"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        # LINE_USER_IDは環境変数から取得されます
        "to": LINE_USER_ID, 
        "messages": [{"type": "text", "text": message}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status() # HTTPエラーをチェック
        print(f"✅ LINE送信成功: {res.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ LINE送信失敗: {e}")
        print(f"レスポンス: {res.text if 'res' in locals() else 'N/A'}")


# ==========================================
# メイン
# ==========================================
if __name__ == "__main__":
    try:
        # 1. 履歴のロード
        history = load_history()
        
        # 2. 最新ニュースの取得とフィルタリング
        latest_news = fetch_latest_news(limit=10)
        # 既に送信済みのURLを除外して、未送信ニュースのリストを作成
        news_list_unseen = [n for n in latest_news if n["url"] not in history]
        
        if not news_list_unseen:
            print("📢 現在、新しい未送信のニュースはありませんでした。処理を終了します。")
            exit()

        # 3. Geminiで最も重要なニュースを選択し、要約とタグを生成
        # 未送信ニュースリストのみを渡す
        result = process_news_with_gemini(news_list_unseen)

        # 結果を取り出し
        summary = result.get("summary", "要約なし")
        raw_hashtags = result.get("hashtags", [])
        url = result.get("selected_url", "")
        
        if not url:
            raise ValueError("Geminiの応答に 'selected_url' が含まれていません。")

        # 4. 送信メッセージの整形
        hashtags = "\n".join(raw_hashtags)
        message = f"{summary}\n\n{hashtags}\n\n{url}"

        # 5. LINE送信
        send_line_message(message)
        
        # 6. 履歴の保存 (送信成功後)
        save_history(url)

        print(f"✅ 完了：LINEにニュースを送信し、URL ({url}) を履歴に保存しました！")

    except Exception as e:
        print(f"❌ 重大なエラーが発生しました。処理を中断します: {e}")
        # 例外が発生した場合、履歴は保存されないため、二重送信は防げる
