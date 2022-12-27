pricing = {
    "base": {  # 文字模型单位是1000字符
        "text-davinci-003": 0.02,
    },
    "image": {
        "256x256": 0.016,
        "512x512": 0.018,
        "1024x1024": 0.02,
    }
}


def language_base_price(model, text):
    salt_rate = 0.93
    length = ((len(text.encode('utf-8')) - len(text)) / 2 + len(text)) * salt_rate

    return pricing["base"][model] * length / 1000


def image_price(size):
    return pricing["image"][size]
