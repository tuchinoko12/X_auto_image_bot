import os
import requests
import feedparser
import json
from dotenv import load_dotenv
import google.generativeai as genai

# ================= 設定 =================
load_dotenv()

LINE_TOKEN = os.getenv("LINE_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RSS_URL = "https://www3.nhk.or.jp/rss/news/cat0.xml"
HISTORY_FILE = "sent_news.json"

# Gemini設定
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 過去に送ったニュース履歴管理
# ==========================================
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_history(url):
    history = load_history()
    history.append(url)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ==========================================
# RSSから最新ニュース取得
# ==========================================
def fetch_latest_news(limit=10):
    feed = feedparser.parse(RSS_URL)
    news_list = []
    for entry in feed.entries[:limit]:
        news_list.append({
            "title": entry.title,
            "summary": entry.summary,
            "url": entry.link
        })
    return news_list

# ==========================================
# Geminiで注目ニュースを選ぶ
# ==========================================
def select_trending_news(news_list):
    prompt = "以下のニュースの中で、政治・社会的に最も注目すべきニュースはどれか選び、URLを教えてください。\n\n"
    for i, news in enumerate(news_list):
        prompt += f"{i+1}. {news['title']} - {news['summary']}\nURL: {news['url']}\n\n"
    prompt += "番号ではなく、ニュースのURLだけを返してください。"

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

# ==========================================
# コレイヌ（アイちゃん）風要約
# ==========================================
def generate_koreinu_summary(news):
    prompt = f"""
以下の政治ニュースを「アイちゃん」という皮肉にモノ申す系女子高生風に要約してください。

条件：
・250文字以内
・ニュース要約＋皮肉コメント
・いいところは良い、悪いところは悪いとハッキリ言う
・文末は女子高生口語（〜だよね、〜じゃん、〜かも、〜なの等）
・ツッコミや感想を必ず入れる
・政治・社会ニュース向けで冷静な批評調
・ネットの反応（多数派の意見）をベースにコメントを作る
・最後にURLを添える

ニュース本文：
{news['summary']}
URL: {news['url']}
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

# ==========================================
# JK風ハッシュタグ生成
# ==========================================
def generate_jk_hashtags(news):
    prompt = f"""
以下のニュースに関連して、3つの日本語ハッシュタグを作ってください。

条件：
- 文頭に#をつける
- 短くてわかりやすい
- 政治・社会ニュース向け
- JKっぽいほんの少し遊び心
- 文章ではなく単語・フレーズのみ

ニュース本文：
{news['summary']}
"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    lines = response.text.strip().splitlines()
    hashtags = [line.strip() for line in lines if line.strip().startswith("#")]
    return hashtags[:3]

# ==========================================
# LINEに送信
# ==========================================
def send_line_message(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    res = requests.post(url, headers=headers, json=payload)
    print(f"LINE送信結果: {res.status_code}, {res.text}")

# ==========================================
# メイン実行
# ==========================================
if __name__ == "__main__":
    try:
        history = load_history()
        news_list = fetch_latest_news(limit=10)
        # 送信済みニュースを除外
        news_list = [n for n in news_list if n["url"] not in history]

        if not news_list:
            print("❌ 新しいニュースはありません")
            exit()

        selected_url = select_trending_news(news_list)
        selected_news = next((n for n in news_list if n["url"] == selected_url), None)
        if not selected_news:
            raise ValueError("Geminiが返したURLがRSSに存在しません。")

        summary = generate_koreinu_summary(selected_news)
        hashtags = generate_jk_hashtags(selected_news)
        hashtag_text = "\n".join(hashtags)

        message = summary + "\n\n" + hashtag_text

        send_line_message(message)
        save_history(selected_news["url"])
        print("✅ 完了：LINEにニュース送信しました！")

    except Exception as e:
        print("❌ エラー:", e)
