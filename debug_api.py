import requests
import json

url = "https://camping.bcparks.ca/api/resourcelocation/resources?resourceLocationId=-2147483645"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print(f"Fetching {url}")
try:
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Type: {type(data)}")
    if isinstance(data, list):
        print(f"First item keys: {data[0].keys() if data else 'Empty List'}")
        if data:
            print(f"First item: {data[0]}")
    elif isinstance(data, dict):
        print(f"Keys: {list(data.keys())[:5]}")
except Exception as e:
    print(f"Error: {e}")
