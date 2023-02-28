# OpenAI账号免费额度剩余查询
import requests


def fetch_credit_data(api_key: str) -> dict:
    """OpenAI账号免费额度剩余查询"""
    resp = requests.get(
        url="https://api.openai.com/dashboard/billing/credit_grants",
        headers={
            "Authorization": "Bearer {}".format(api_key),
        }
    )
    return resp.json()