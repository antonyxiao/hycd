import pickle
import sys
from pprint import pprint

try:
    data = pickle.load(open('wiki.pkl', 'rb'))
    print(f"Total entries: {len(data)}")
    # Find a non-empty entry to inspect
    for i in range(min(100, len(data))):
        if 'sounds' in data[i] and data[i]['sounds']:
            print(f"\nInspecting entry index {i}:")
            pprint(data[i])
            break
except Exception as e:
    print(f"Error: {e}")
