import requests
import json

# Use user provided params
url = "https://camping.bcparks.ca/api/availability/map?mapId=-2147483448&startDate=2026-01-09&endDate=2026-01-12&getDailyAvailability=true"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

resp = requests.get(url, headers=headers)
data = resp.json()
res_avails = data.get('resourceAvailabilities', {})
print(f"Count: {len(res_avails)}")
if len(res_avails) > 0:
    first_key = list(res_avails.keys())[0]
    print(f"First Key: {first_key}")
    print(f"Value Structure: {res_avails[first_key]}")
