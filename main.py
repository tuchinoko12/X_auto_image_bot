import os
import random
import tweepy
from gradio_client import Client
from google import genai
import requests

# ==== API Keys ====
API_KEY = os.getenv("API_KEY_1")
API_SECRET = os.getenv("API_SECRET_1")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN_1")
ACCESS_SECRET = os.getenv("ACCESS_SECRET_1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_SPACE_ID = os.getenv("HF_SPACE_ID")

# ==== Twitter認証 ====
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# ==== 単語リスト ====
WORDS = ["けえす", "しんえん", "にゃるらと", "とけいだい", "ゆめのあと", "あめあがり", "しずく", "てんま", "ほしのゆめ"]

# ==== ランダム単語生成 ====
word = random.choice(WORDS)
print(f"🎲 生成単語: {word}")

# ==== 画像生成 ====
try:
    print("🎨 画像生成中...")
    client = Client(HF_SPACE_ID)
    result = client.predict(word)

    # 出力結果の形式を確認
    if isinstance(result, list):
        image_path = result[0]
    else:
        image_path = result

    # ローカルパス or URL 判定
    if os.path.exists(image_path):
        media = api.media_upload(filename=image_path)
    else:
        img_data = requests.get(image_path).content
        with open("temp.jpg", "wb") as f:
            f.write(img_data)
        media = api.media_upload(filename="temp.jpg")

except Exception as e:
    print(f"❌ 画像生成エラー: {e}")
    media = None

# ==== Geminiでハッシュタグ生成 ====
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"単語『{word}』を含む創作的な日本語ツイート文とハッシュタグ3つを生成してください。"
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[prompt]
    )
    tweet_text = response.text.strip()
except Exception as e:
    print(f"❌ ハッシュタグ生成エラー: {e}")
    tweet_text = f"{word} #AI生成 #自動投稿"

# ==== Xに投稿 ====
try:
    if media:
        api.update_status(status=tweet_text, media_ids=[media.media_id])
    else:
        api.update_status(status=tweet_text)
    print("✅ 投稿完了！")
except Exception as e:
    print(f"❌ 投稿エラー: {e}")
