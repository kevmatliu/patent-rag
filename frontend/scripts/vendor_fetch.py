import urllib.request
import os

url = "https://esm.sh/*ketcher-react@3.5.0,*ketcher-standalone@3.5.0?deps=react@18.3.1,react-dom@18.3.1&bundle-deps&target=es2022"
print("Fetching from esm.sh...", url)

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    content = response.read().decode('utf-8')

os.makedirs("/Users/kevinliu/Desktop/patent-rag-chem/v2/frontend/public/ketcher/vendor/combined", exist_ok=True)
with open("/Users/kevinliu/Desktop/patent-rag-chem/v2/frontend/public/ketcher/vendor/combined/ketcher.bundle.mjs", "w") as f:
    f.write(content)

print("Downloaded combined bundle successfully!")
