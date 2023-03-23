# OpenAI账号免费额度剩余查询
import requests

def fetch_credit_data(api_key: str, http_proxy: str) -> dict:
    """OpenAI账号免费额度剩余查询"""
    proxies = {
        "http":http_proxy,
        "https":http_proxy
    } if http_proxy is not None else None

    resp = requests.get(
        url="https://api.openai.com/dashboard/billing/credit_grants",
        headers={
            "Authorization": "Bearer {}".format(api_key),
        },
        proxies=proxies
    )

    return resp.json()