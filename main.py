import os
import random
import base64
from io import BytesIO
from PIL import Image
import tweepy
from gradio_client import Client
import google.generativeai as genai

# ======== 環境変数ロード ========
TWITTER_API_KEY = os.getenv("API_KEY_1")
TWITTER_API_SECRET = os.getenv("API_SECRET_1")
TWITTER_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN_1")
TWITTER_ACCESS_SECRET = os.getenv("ACCESS_SECRET_1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_SPACE_ID = os.getenv("HF_SPACE_ID")  # 例: "robotsan-x-bot-image"

# ======== Twitter 認証 ========
auth = tweepy.OAuth1UserHandler(
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET
)
api_v1 = tweepy.API(auth)

# ======== Gemini 初期化 ========
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-1.5-flash-latest"

# ======== ひらがな3文字生成 ========
def generate_word():
    hira = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    return "".join(random.choice(hira) for _ in range(3))

# ======== 画像生成 ========
def generate_image(word):
    try:
        print("🎨 画像生成中...")
        client = Client(f"https://{HF_SPACE_ID}.hf.space/")
        result = client.predict(
            f"『{word}』という日本語の単語から連想されるバズるイラストまたは写真",
            api_name="/predict"
        )

        # Spaceの出力形式に応じて処理
        if isinstance(result, str) and result.startswith("data:image"):
            image_base64 = result.split(",")[1]
        elif isinstance(result, list) and isinstance(result[0], str):
            image_base64 = result[0].split(",")[1] if result[0].startswith("data:image") else result[0]
        else:
            raise ValueError(f"画像生成APIの応答が不正です: {result}")

        # base64 デコード
        image_data = base64.b64decode(image_base64 + "=" * (-len(image_base64) % 4))
        image_path = "output.png"
        with open(image_path, "wb") as f:
            f.write(image_data)

        print("✅ 画像生成成功")
        return image_path
    except Exception as e:
        print(f"❌ 画像生成エラー: {e}")
        return None

# ======== ハッシュタグ生成 ========
def generate_hashtags(word):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"「{word}」から連想される面白く自然な日本語ハッシュタグを5個、#をつけて改行区切りで出力してください。"
        response = model.generate_content(prompt)
        hashtags = [tag.strip() for tag in response.text.strip().split("\n") if tag.strip()]
        print("✅ ハッシュタグ生成成功")
        return hashtags
    except Exception as e:
        print(f"❌ ハッシュタグ生成エラー: {e}")
        return []

# ======== Twitter 投稿 ========
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

# ======== メイン処理 ========
def main():
    word = generate_word()
    print(f"🎲 生成単語: {word}")
    image_path = generate_image(word)
    post_to_twitter(word, image_path)

if __name__ == "__main__":
    main()
