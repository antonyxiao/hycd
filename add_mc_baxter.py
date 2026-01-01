import csv
import re
import collections
import os

# Configuration
HANZI_CSV = 'hanzi_cards.csv'
BAXTER_CSV = 'BaxterSagartOC2015-10-13.csv'
OUTPUT_CSV = 'hanzi_cards_mc.csv'

def clean_gloss(text):
    """Simple cleanup for keyword matching."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = set(text.split())
    # remove common small words
    words = {w for w in words if len(w) > 2}
    return words

def main():
    if not os.path.exists(BAXTER_CSV):
        print(f"Error: {BAXTER_CSV} not found.")
        return

    # 1. Load Baxter-Sagart Data
    # Mapping: (Char, Pinyin) -> list of {'mc': ..., 'gloss': ..., 'keywords': ...}
    baxter_data = collections.defaultdict(list)
    
    print("Loading Baxter-Sagart data...")
    with open(BAXTER_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            char = row['zi'].strip()
            py = row['py'].strip()
            mc = row['MC'].strip()
            gloss = row['gloss'].strip()
            
            baxter_data[(char, py)].append({
                'mc': mc,
                'gloss': gloss,
                'keywords': clean_gloss(gloss)
            })

    # 2. Process Hanzi Cards
    print(f"Processing {HANZI_CSV}...")
    updated_rows = []
    fieldnames = []
    
    with open(HANZI_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        # Add MiddleChinese column after Jyutping if possible, or just at end
        if 'MiddleChinese' not in fieldnames:
            # Insert after Jyutping (index 5)
            idx = fieldnames.index('Jyutping') + 1
            fieldnames.insert(idx, 'MiddleChinese')
            
        for row in reader:
            char_display = row['Character'] # e.g. "台（臺）"
            pinyin = row['Pinyin']
            english_def = row['English']
            eng_keywords = clean_gloss(english_def)
            
            # Extract all candidate characters for matching (Simp + Trad variants)
            # From ID: 屿_嶼_1 -> ['屿', '嶼']
            id_parts = row['ID'].split('_')
            candidates = set()
            if len(id_parts) >= 2:
                candidates.add(id_parts[0]) # Simplified
                # Check middle part for variants
                variants = id_parts[1]
                # Split variants by any non-hanzi characters
                for v in re.findall(r'[\u4e00-\u9fff]', variants):
                    candidates.add(v)
            
            # Also add from character field just in case
            for v in re.findall(r'[\u4e00-\u9fff]', char_display):
                candidates.add(v)

            # Find matching MC entries
            possible_mcs = []
            for cand_char in candidates:
                matches = baxter_data.get((cand_char, pinyin), [])
                for m in matches:
                    # Score based on keyword overlap
                    score = len(m['keywords'].intersection(eng_keywords))
                    possible_mcs.append((score, m['mc'], m['gloss']))

            # Selection logic
            selected_mc = ""
            if possible_mcs:
                # Sort by score desc
                possible_mcs.sort(key=lambda x: x[0], reverse=True)
                best_score = possible_mcs[0][0]
                
                # If we have a clear winner or multiple with same score
                # Take all unique MCs from the top score group
                winners = set()
                for score, mc, gloss in possible_mcs:
                    if score == best_score:
                        winners.add(mc)
                    else:
                        break
                selected_mc = " / ".join(sorted(list(winners)))
            
            row['MiddleChinese'] = selected_mc
            updated_rows.append(row)

    # 3. Write Output
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Done! Saved {len(updated_rows)} cards to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
