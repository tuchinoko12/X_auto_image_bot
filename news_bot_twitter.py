import os
import requests
import feedparser
import google.generativeai as genai
import json
import tweepy
from dotenv import load_dotenv

# ================= 設定 =================
load_dotenv()

API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"
HISTORY_FILE = "sent_news.json"

genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 履歴管理
# ==========================================
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_history(url):
    history = load_history()
    if url not in history:
        history.append(url)
    history = history[-50:]  # 過去50件だけ保持
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ==========================================
# NHK RSSニュース取得
# ==========================================
def fetch_latest_news(limit=10):
    try:
        feed = feedparser.parse(RSS_URL)
        return [{"title": e.title, "summary": e.summary, "url": e.link} for e in feed.entries[:limit]]
    except:
        return []

# ==========================================
# X（Twitter）トレンド取得
# ==========================================
def get_trend_words(limit=5):
    """日本と世界のトレンドから上位ワードを数件取得"""
    try:
        auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        api = tweepy.API(auth)

        jp = api.get_place_trends(23424856)[0]["trends"]   # 日本
        world = api.get_place_trends(1)[0]["trends"]       # 世界

        words = [t["name"] for t in (jp + world)[:limit]]
        return words

    except Exception as e:
        print("トレンド取得失敗:", e)
        return []

# ==========================================
# Gemini による要約生成（150〜200文字）
# ==========================================
def process_news_with_gemini(news_list, trend_words):
    news_data = [{"title": n["title"], "url": n["url"]} for n in news_list]

    prompt = f"""
以下のニュース一覧から重要な1件を選び、以下のJSON形式だけで返してください。

・ハッシュタグ禁止
・150〜200文字
・皮肉＋JK口調
・文頭は【速報】【朗報】【悲報】のいずれか
・絵文字を適度に使う
・トレンドワードを自然に混ぜる（無理やりはNG）
・「共感 → ツッコミ → 軽いオチ」の構成でバズりを意識

トレンドワード: {trend_words}

形式:
{{
  "selected_url": "ニュースURL",
  "text": "Xに投稿する本文（150〜200文字）"
}}

ニュース一覧:
{json.dumps(news_data, ensure_ascii=False)}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw = response.text.strip()

    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        return json.loads(raw[json_start:json_end])
    except Exception as e:
        print("Gemini出力読み取り失敗:", raw)
        raise e

# ==========================================
# Xへ投稿（v1.1 API → Freeプランでも確実）
# ==========================================
def post_to_twitter(message):
    try:
        auth = tweepy.OAuth1UserHandler(
            API_KEY,
            API_SECRET,
            ACCESS_TOKEN,
            ACCESS_TOKEN_SECRET
        )
        api = tweepy.API(auth)

        api.update_status(status=message)
        print("✅ X投稿成功！")
        return True

    except Exception as e:
        print(f"❌ X投稿失敗: {e}")
        return False

# ==========================================
# メイン処理
# ==========================================
if __name__ == "__main__":
    try:
        history = load_history()
        latest_news = fetch_latest_news()
        trend_words = get_trend_words(limit=5)

        # 新しいニュースだけ対象
        news_list_unseen = [n for n in latest_news if n["url"] not in history]

        if not news_list_unseen:
            print("新しいニュースなし")
            exit()

        # Gemini で投稿文生成
        result = process_news_with_gemini(news_list_unseen, trend_words)

        text = result.get("text", "")
        url = result.get("selected_url", "")

        tweet_text = f"{text}\n{url}"

        if post_to_twitter(tweet_text):
            save_history(url)

    except Exception as e:
        print(f"Error: {e}")
