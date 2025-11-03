import os
import random
from gradio_client import Client
import tweepy
import google.generativeai as genai

# ===== 設定 =====
POST_INTERVAL_HOURS = 8  # もしループで自動投稿する場合
HF_SPACE_ID = os.getenv("HF_SPACE_ID")  # GitHub Secrets
MODEL_INPUT_KEY = "prompt"

# ===== Gemini text_model 初期化 =====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
text_model = "gemini-2.0-flash"

# ===== Twitter 認証 =====
TWITTER_API_KEY = os.getenv("API_KEY_1")
TWITTER_API_SECRET = os.getenv("API_SECRET_1")
TWITTER_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN_1")
TWITTER_ACCESS_SECRET = os.getenv("ACCESS_SECRET_1")

auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
api_v1 = tweepy.API(auth)

# ===== ひらがな3文字生成 =====
def generate_word():
    hira = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    return "".join(random.choice(hira) for _ in range(3))

# ===== 画像生成 (gradio_client 経由) =====
def generate_image(word):
    prompt = f"『{word}』という日本語の単語から連想されるバズるイラストまたは写真"
    try:
        client = Client(HF_SPACE_ID)
        result = client.predict(prompt, api_name="/predict")  # Space によって api_name が異なる場合あり
        # result は dict か list 形式 depending on Space
        if isinstance(result, dict) and "data" in result:
            image_data = result["data"][0]
        else:
            image_data = result[0]  # 適宜調整
        return image_data  # URL か base64 など Space による
    except Exception as e:
        print(f"❌ 画像生成エラー: {e}")
        return None

# ===== ハッシュタグ生成 =====
def generate_hashtags(word):
    prompt = f"「{word}」に関連するユーモラスで自然な日本語ハッシュタグを10個生成してください。#をつけて改行で区切ってください。"
    try:
        response = genai.chat(
            model=text_model,
            messages=[{"role": "user", "content": prompt}],
        )
        hashtags_text = response.last.message["content"]
        hashtags = [tag.strip() for tag in hashtags_text.split("\n") if tag.strip()]
        return hashtags[:10]
    except Exception as e:
        print(f"❌ ハッシュタグ生成エラー: {e}")
        return []

# ===== Twitter 投稿 =====
def post_to_twitter(word, image_data):
    hashtags = generate_hashtags(word)
    try:
        media_ids = None
        if image_data:
            # 画像がURLの場合は requests で取得して一時保存
            import requests
            from PIL import Image
            from io import BytesIO

            if image_data.startswith("http"):
                resp = requests.get(image_data)
                image = Image.open(BytesIO(resp.content))
            else:
                # base64 の場合
                import base64
                image = Image.open(BytesIO(base64.b64decode(image_data)))

            file_name = f"{word}.png"
            image.save(file_name)
            media = api_v1.media_upload(filename=file_name)
            media_ids = [media.media_id]

        text = f"生成単語: {word}\n" + " ".join(hashtags)
        api_v1.update_status(status=text, media_ids=media_ids)
        print(f"✅ 投稿成功: {text}")
    except Exception as e:
        print(f"❌ 投稿エラー: {e}")

# ===== メイン =====
def main():
    word = generate_word()
    print(f"🎲 生成単語: {word}")
    image_data = generate_image(word)
    post_to_twitter(word, image_data)

if __name__ == "__main__":
    main()



