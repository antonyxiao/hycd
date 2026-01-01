import json

try:
    with open('hint_cache.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        for k, v in data.items():
            if not isinstance(v, str):
                print(f"Key: {k}, Type: {type(v)}, Value: {v}")
except Exception as e:
    print(e)
