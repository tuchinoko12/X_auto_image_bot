import os
import random
import requests
from PIL import Image
from io import BytesIO
import base64
import tweepy
from google import genai  # Gemini 用

# ===== 環境変数ロード =====
TWITTER_API_KEY = os.getenv("API_KEY_1")
TWITTER_API_SECRET = os.getenv("API_SECRET_1")
TWITTER_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN_1")
TWITTER_ACCESS_SECRET = os.getenv("ACCESS_SECRET_1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_SPACE_ID = os.getenv("HF_SPACE_ID")  # GitHub Secrets から

HUGGINGFACE_SPACE_URL = f"https://{HF_SPACE_ID}.hf.space/run/predict"
MODEL_INPUT_KEY = "prompt"  # Space によって異なる場合あり

# ===== Gemini text_model 初期化 =====
client_gemini = genai.Client(api_key=GEMINI_API_KEY)
text_model = "gemini-2.0-flash"

# ===== Twitter 認証 =====
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
api_v1 = tweepy.API(auth)

# ===== ひらがな3文字生成 =====
def generate_word():
    hira = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    return "".join(random.choice(hira) for _ in range(3))

# ===== 画像生成 =====
def generate_image(word):
    prompt = f"『{word}』という日本語の単語から連想されるバズるイラストまたは写真"
    payload = {MODEL_INPUT_KEY: prompt}
    try:
        response = requests.post(HUGGINGFACE_SPACE_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        # Space によって返却形式が異なる場合はここを調整
        image_base64 = data["data"][0]  
        image = Image.open(BytesIO(base64.b64decode(image_base64)))
        file_name = f"{word}.png"
        image.save(file_name)
        return file_name
    except Exception as e:
        print(f"❌ 画像生成エラー: {e}")
        return None

# ===== ハッシュタグ生成 =====
def generate_hashtags(word):
    prompt = f"「{word}」に関連するユーモラスで自然な日本語ハッシュタグを10個生成してください。#をつけて改行で区切ってください。"
    try:
        response = client_gemini.models.generate_content(
            model=text_model,
            contents=[prompt],
        )
        hashtags_text = response.candidates[0].content[0].text
        hashtags = [tag.strip() for tag in hashtags_text.split("\n") if tag.strip()]
        return hashtags[:10]
    except Exception as e:
        print(f"❌ ハッシュタグ生成エラー: {e}")
        return []

# ===== Twitter 投稿 =====
def post_to_twitter(word, image_path):
    hashtags = generate_hashtags(word)
    try:
        if image_path:
            media = api_v1.media_upload(filename=image_path)
            media_ids = [media.media_id]
        else:
            media_ids = None

        text = f"生成単語: {word}\n" + " ".join(hashtags)
        api_v1.update_status(status=text, media_ids=media_ids)
        print(f"✅ 投稿成功: {text}")
    except Exception as e:
        print(f"❌ 投稿エラー: {e}")

# ===== メイン =====
def main():
    word = generate_word()
    print(f"🎲 生成単語: {word}")
    image_path = generate_image(word)
    post_to_twitter(word, image_path)

if __name__ == "__main__":
    main()
