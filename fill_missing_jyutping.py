import csv
import re
import os

CSV_FILE = 'hanzi_cards_complete.csv'
UNIHAN_FILE = '/home/antony/.gemini/tmp/f9a74935d10281ca610e70c9e3ea1e0dc2d0997b73b4f242f57894b06bd629b0/Unihan_Readings.txt'

def load_unihan_cantonese(filepath):
    print("Loading Unihan Cantonese readings...")
    cantonese_map = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[1] == 'kCantonese':
                code_point = parts[0]
                reading = parts[2]
                try:
                    char = chr(int(code_point[2:], 16))
                    # Take the first reading if multiple (separated by space)
                    # Unihan readings are like "jau1" or "zim1 zim2"
                    # We'll normalize to just the first one for simplicity, or join with /
                    # Let's use the first one as primary
                    primary_reading = reading.split()[0]
                    cantonese_map[char] = primary_reading
                except ValueError:
                    continue
    print(f"Loaded {len(cantonese_map)} Cantonese readings.")
    return cantonese_map

def main():
    if not os.path.exists(CSV_FILE):
        print(f"{CSV_FILE} not found.")
        return

    rows = []
    missing_count = 0
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Check which chars need lookup
    chars_to_lookup = set()
    for row in rows:
        if not row['Jyutping'].strip():
            # Extract base char: "𬍡（璗）" -> "𬍡"
            char_display = row['Character']
            base_char = re.sub(r'（.*?）', '', char_display).strip()
            # Also consider variants inside parens if base char fails?
            # For now just base char.
            chars_to_lookup.add(base_char)
            missing_count += 1
            
    print(f"Found {missing_count} rows missing Jyutping.")
    
    if missing_count == 0:
        print("No missing Jyutping. Exiting.")
        return

    # Load Unihan
    unihan_map = load_unihan_cantonese(UNIHAN_FILE)
    
    filled_count = 0
    for row in rows:
        if not row['Jyutping'].strip():
            char_display = row['Character']
            base_char = re.sub(r'（.*?）', '', char_display).strip()
            
            jyutping = unihan_map.get(base_char)
            
            # If base char not found, try variants if any
            if not jyutping:
                variants = re.findall(r'（(.*?)）', char_display)
                if variants:
                    # variants string might be "a、b"
                    vars_list = re.split(r'[、,]', variants[0])
                    for v in vars_list:
                        v = v.strip()
                        if v in unihan_map:
                            jyutping = unihan_map[v]
                            break
            
            if jyutping:
                row['Jyutping'] = jyutping
                filled_count += 1
    
    print(f"Filled {filled_count} missing Jyutping entries.")
    
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print("Done.")

if __name__ == '__main__':
    main()
