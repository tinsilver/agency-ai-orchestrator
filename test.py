import requests
import json
from requests.auth import HTTPBasicAuth

# Your DataForSEO credentials
USERNAME = "webmaster@cocoarunners.com"
PASSWORD = "4492bd0630b46a35"

url = "https://api.dataforseo.com/v3/dataforseo_labs/google/domain_rank_overview/live"

payload = [
    {
        "target": "enricoviola.com"
    }
]

response = requests.post(
    url,
    auth=HTTPBasicAuth(USERNAME, PASSWORD),
    headers={"Content-Type": "application/json"},
    data=json.dumps(payload)
)

data = response.json()

# Extract monthly traffic estimate
try:
    metrics = data["tasks"][0]["result"][0]["metrics"]["organic"]
    print(f"Estimated monthly traffic: {metrics['etv']}")
    # etv = estimated traffic value / monthly visits estimate
except (KeyError, IndexError, TypeError) as e:
    print("Could not extract traffic data:", e)
    print(json.dumps(data, indent=2))