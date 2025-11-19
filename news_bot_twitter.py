import os
import requests
import feedparser
import google.generativeai as genai
import json
import tweepy  # 👈 追加
from dotenv import load_dotenv
# ================= 設定 =================
load_dotenv()
# X API 認証情報 (Free Tier用)
API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"
HISTORY_FILE = "sent_news.json"
genai.configure(api_key=GEMINI_API_KEY)
# ==========================================
# Xクライアントのセットアップ
# ==========================================
def get_twitter_client():
    """X API v2 Clientを初期化して返す"""
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )
    return client
# ==========================================
# 履歴管理 (変更なし)
# ==========================================
def load_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []
def save_history(url):
    history = load_history()
    history = list(set(history))
    if url not in history: history.append(url)
    history = history[-50:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
# ==========================================
# RSS取得 (変更なし)
# ==========================================
def fetch_latest_news(limit=10):
    try:
        feed = feedparser.parse(RSS_URL)
        return [{"title": e.title, "summary": e.summary, "url": e.link} for e in feed.entries[:limit]]
    except: return []
# ==========================================
# Gemini (文字数調整済み)
# ==========================================
def process_news_with_gemini(news_list):
    news_data = [{"title": n["title"], "url": n["url"]} for n in news_list]
    # X(Twitter)は全角140文字制限があります（URLは23文字換算）。
    # そのため、要約は「100文字以内」くらいに抑える必要があります。
    prompt = f"""
以下の未送信ニュース一覧から重要な 1 件を選び、以下の JSON 形式だけで返してください。
JSONの外に余計な文字は一切書かないこと。
形式:
{{
    "selected_url": "ニュースURL",
    "summary": "ニュース内容と皮肉コメントを混ぜて【200文字以内】でJK口調で要約。Xのトレンドのワードを1~2個盛り込んでください。また文頭は【速報】、【悲報】、【朗報】のいずれかを状況に応じて使ってください。バズりやすい構造（共感 → ツッコミ → 軽いオチ）を意識してください",
    "hashtags": ["#タグ1", "#タグ2","#タグ3"]
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
        print(f"Error: {raw}")
        raise e
# ==========================================
# Xへの投稿処理 (ここがメインの変更点)
# ==========================================
def post_to_twitter(message):
    try:
        client = get_twitter_client()
        response = client.create_tweet(text=message)
        print(f"✅ X投稿成功！ ID: {response.data['id']}")
        return True
    except tweepy.TweepyException as e:
        print(f"❌ X投稿失敗: {e}")
        return False
# ==========================================
# メイン
# ==========================================
if __name__ == "__main__":
    try:
        history = load_history()
        latest_news = fetch_latest_news()
        news_list_unseen = [n for n in latest_news if n["url"] not in history]
        if not news_list_unseen:
            print("新しいニュースなし")
            exit()
        result = process_news_with_gemini(news_list_unseen)
        summary = result.get("summary", "")
        hashtags = " ".join(result.get("hashtags", [])) # Xは改行よりスペース区切りが一般的
        url = result.get("selected_url", "")
        # ツイート本文の組み立て
        # Xの制限: 全角140文字 (URLは短縮され23文字分消費)
        # なので本文＋タグは 117文字以内に収める必要がある
        tweet_text = f"{summary}\n\n{hashtags}\n{url}"
        if post_to_twitter(tweet_text):
            save_history(url)
    except Exception as e:

        print(f"Error: {e}")

