import pickle
import sys
from pprint import pprint

try:
    data = pickle.load(open('word_table.pkl', 'rb'))
    print(f"Type: {type(data)}")
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())[:5]}")
        first_key = list(data.keys())[0]
        print(f"Sample entry [{first_key}]:")
        pprint(data[first_key])
    elif isinstance(data, list):
        print(f"Length: {len(data)}")
        print("Sample entry:")
        pprint(data[0])
except Exception as e:
    print(f"Error: {e}")
