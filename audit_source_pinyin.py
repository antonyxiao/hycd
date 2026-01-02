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
    
    print("Auditing XHZD Pinyin (Character-level check)...")
    
    # Group XHZD entries by character
    xhzd_entries = {} # char -> list of {line, pinyin}
    
    with open(XHZD_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) < 4: continue
            char_raw = row[0].strip()
            pinyin_raw = row[3].strip()
            
            if char_raw == '字头' or not pinyin_raw: continue
            
            match = re.search(r'^(.*?)（.*?）$', char_raw)
            base_char = match.group(1) if match else char_raw
            
            if base_char not in xhzd_entries:
                xhzd_entries[base_char] = []
            
            xhzd_entries[base_char].append({
                'line': i + 1,
                'pinyin': pinyin_raw
            })
            
    mismatches = []
    
    for char, entries in xhzd_entries.items():
        if char not in cedict:
            continue
            
        cedict_pinyins = cedict[char]
        
        # Check if ANY entry for this char matches ANY cedict pinyin
        has_any_match = False
        
        for entry in entries:
            xhzd_base, xhzd_tones = parse_pinyin_info(entry['pinyin'])
            
            for cp in cedict_pinyins:
                cedict_base, cedict_tones = parse_pinyin_info(cp)
                
                if xhzd_base != cedict_base:
                    continue
                
                # Check tones
                if xhzd_tones == cedict_tones:
                    has_any_match = True
                    break
                if not xhzd_tones and cedict_tones == {5}:
                    has_any_match = True
                    break
            
            if has_any_match:
                break
        
        # If NO entry matched, report ALL entries for this char
        if not has_any_match:
            for entry in entries:
                mismatches.append({
                    'line': entry['line'],
                    'char': char,
                    'xhzd': entry['pinyin'],
                    'cedict': list(cedict_pinyins)
                })
    
    # Sort by line number
    mismatches.sort(key=lambda x: x['line'])
    
    # Report
    print(f"Found {len(mismatches)} mismatches.")
    with open('pinyin_mismatches_smart.txt', 'w', encoding='utf-8') as f:
        for m in mismatches:
            f.write(f"Line {m['line']}: {m['char']} | XHZD: {m['xhzd']} | CEDICT: {m['cedict']}\n")
            
    print("Report saved to pinyin_mismatches_smart.txt")

if __name__ == '__main__':
    main()
