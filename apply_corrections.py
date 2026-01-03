import sys
import re

# Vowels for tone marking priority
VOWELS = "aoeiuüv"
# Maps for tones
TONE_MARKS = {
    'a': "āáǎà",
    'o': "ōóǒò",
    'e': "ēéěè",
    'i': "īíǐì",
    'u': "ūúǔù",
    'ü': "ǖǘǚǜ",
    'v': "ǖǘǚǜ"
}

def numbered_to_marked(pinyin_numbered):
    """
    Converts numbered pinyin (e.g. 'ai1', 'lv4', 'da5') to tone marked (e.g. 'āi', 'lǜ', 'da').
    """
    if not pinyin_numbered:
        return ""
    
    # Separate syllable and tone
    match = re.match(r'^([a-zA-Züv]+)(\d)$', pinyin_numbered)
    if not match:
        return pinyin_numbered
    
    syl = match.group(1).lower()
    tone = int(match.group(2))
    
    if tone == 5 or tone == 0:
        # Neutral tone, just return syllable
        return syl.replace('v', 'ü')
    
    syl = syl.replace('v', 'ü')
    
    def replace_char(s, idx, char_with_tone):
        return s[:idx] + char_with_tone + s[idx+1:]
        
    idx_to_mark = -1
    
    # Standard Pinyin marking rules
    if 'a' in syl:
        idx_to_mark = syl.find('a')
    elif 'e' in syl:
        idx_to_mark = syl.find('e')
    elif 'ou' in syl:
        idx_to_mark = syl.find('o')
    else:
        # For 'iu' or 'ui', mark the last vowel. 
        # For single vowels, this also works.
        for i in range(len(syl) - 1, -1, -1):
            if syl[i] in VOWELS:
                idx_to_mark = i
                break
                
    if idx_to_mark != -1:
        char = syl[idx_to_mark]
        if char in TONE_MARKS:
            # tone 1-4 maps to index 0-3
            marked_char = TONE_MARKS[char][tone - 1]
            return replace_char(syl, idx_to_mark, marked_char)
            
    return pinyin_numbered

def apply_corrections(suggestions_file, csv_file):
    # 1. Parse suggestions
    corrections = {} # line_index (0-based) -> new_pinyin_marked
    
    print("Parsing suggestions...")
    with open(suggestions_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: 
                continue
            # Format: Line 18: 锿 | XHZD: ā | ... | Suggestions: ['ai1', '...']
            # We capture the FIRST suggestion in the list which is the highest ranked.
            match = re.search(r'Line (\d+):.+Suggestions: [\'\"]([^\'\"]+)', line)
            if match:
                line_num = int(match.group(1))
                best_pinyin_numbered = match.group(2)
                
                new_pinyin_marked = numbered_to_marked(best_pinyin_numbered)
                corrections[line_num - 1] = new_pinyin_marked
    
    print(f"Loaded {len(corrections)} highest-ranked corrections.")

    # 2. Read CSV
    print("Reading CSV...")
    with open(csv_file, 'r', encoding='utf-8') as f:
        csv_lines = f.readlines()
        
    # 3. Apply corrections
    applied_count = 0
    
    for line_idx, new_pinyin in corrections.items():
        if line_idx < 0 or line_idx >= len(csv_lines):
            print(f"Warning: Line {line_idx+1} out of bounds.")
            continue
            
        row_content = csv_lines[line_idx]
        parts = row_content.split(',')
        
        # CSV structure: Character, Page, Column_Entry, Pinyin, ...
        if len(parts) > 3:
            old_pinyin = parts[3]
            parts[3] = new_pinyin
            
            # Reconstruct line
            new_line = ",".join(parts)
            csv_lines[line_idx] = new_line
            applied_count += 1
        else:
            print(f"Warning: Line {line_idx+1} malformed or too short.")

    # 4. Write back
    print(f"Writing {applied_count} corrections to {csv_file}...")
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.writelines(csv_lines)
    print("Success.")

if __name__ == "__main__":
    apply_corrections("pinyin_suggestions.txt", "xhzd_corrected.csv")
