import pickle
import sys

try:
    with open('jp_mc_en.pkl', 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded {len(data)} entries.")
    # Show first 5 non-empty MC entries
    count = 0
    for char, info in data.items():
        if info.get('mc'):
            print(f"Char: {char}, MC: {info.get('mc')}")
            count += 1
        if count >= 5:
            break
except FileNotFoundError:
    print("File not found")
except Exception as e:
    print(f"Error: {e}")
