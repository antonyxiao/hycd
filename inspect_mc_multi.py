import pickle
import sys

try:
    with open('jp_mc_en.pkl', 'rb') as f:
        data = pickle.load(f)
    
    # Find a char with multiple MC sounds (if list length > 1)
    for char, info in data.items():
        mc = info.get('mc')
        # Check if it's a list with > 1 item, or a string that might need parsing?
        # Based on previous read, it looked like a string "'oj".
        # Let's see the raw type.
        if mc:
            print(f"Char: {char}, Type: {type(mc)}, Value: {mc}")
            # If it's a list, stop at first one with > 1
            if isinstance(mc, list) and len(mc) > 1:
                print(f"FOUND MULTIPLE: {char} -> {mc}")
                break
            # If it's a string, maybe we check for commas? 
            # But earlier read showed single string.
            
    # Let's force check a known polyphone like 行 or 乐
    print("\nSpecific Checks:")
    for c in ['行', '乐', '好']:
        if c in data:
            print(f"{c}: {data[c].get('mc')}")
            
except Exception as e:
    print(f"Error: {e}")
