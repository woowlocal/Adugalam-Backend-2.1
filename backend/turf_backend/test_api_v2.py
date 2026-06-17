import urllib.request
import json

url = "http://127.0.0.1:8000/api/recent-otps/?email=charles9025032966@gmail.com"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
