import sys
import time
import concurrent.futures
from scrape_zi_tools import get_guanhua_readings

# Pinyin tone mapping
tone_map = {
    'ā': 'a1', 'á': 'a2', 'ǎ': 'a3', 'à': 'a4',
    'ē': 'e1', 'é': 'e2', 'ě': 'e3', 'è': 'e4',
    'ī': 'i1', 'í': 'i2', 'ǐ': 'i3', 'ì': 'i4',
    'ō': 'o1', 'ó': 'o2', 'ǒ': 'o3', 'ò': 'o4',
    'ū': 'u1', 'ú': 'u2', 'ǔ': 'u3', 'ù': 'u4',
    'ǖ': 'v1', 'ǘ': 'v2', 'ǚ': 'v3', 'ǜ': 'v4',
    'ü': 'v'
}

# Reverse mapping for vowels to remove tone marks
vowel_map = {
    'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
    'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
    'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
    'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
    'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
    'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v',
    'ü': 'v'
}

def get_guanhua_readings_with_retry(char, max_retries=3):
    for attempt in range(max_retries):
        try:
            return get_guanhua_readings(char)
        except Exception as e:
            if attempt < max_retries - 1:
                # print(f"Error fetching readings for {char} (attempt {attempt+1}/{max_retries}): {e}. Retrying...", file=sys.stderr)
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Failed to get readings for {char} after {max_retries} attempts: {e}", file=sys.stderr)
                return [] # Return empty list on failure to avoid crashing

def convert_to_numbered(pinyin):
    """
    Converts pinyin with tone marks to numbered pinyin.
    e.g., 'bǎn' -> 'ban3', 'da' -> 'da5', 'lǜ' -> 'lv4'
    """
    if not pinyin:
        return ""
        
    syl = pinyin
    tone = 5 # Default to neutral
    
    # Check for tone marks
    for char, mapped in tone_map.items():
        if char in syl:
            tone = int(mapped[-1])
            if mapped[-1].isdigit(): # mapped is like a1, v4
                 # Replace the vowel with plain version
                 syl = syl.replace(char, vowel_map[char])
            else:
                 # Case where tone_map entry might not have number if I defined plain ü there
                 syl = syl.replace(char, 'v')
            break
            
    # Handle plain 'ü' if not handled by loop (neutral tone ü)
    if 'ü' in syl:
        syl = syl.replace('ü', 'v')
        
    return f"{syl}{tone}"

def process_line(line_info):
    """
    Process a single line.
    line_info is a tuple (index, line_content)
    Returns: (index, keep_line_bool, message, line_content)
    """
    i, line = line_info
    line = line.strip()
    if not line:
        return (i, False, None, line)
        
    # Line format: Line 18: 锿 | XHZD: ā | CEDICT: ['ai1']
    parts = line.split('|')
    if len(parts) < 3:
        return (i, True, None, line) # Keep malformed lines
        
    # Extract char
    char_part = parts[0].strip()
    char = char_part.split(' ')[-1]
    
    # Extract XHZD pinyin
    xhzd_part = parts[1].strip()
    xhzd_pinyin_raw = xhzd_part.replace('XHZD:', '').strip()
    
    # Convert to numbered
    xhzd_numbered = convert_to_numbered(xhzd_pinyin_raw)
    
    # Get valid readings
    valid_readings = get_guanhua_readings_with_retry(char)
    
    if xhzd_numbered in valid_readings:
        return (i, False, f"Line {i+1}: Validated {char} ({xhzd_pinyin_raw} -> {xhzd_numbered}) in {valid_readings}. Removing.", line)
    else:
        return (i, True, f"Line {i+1}: Mismatch confirmed for {char} ({xhzd_pinyin_raw} -> {xhzd_numbered}). Valid: {valid_readings}", line)

def process_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"Processing {len(lines)} lines with 10 processes...")
    
    # Prepare data for processing
    indexed_lines = [(i, line) for i, line in enumerate(lines)]
    
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=10) as executor:
        # Map returns results in the order of calls, which is perfect
        for result in executor.map(process_line, indexed_lines):
            results.append(result)
            if result[2]: # If there is a message
                print(result[2])

    # Reconstruct the list of lines to keep
    # We sort by index just in case, though map preserves order
    results.sort(key=lambda x: x[0])
    
    new_lines = [res[3] for res in results if res[1]]

    print(f"Finished. Reduced from {len(lines)} to {len(new_lines)} lines.")
    
    with open(filename, 'w', encoding='utf-8') as f:
        for line in new_lines:
            f.write(line + '\n')

if __name__ == "__main__":
    process_file("pinyin_mismatches_smart.txt")