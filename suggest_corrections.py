import sys
import time
import concurrent.futures
from scrape_zi_tools import get_guanhua_readings

# Pinyin tone mapping (reused)
tone_map = {
    'ā': 'a1', 'á': 'a2', 'ǎ': 'a3', 'à': 'a4',
    'ē': 'e1', 'é': 'e2', 'ě': 'e3', 'è': 'e4',
    'ī': 'i1', 'í': 'i2', 'ǐ': 'i3', 'ì': 'i4',
    'ō': 'o1', 'ó': 'o2', 'ǒ': 'o3', 'ò': 'o4',
    'ū': 'u1', 'ú': 'u2', 'ǔ': 'u3', 'ù': 'u4',
    'ǖ': 'v1', 'ǘ': 'v2', 'ǚ': 'v3', 'ǜ': 'v4',
    'ü': 'v'
}

vowel_map = {
    'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
    'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
    'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
    'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
    'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
    'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v',
    'ü': 'v'
}

initials = sorted(['b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h', 'j', 'q', 'x', 'zh', 'ch', 'sh', 'r', 'z', 'c', 's', 'y', 'w'], key=len, reverse=True)

def get_guanhua_readings_with_retry(char, max_retries=3):
    for attempt in range(max_retries):
        try:
            return get_guanhua_readings(char)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return []

def convert_to_numbered(pinyin):
    if not pinyin:
        return ""
    syl = pinyin
    tone = 5
    for char, mapped in tone_map.items():
        if char in syl:
            tone = int(mapped[-1])
            if mapped[-1].isdigit():
                 syl = syl.replace(char, vowel_map[char])
            else:
                 syl = syl.replace(char, 'v')
            break
    if 'ü' in syl:
        syl = syl.replace('ü', 'v')
    return f"{syl}{tone}"

def parse_pinyin(p):
    if not p:
        return "", "", 5
    
    if p[-1].isdigit():
        tone = int(p[-1])
        syl = p[:-1]
    else:
        tone = 5
        syl = p
    
    initial = ""
    final = syl
    for ini in initials:
        if syl.startswith(ini):
            initial = ini
            final = syl[len(ini):]
            break
    return initial, final, tone

def calculate_score(target, candidate):
    """
    Calculate similarity score between target (XHZD) and candidate (Valid).
    Higher is better.
    """
    i1, f1, t1 = parse_pinyin(target)
    i2, f2, t2 = parse_pinyin(candidate)
    
    score = 0
    
    # Syllable match (Initial + Final)
    if i1 == i2 and f1 == f2:
        score += 100
    
    # Initial match
    if i1 == i2:
        score += 10
        
    # Final match
    if f1 == f2:
        score += 10
        
    # Tone closeness (max 5 points)
    # 5 - distance. e.g. dist 0 -> 5 pts. dist 4 -> 1 pt.
    tone_dist = abs(t1 - t2)
    score += max(0, 5 - tone_dist)
    
    return score

def process_line(line_info):
    i, line = line_info
    line = line.strip()
    if not line:
        return None
        
    parts = line.split('|')
    if len(parts) < 3:
        return f"{line} | Error: Malformed line"
        
    char_part = parts[0].strip()
    char = char_part.split(' ')[-1]
    
    xhzd_part = parts[1].strip()
    xhzd_pinyin_raw = xhzd_part.replace('XHZD:', '').strip()
    xhzd_numbered = convert_to_numbered(xhzd_pinyin_raw)
    
    valid_readings = get_guanhua_readings_with_retry(char)
    
    if not valid_readings:
        return f"{line} | Suggestions: None (No data found)"
        
    if xhzd_numbered in valid_readings:
        # Should have been filtered, but just in case
        return f"{line} | Note: Match found (should have been filtered)"
        
    # Find best matches
    scored_candidates = []
    for cand in valid_readings:
        score = calculate_score(xhzd_numbered, cand)
        scored_candidates.append((score, cand))
        
    # Sort by score desc
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    best_candidates = [c[1] for c in scored_candidates]
    # Optionally include score? Just the candidates is cleaner.
    
    return f"{line} | Suggestions: {best_candidates}"

def process_file(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"Generating suggestions for {len(lines)} lines with 10 processes...")
    
    indexed_lines = [(i, line) for i, line in enumerate(lines)]
    
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
        for result in executor.map(process_line, indexed_lines):
            if result:
                results.append(result)

    print(f"Finished. Writing results to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in results:
            f.write(line + '\n')

if __name__ == "__main__":
    process_file("pinyin_mismatches_smart.txt", "pinyin_suggestions.txt")
