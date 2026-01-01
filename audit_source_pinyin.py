import csv
import re
import unicodedata

XHZD_FILE = 'xhzd_corrected.csv'
CEDICT_FILE = 'cedict_ts.u8'

def load_cedict():
    print("Loading CEDICT...")
    cedict = {}
    with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip(): continue
            parts = line.strip().split('/')
            if len(parts) < 2: continue
            
            header = parts[0]
            match = re.match(r'(\S+)\s+(\S+)\s+\[(.*)\]', header)
            if match:
                trad, simp, pinyin = match.groups()
                # CEDICT pinyin is numbered: "a1"
                # Handle multiple pinyins if present? CEDICT entries are usually split by definition
                # but unique chars map to set of pinyins.
                if simp not in cedict:
                    cedict[simp] = set()
                
                # Normalize pinyin: lowercase, remove spaces, u: -> v
                norm_pinyin = pinyin.lower().replace("u:", "v").replace(" ", "")
                cedict[simp].add(norm_pinyin)
    return cedict

def parse_pinyin_info(pinyin_str):
    # Split on delimiters and take first for primary comparison
    first_part = re.split(r'[又或/,;]', pinyin_str)[0].strip()
    
    # Remove parens and content
    clean = re.sub(r'（.*?）', '', first_part)
    clean = re.sub(r'\(.*?\)', '', clean)
    clean = clean.lower().replace('u:', 'v').replace('ü', 'v')
    
    # Extract tones from unicode marks BEFORE normalization strips them
    tones = set()
    mapping = {
        'ā': 1, 'á': 2, 'ǎ': 3, 'à': 4,
        'ē': 1, 'é': 2, 'ě': 3, 'è': 4,
        'ī': 1, 'í': 2, 'ǐ': 3, 'ì': 4,
        'ō': 1, 'ó': 2, 'ǒ': 3, 'ò': 4,
        'ū': 1, 'ú': 2, 'ǔ': 3, 'ù': 4,
        'ǖ': 1, 'ǘ': 2, 'ǚ': 3, 'ǜ': 4
    }
    
    for char, t in mapping.items():
        if char in clean:
            tones.add(t)
            
    # Normalize to base letters
    normalized_base = unicodedata.normalize('NFKD', clean).encode('ASCII', 'ignore').decode('ASCII')
    
    # Extract clean letters from normalized base
    letters = re.sub(r'[^a-z0-9v]', '', normalized_base)
    base_letters = re.sub(r'[0-9]', '', letters)
    
    # Check for numbers
    for char in clean:
        if char.isdigit():
            tones.add(int(char))
            
    return base_letters, tones

def main():
    cedict = load_cedict()
    
    print("Auditing XHZD Pinyin (Smart Match)...")
    mismatches = []
    
    with open(XHZD_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) < 4: continue
            char_raw = row[0].strip()
            pinyin_raw = row[3].strip()
            
            if char_raw == '字头' or not pinyin_raw: continue
            
            match = re.search(r'^(.*?)（.*?）$', char_raw)
            base_char = match.group(1) if match else char_raw
            
            if base_char in cedict:
                cedict_pinyins = cedict[base_char]
                
                xhzd_base, xhzd_tones = parse_pinyin_info(pinyin_raw)
                
                match_found = False
                for cp in cedict_pinyins:
                    cedict_base, cedict_tones = parse_pinyin_info(cp)
                    
                    # Letters must match
                    if xhzd_base != cedict_base:
                        continue
                        
                    # Tones must match (subset or equal?)
                    # XHZD might be polyphonic listed as one entry? No, separate entries.
                    # BUT qiānwǎ has {1, 3}. qian1wa3 has {1, 3}.
                    # ā has {1}. ai1 has {1}. Mismatch on letters.
                    
                    # Tone logic:
                    # If XHZD has tones, they should match CEDICT tones.
                    # If XHZD has no tones (neutral), CEDICT might have 5 or nothing.
                    # If sets are equal, good.
                    
                    if xhzd_tones == cedict_tones:
                        match_found = True
                        break
                    
                    # Allow loose neutral match: empty vs {5}
                    if not xhzd_tones and cedict_tones == {5}:
                        match_found = True
                        break
                
                if not match_found:
                    mismatches.append({
                        'line': i + 1,
                        'char': base_char,
                        'xhzd': pinyin_raw,
                        'cedict': list(cedict_pinyins)
                    })
    
    # Report
    print(f"Found {len(mismatches)} mismatches.")
    with open('pinyin_mismatches_smart.txt', 'w', encoding='utf-8') as f:
        for m in mismatches:
            f.write(f"Line {m['line']}: {m['char']} | XHZD: {m['xhzd']} | CEDICT: {m['cedict']}\n")
            
    print("Report saved to pinyin_mismatches_smart.txt")

if __name__ == '__main__':
    main()
