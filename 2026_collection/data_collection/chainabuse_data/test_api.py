import os
import json
import requests

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CHAINABUSE_API_KEY")

if not API_KEY:
    raise ValueError("CHAINABUSE_API_KEY is missing from .env")

URL = "https://api.chainabuse.com/v0/reports"

params = {}

response = requests.get(
    URL,
    params=params,
    auth=(API_KEY, API_KEY),
    timeout=30
)

print("Status Code:", response.status_code)
print("Request URL:", response.url)
print("Response Body:", response.text)

response.raise_for_status()

data = response.json()

print(json.dumps(data, indent=4))
