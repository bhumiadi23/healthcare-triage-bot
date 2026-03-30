import requests

lat, lng = 20.2961, 85.8245

params = {
    "q": "hospital",
    "format": "json",
    "addressdetails": 1,
    "limit": 5,
    "viewbox": f"{lng-0.1},{lat+0.1},{lng+0.1},{lat-0.1}",
    "bounded": 1,
}
headers = {"User-Agent": "healthcare-triage-bot/1.0"}
resp = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=15)
print("HTTP:", resp.status_code)
data = resp.json()
print("Results:", len(data))
for p in data:
    print(" -", p.get("display_name", "")[:80])
