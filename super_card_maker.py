import csv
import re
import collections
import unicodedata
import os
import json
import threading
import requests
import time
import concurrent.futures

# Optional libraries
try:
    import pycantonese
    from hanziconv import HanziConv
    import ToJyutping
    HAS_NLP = True
except ImportError:
    HAS_NLP = False
    print("Warning: 'pycantonese', 'hanziconv', or 'ToJyutping' not found. Jyutping generation will be limited.")

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
INPUT_CSV = 'xhzd_corrected.csv'
CEDICT_FILE = 'cedict_ts.u8'
FREQ_FILE = 'CharFreq-Combined.csv'
BAXTER_FILE = 'BaxterSagartOC2015-10-13.csv'
TRANSLATION_CACHE_FILE = 'translation_cache.json'
HINT_CACHE_FILE = 'hint_cache.json'
JP_CACHE_FILE = 'jp_cache.json'
LD_CHARSET_FILE = 'ld_charset.csv'
UNIHAN_FILE = 'Unihan_Readings.txt'
OUTPUT_CSV = 'hanzi_cards_complete.csv'
PINYIN_SUGGESTIONS_FILE = 'pinyin_suggestions.txt'

def load_env_key():
    try:
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('OPENROUTER_API_KEY='):
                        return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error loading .env: {e}")
    return ""

# LLM Config
OPENROUTER_API_KEY = load_env_key()
USE_LLM = True 

# -----------------------------------------------------------------------------
# DATA LOADING
# -----------------------------------------------------------------------------

def load_frequency_map(filepath):
    freq_data = {}
    if not os.path.exists(filepath):
        print(f"Warning: Frequency file '{filepath}' not found.")
        return freq_data

    print(f"Loading Frequency data from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 4:
                try:
                    # File format: Rank, Character, RawFreq, Percentile
                    freq_data[row[1]] = {
                        'rank': row[0],
                        'raw': row[2],
                        'percentile': row[3]
                    }
                except IndexError:
                    continue
    return freq_data

def load_baxter_data(filepath):
    data = collections.defaultdict(list)
    if not os.path.exists(filepath):
        print(f"Warning: Baxter file '{filepath}' not found.")
        return data

    print(f"Loading Baxter-Sagart data from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            char = row.get('zi', '').strip()
            py = row.get('py', '').strip()
            mc = row.get('MC', '').strip()
            gloss = row.get('gloss', '').strip()
            
            if char:
                # Clean gloss for keywords
                clean_keywords = set()
                if gloss:
                    clean_text = re.sub(r'[^\w\s]', ' ', gloss.lower())
                    clean_keywords = {w for w in clean_text.split() if len(w) > 2}

                data[(char, py)].append({
                    'mc': mc,
                    'gloss': gloss,
                    'keywords': clean_keywords
                })
    return data

def load_json_cache(filepath):
    if os.path.exists(filepath):
        print(f"Loading cache from {filepath}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Corrupt cache file {filepath}.")
    return {}

def save_json_cache(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_unihan_data(filepath):
    print(f"Loading Unihan data from {filepath}...")
    data = collections.defaultdict(dict)
    if not os.path.exists(filepath):
        print(f"Warning: Unihan file '{filepath}' not found.")
        return data
        
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip(): continue
            parts = line.strip().split('\t')
            if len(parts) < 3: continue
            
            code_point = parts[0]
            field = parts[1]
            value = parts[2]
            
            try:
                char = chr(int(code_point[2:], 16))
                if field == 'kTang':
                    data[char]['mc'] = value
                elif field == 'kCantonese':
                    data[char]['jyutping_list'] = value.split()
                    data[char]['jyutping'] = value.split()[0]
                elif field == 'kHangul':
                    # Clean up: "온:N 은:N" -> "온 / 은"
                    cleaned_values = []
                    for v in value.split():
                        v = v.split(':')[0]
                        cleaned_values.append(v)
                    data[char]['hangul'] = " / ".join(cleaned_values)
                elif field == 'kHanyuPinlu':
                    # e.g. zhǎng(1879) cháng(1179)
                    readings = re.findall(r'([a-zA-Züvāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+)\(\d+\)', value)
                    data[char]['pinlu'] = readings
                elif field == 'kSMSZD2003Readings':
                    # e.g. cháng粵coeng4 zhàng粵zoeng6
                    mapping = {}
                    pairs = value.split()
                    for pair in pairs:
                        if '粵' in pair:
                            m_py, c_jp = pair.split('粵')
                            mapping[m_py] = c_jp
                    data[char]['m_to_c'] = mapping
            except ValueError:
                continue
    return data

def parse_cedict(filepath):
    cedict_data = {}
    cedict_reverse = collections.defaultdict(set)
    STOPWORDS = {
        'a', 'an', 'the', 'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but', 'and', 'or', 'as', 'if',
        'so', 'than', 'that', 'this', 'these', 'those', 'from', 'up', 'down', 'out', 'into', 'over', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
        'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'don', 'should', 'now'
    }

    if not os.path.exists(filepath):
        print(f"Warning: CEDICT file '{filepath}' not found.")
        return cedict_data, cedict_reverse

    print(f"Parsing CEDICT from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.rstrip('/').split('/')
            if len(parts) <= 1:
                continue
            
            english_raw = "; ".join(parts[1:])
            header = parts[0]
            match = re.match(r'(\S+)\s+(\S+)\s+\[(.*)\]', header)
            if match:
                trad, simp, pinyin_raw = match.groups()
                
                if simp not in cedict_data:
                    cedict_data[simp] = []
                
                norm_pinyin = pinyin_raw.lower().replace("u:", "v")
                
                cedict_data[simp].append({
                    'pinyin': norm_pinyin,
                    'eng': english_raw
                })
                
                # Keywords for scoring
                text = re.sub(r'[^\w\s]', ' ', english_raw)
                words = text.lower().split()
                keywords = {w for w in words if w not in STOPWORDS and len(w) > 1}
                cedict_reverse[simp].update(keywords)
    
    return cedict_data, cedict_reverse

# -----------------------------------------------------------------------------
# PINYIN CORRECTION HELPERS
# -----------------------------------------------------------------------------

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
        return syl.replace('v', 'ü')
    
    syl = syl.replace('v', 'ü')
    
    def replace_char(s, idx, char_with_tone):
        return s[:idx] + char_with_tone + s[idx+1:]
        
    idx_to_mark = -1
    
    if 'a' in syl:
        idx_to_mark = syl.find('a')
    elif 'e' in syl:
        idx_to_mark = syl.find('e')
    elif 'ou' in syl:
        idx_to_mark = syl.find('o')
    else:
        for i in range(len(syl) - 1, -1, -1):
            if syl[i] in VOWELS:
                idx_to_mark = i
                break
                
    if idx_to_mark != -1:
        char = syl[idx_to_mark]
        if char in TONE_MARKS:
            marked_char = TONE_MARKS[char][tone - 1]
            return replace_char(syl, idx_to_mark, marked_char)
            
    return pinyin_numbered

def load_pinyin_suggestions(filepath):
    corrections = {} # 1-based line_num -> new_pinyin_marked
    if not os.path.exists(filepath):
        print(f"Warning: Suggestions file '{filepath}' not found. Skipping pinyin corrections.")
        return corrections

    print(f"Loading Pinyin suggestions from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            # Robust parsing for "Line 123: ... Suggestions: ['pinyin1', ...]"
            match = re.search(r'Line (\d+):.+Suggestions: \[[\'"]([^\'\n]+)[\'"]', line)
            # print(f"Debug: Line '{line}' match: {match}")
            if match:
                line_num = int(match.group(1))
                best_pinyin_numbered = match.group(2)
                new_pinyin_marked = numbered_to_marked(best_pinyin_numbered)
                corrections[line_num] = new_pinyin_marked
    
    print(f"Loaded {len(corrections)} pinyin corrections.")
    return corrections

def apply_pinyin_override(row_index, current_pinyin, corrections):
    """
    Overrides the pinyin if a correction exists for this row index.
    """
    if row_index in corrections:
        # print(f"Overriding line {row_index}: {current_pinyin} -> {corrections[row_index]}")
        return corrections[row_index]
    return current_pinyin

# -----------------------------------------------------------------------------
# LLM GENERATION
# -----------------------------------------------------------------------------

def generate_hints_batch(batch_items, batch_id):
    """
    batch_items: list of {'id': ..., 'char': ..., 'def': ...}
    """
    prompt = f"""
    Generate helpful, high-quality Chinese hints (example words or short phrases) for these characters based on their definition.
    Current entries have NO hints. 
    Format: "Example1 / Example2" (Traditional or Simplified is fine, prefer contextually appropriate).
    Keep it concise (2-3 examples max).
    
    IMPORTANT: If the character itself appears in the example, replace it with '～'. 
    Example: For character '爱', if the hint is '爱情', return '～情'.

    Return ONLY a JSON object where keys are the 'id' and values are the hint strings.

    Entries:
    {json.dumps(batch_items, ensure_ascii=False)}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek/deepseek-v3.2",
        "messages": [
            {"role": "system", "content": "You are a Chinese language dictionary assistant. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    print(f"    [Batch {batch_id}] Sending request...")
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )
        if response.status_code != 200:
            print(f"    [Batch {batch_id}] API Error {response.status_code}: {response.text[:100]}...")
            return {}
        
        raw_content = response.json()['choices'][0]['message']['content']
        clean_content = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip(), flags=re.MULTILINE)
        results = json.loads(clean_content)
        
        # Post-process: enforce tilde replacement
        char_map = {item['id']: item['char'] for item in batch_items}
        processed_results = {}
        for rid, hint in results.items():
            if rid in char_map and isinstance(hint, str):
                char = char_map[rid]
                # Extract base char if complex variant
                base = re.sub(r'（.*?）', '', char).strip()
                if base:
                    hint = hint.replace(base, '～')
                processed_results[rid] = hint
            else:
                processed_results[rid] = hint
                
        print(f"    [Batch {batch_id}] Success.")
        return processed_results
    except Exception as e:
        print(f"    [Batch {batch_id}] Error: {e}")
        return {}

def run_missing_hint_generation(missing_items, cache_file, cache_data):
    """
    missing_items: list of dicts {'id', 'char', 'def'}
    """
    if not missing_items:
        return

    BATCH_SIZE = 20
    MAX_WORKERS = 20
    
    batches = [missing_items[i:i + BATCH_SIZE] for i in range(0, len(missing_items), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"Generating hints for {len(missing_items)} items in {total_batches} batches...")
    
    lock = threading.Lock()
    
    def process_batch(batch, idx):
        results = generate_hints_batch(batch, idx+1)
        if results:
            with lock:
                cache_data.update(results)
                save_json_cache(cache_data, cache_file)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, batch in enumerate(batches):
            futures.append(executor.submit(process_batch, batch, i))
            time.sleep(0.1) # stagger starts
        concurrent.futures.wait(futures)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def pinyin_marks_to_numbers(pinyin_str):
    # Remove parens and content
    clean = re.sub(r'（.*?）', '', pinyin_str)
    clean = re.sub(r'\(.*\)', '', clean)
    clean = clean.lower().replace('u:', 'v').replace('ü', 'v')
    
    mapping = {
        'ā': 1, 'á': 2, 'ǎ': 3, 'à': 4,
        'ē': 1, 'é': 2, 'ě': 3, 'è': 4,
        'ī': 1, 'í': 2, 'ǐ': 3, 'ì': 4,
        'ō': 1, 'ó': 2, 'ǒ': 3, 'ò': 4,
        'ū': 1, 'ú': 2, 'ǔ': 3, 'ù': 4,
        'ǖ': 1, 'ǘ': 2, 'ǚ': 3, 'ǜ': 4
    }
    
    # Normalize base
    normalized = unicodedata.normalize('NFKD', clean).encode('ASCII', 'ignore').decode('ASCII')
    base_letters = re.sub(r'[^a-z0-9v]', '', normalized)
    base_letters = re.sub(r'[0-9]', '', base_letters)
    
    # Extract tone
    tone = 0
    for char, t in mapping.items():
        if char in clean:
            tone = t
            break
    if tone == 0:
        for char in clean:
            if char.isdigit():
                tone = int(char)
                break
    
    if tone:
        return f"{base_letters}{tone}"
    return base_letters

def score_definition(target_eng_def, chinese_def_tokens, cedict_reverse):
    score = 0
    text = re.sub(r'[^\w\s]', ' ', target_eng_def)
    target_keywords = set(text.lower().split())

    for cn_token in chinese_def_tokens:
        if cn_token in cedict_reverse:
            potential_eng_keywords = cedict_reverse[cn_token]
            overlap = target_keywords.intersection(potential_eng_keywords)
            score += len(overlap)
    
    if '姓' in chinese_def_tokens and 'surname' in target_keywords:
        score += 10
    
    # Boost if chinese char appears in definition
    for token in chinese_def_tokens:
        if len(token) == 1 and '\u4e00' <= token <= '\u9fff': 
             if token in target_eng_def: 
                 score += 5
    return score

def get_best_cedict_english(char, xhzd_def, xhzd_pinyin, cedict_data, cedict_reverse):
    if char not in cedict_data:
        return ""
    
    candidates = cedict_data[char]
    xhzd_loose = pinyin_marks_to_numbers(xhzd_pinyin)
    
    # Filter by pinyin match
    pinyin_filtered = []
    for cand in candidates:
        cand_loose = ''.join([c for c in cand['pinyin'] if not c.isdigit()])
        if xhzd_loose == cand_loose:
             pinyin_filtered.append(cand)
    
    current_candidates = pinyin_filtered if pinyin_filtered else candidates
    
    if len(current_candidates) == 1:
        return current_candidates[0]['eng']
        
    # Score based on overlap with Chinese definition keywords
    cn_tokens = re.findall(r'[\u4e00-\u9fff]+', xhzd_def)
    scored_candidates = []
    
    for cand in current_candidates:
        score = score_definition(cand['eng'], cn_tokens, cedict_reverse)
        scored_candidates.append((score, cand['eng']))
        
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score = scored_candidates[0][0]
    
    # If no correlation found, return all definitions to be safe
    if best_score == 0:
        unique_defs = sorted(list(set([c['eng'] for c in current_candidates])))
        return "; ".join(unique_defs)
    
    winners = [c[1] for c in scored_candidates if c[0] == best_score]
    return "; ".join(sorted(list(set(winners))))

def get_middle_chinese(candidates, pinyin, english_keywords, baxter_data):
    possible_mcs = []
    for char in candidates:
        matches = baxter_data.get((char, pinyin), [])
        for m in matches:
            score = len(m['keywords'].intersection(english_keywords))
            possible_mcs.append((score, m['mc']))
    
    if not possible_mcs:
        return ""
        
    possible_mcs.sort(key=lambda x: x[0], reverse=True)
    best_score = possible_mcs[0][0]
    
    winners = sorted(list(set([mc for score, mc in possible_mcs if score == best_score])))
    return " / ".join(winners)

def disambiguate_jyutping_batch(batch_items, batch_id):
    """
    batch_items: list of {'id': ..., 'char': ..., 'py': ..., 'def': ..., 'hints': ..., 'candidates': [...]}
    """
    prompt = f"""
    For each Chinese character entry below, select the single most appropriate Cantonese Jyutping reading.
    
    CRITICAL:
    1. If the character has multiple readings (polyphones), choose the one that matches the specific definition and examples.
    2. Example '生': 'sang1' is often used for 'living/born', while 'saang1' is often used for 'unripe/raw/student'.
    3. Example '长': 'coeng4' matches 'cháng' (long), 'zoeng2' matches 'zhǎng' (grow/elder).
    4. If the provided 'candidates' list is missing the correct reading, you MUST provide the correct one anyway.
    
    Return ONLY a JSON object where keys are the 'id' and values are the single selected Jyutping string (e.g. "zoeng2").

    Entries:
    {json.dumps(batch_items, ensure_ascii=False)}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek/deepseek-v3.2",
        "messages": [
            {"role": "system", "content": "You are a world-class Cantonese linguistics expert. You provide accurate Jyutping based on semantic context. Respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    print(f"    [JP Batch {batch_id}] Sending request...")
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )
        if response.status_code != 200:
            print(f"    [JP Batch {batch_id}] API Error {response.status_code}")
            return {}
        
        raw_content = response.json()['choices'][0]['message']['content']
        clean_content = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip(), flags=re.MULTILINE)
        return json.loads(clean_content)
    except Exception as e:
        print(f"    [JP Batch {batch_id}] Error: {e}")
        return {}

def run_jyutping_disambiguation(missing_items, cache_file, cache_data):
    if not missing_items:
        return

    BATCH_SIZE = 20
    MAX_WORKERS = 20
    
    batches = [missing_items[i:i + BATCH_SIZE] for i in range(0, len(missing_items), BATCH_SIZE)]
    print(f"Disambiguating Jyutping for {len(missing_items)} items in {len(batches)} batches...")
    
    lock = threading.Lock()
    
    def process_batch(batch, idx):
        results = disambiguate_jyutping_batch(batch, idx+1)
        if results:
            with lock:
                # Basic validation: ensure the result is one of the candidates if candidates were provided
                valid_results = {}
                batch_map = {item['id']: item['candidates'] for item in batch}
                for rid, jp in results.items():
                    if rid in batch_map:
                        candidates = batch_map[rid]
                        if not candidates or jp in candidates:
                            valid_results[rid] = jp
                        else:
                            # If LLM gave something else, find closest or just take it if candidates were empty
                            valid_results[rid] = jp
                
                cache_data.update(valid_results)
                save_json_cache(cache_data, cache_file)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_batch, b, i) for i, b in enumerate(batches)]
        concurrent.futures.wait(futures)

def enrich_definition_with_jyutping(definition):
    """
    Searches for words in brackets ［word］ followed by pinyin guides （guide）.
    Looks up the word in pycantonese and appends the Jyutping to the guide.
    Example: ［舴艋］（–měng） -> ［舴艋］（–měng/-maang5）
    """
    if not HAS_NLP:
        return definition
        
    def replacer(match):
        full_match = match.group(0)
        word = match.group(1)
        guide = match.group(2)
        
        if '/-' in guide:
            return full_match

        try:
            # ToJyutping handles both simplified and traditional
            jp_list = ToJyutping.get_jyutping_list(word)
        except:
            return full_match
            
        dash = '–' if '–' in guide else '-' 
        if dash not in guide:
            return full_match
            
        if len(word) == 2:
            if guide.startswith(dash):
                pinyin_part = guide[len(dash):].strip()
                # Target is 2nd char
                target_jp = ""
                if len(jp_list) == 2:
                    target_jp = jp_list[1][1]
                elif len(jp_list) == 1:
                    # Combined case: ('傾軋', 'king1aat3')
                    full_jp = jp_list[0][1]
                    parts = re.findall(r'[a-z]+[1-6]', full_jp)
                    if len(parts) == 2:
                        target_jp = parts[1]
                    else:
                        # Fallback to single char lookup
                        target_jp_list = ToJyutping.get_jyutping_list(word[1])
                        if target_jp_list:
                            target_jp = target_jp_list[0][1]
                
                if target_jp:
                    return f"［{word}］（{dash}{pinyin_part}/-{target_jp}）"
            elif guide.endswith(dash):
                pinyin_part = guide[:-len(dash)].strip()
                # Target is 1st char
                target_jp = ""
                if len(jp_list) == 2:
                    target_jp = jp_list[0][1]
                elif len(jp_list) == 1:
                    full_jp = jp_list[0][1]
                    parts = re.findall(r'[a-z]+[1-6]', full_jp)
                    if len(parts) == 2:
                        target_jp = parts[0]
                    else:
                        target_jp_list = ToJyutping.get_jyutping_list(word[0])
                        if target_jp_list:
                            target_jp = target_jp_list[0][1]
                
                if target_jp:
                    return f"［{word}］（{pinyin_part}/-{target_jp}{dash}）"
        
        return full_match

    new_def = re.sub(r'［(.*?)］（(.*?)）', replacer, definition)
    return new_def

def get_cantonese(char_display, hint_str):
    if not HAS_NLP:
        return "", False
    primary_char = re.sub(r'（.*?）', '', char_display).strip()
    
    # Try to find context-specific Jyutping from hints
    if hint_str and isinstance(hint_str, str):
        # Split hints to process words individually
        hints = hint_str.split(' / ')
        for hint in hints:
            if not hint: continue
            # Handle ～ replacement
            word = hint.replace('～', primary_char)
            # Remove any extra info in parens from the hint itself if any
            word = re.sub(r'（.*?）', '', word)
            
            try:
                # ToJyutping handles both simplified and traditional
                jp_list = ToJyutping.get_jyutping_list(word)
                
                # Check the result for our target character
                for ch, jp in jp_list:
                    if ch == primary_char and jp:
                        # Return the first one found in a hint
                        return jp, True
            except:
                continue

    # Fallback to ToJyutping for single character
    try:
        jp_list = ToJyutping.get_jyutping_list(primary_char)
        if jp_list and jp_list[0][1]:
            return jp_list[0][1], False
    except:
        pass
    return "", False

def parse_complex_variants(char_raw):
    CIRCLE_MAP = {c: i+1 for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩")}
    match = re.search(r'^(.*?)（(.*?)）$', char_raw)
    if not match:
        return {}, char_raw
    
    base_char = match.group(1)
    variant_str = match.group(2)
    sense_map = collections.defaultdict(list)
    parts = re.split(r'[、,]', variant_str)
    
    for p in parts:
        nums = []
        range_match = re.search(r'([①-⑩])—([①-⑩])', p)
        if range_match:
            start = CIRCLE_MAP[range_match.group(1)]
            end = CIRCLE_MAP[range_match.group(2)]
            nums.extend(list(range(start, end + 1)))
            p = p.replace(range_match.group(0), '')
        found_nums = re.findall(r'[①-⑩]', p)
        if found_nums:
            nums.extend([CIRCLE_MAP[f] for f in found_nums])
            for f in found_nums:
                p = p.replace(f, '')
        v_clean = p.strip()
        if v_clean:
            if not nums:
                sense_map[0].append(v_clean)
            else:
                for n in set(nums):
                    if v_clean not in sense_map[n]:
                        sense_map[n].append(v_clean)
    return sense_map, base_char

def parse_xhzd_definitions(def_text):
    def_text = re.sub(r'([❶-❿⓫-⓴])', r'\n\1', def_text)
    lines = def_text.split('\n')
    parsed_defs = []
    current_def = ""
    current_hints = []
    
    for line in lines:
        line = line.strip()
        if not line: continue
        is_new_def = re.match(r'^[❶-❿⓫-⓴0-9]\.?', line)
        if (line.startswith('［') or line.startswith('[')) and (parsed_defs or current_def):
             continue
        if is_new_def or (not parsed_defs and not current_def):
            if current_def:
                parsed_defs.append({'def': current_def, 'hints': current_hints})
                current_def = ""
                current_hints = []
            clean_line = re.sub(r'^[❶-❿⓫-⓴0-9]\.?\s*', '', line)
            parts = clean_line.split('：', 1)
            valid_split = False
            if len(parts) == 2:
                left = parts[0]
                if left.count('（') == left.count('）'):
                    valid_split = True
            if valid_split:
                current_def = parts[0].replace('"', '').strip()
                current_hints = [h.strip() for h in parts[1].replace('。', '').split('|')]
            else:
                current_def = clean_line.replace('"', '').strip()
        else:
             current_def += " " + line
    if current_def:
        parsed_defs.append({'def': current_def, 'hints': current_hints})
    return parsed_defs

# -----------------------------------------------------------------------------
# TTS PROXY HELPER
# -----------------------------------------------------------------------------
def get_tts_proxy(pron, pron_map, char_pron_counts, freq_map):
    if not pron: return ""
    candidates = pron_map.get(pron)
    if not candidates:
        return ""
    
    def sort_key(char):
        # 1. Monophony (False < True) -> Prefer count=1
        count = len(char_pron_counts.get(char, set()))
        is_poly = count > 1
        
        # 2. Frequency (Lower rank < Higher rank)
        f = freq_map.get(char)
        if f and f['rank'].isdigit():
            rank = int(f['rank'])
        else:
            rank = 100000
            
        return (is_poly, rank)
    
    sorted_cands = sorted(list(candidates), key=sort_key)
    return sorted_cands[0]

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    # 1. Load Data
    freq_map = load_frequency_map(FREQ_FILE)
    baxter_data = load_baxter_data(BAXTER_FILE)
    cedict_data, cedict_reverse = parse_cedict(CEDICT_FILE)
    trans_cache = load_json_cache(TRANSLATION_CACHE_FILE)
    hint_cache = load_json_cache(HINT_CACHE_FILE)
    jp_cache = load_json_cache(JP_CACHE_FILE)
    unihan_data = load_unihan_data(UNIHAN_FILE)
    
    # Load Pinyin Corrections
    pinyin_corrections = load_pinyin_suggestions(PINYIN_SUGGESTIONS_FILE)
    
    # Build Jyutping Maps from Unihan
    jp_map = collections.defaultdict(set)
    char_jp_counts = collections.defaultdict(set)
    
    for char, data in unihan_data.items():
        if 'jyutping' in data:
            jp = data['jyutping']
            jp_map[jp].add(char)
            char_jp_counts[char].add(jp)
            if 'jyutping_list' in data:
                for j in data['jyutping_list']:
                    jp_map[j].add(char)
                    char_jp_counts[char].add(j)
    
    print(f"Reading {INPUT_CSV} to identify necessary work...")
    
    items_for_hint_gen = []
    char_counters = {}
    
    # Maps for Pinyin Proxy
    py_map = collections.defaultdict(set)
    char_py_counts = collections.defaultdict(set)
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        row_index = 0
        for row in reader:
            if len(row) < 7: continue
            row_index += 1 # 1-based index to match corrections
            
            char_raw = row[0].strip()
            pinyin = row[3].strip()
            
            # Apply correction if exists
            pinyin = apply_pinyin_override(row_index, pinyin, pinyin_corrections)
            
            if char_raw == '字头' or (char_raw == '吖' and '释文' in row[6]):
                continue
            
            sense_map, base_char = parse_complex_variants(char_raw)
            
            if pinyin:
                py_map[pinyin].add(base_char)
                char_py_counts[base_char].add(pinyin)

            raw_def = row[6]
            senses = parse_xhzd_definitions(raw_def)
            
            for i, sense in enumerate(senses, 1):
                if char_raw not in char_counters: char_counters[char_raw] = 0
                char_counters[char_raw] += 1
                
                clean_id_base = char_raw.replace('（', '_').replace('）', '')
                card_id = f"{clean_id_base}_{char_counters[char_raw]}"
                
                definition = sense['def'].strip().rstrip('；').strip()
                definition = re.sub(r'另见.*?(?:。|；|$)', '', definition).strip()
                
                hints = sense['hints']
                # Extract bracketed words from definition as extra hints for context
                bracket_hints = re.findall(r'［(.*?)］', definition)
                all_hints_list = hints + bracket_hints
                hint_str = " / ".join(all_hints_list) if all_hints_list else ""

                # 1. Identify missing hints
                if not hints and card_id not in hint_cache:
                    items_for_hint_gen.append({
                        'id': card_id,
                        'char': char_raw,
                        'def': definition
                    })

    if USE_LLM:
        if items_for_hint_gen:
            run_missing_hint_generation(items_for_hint_gen, HINT_CACHE_FILE, hint_cache)
            hint_cache = load_json_cache(HINT_CACHE_FILE)
        
    print(f"Generating final cards...")
    
    char_counters = {}
    generated_rows = []
    
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        row_index = 0
        for row in reader:
            if len(row) < 7: continue
            row_index += 1
            
            char_raw = row[0].strip()
            pinyin = row[3].strip()
            
            # Apply correction if exists
            pinyin = apply_pinyin_override(row_index, pinyin, pinyin_corrections)
            
            level = row[4].strip()
            raw_def = row[6]
            
            if char_raw == '字头' or (char_raw == '吖' and '释文' in raw_def):
                continue

            sense_map, base_char = parse_complex_variants(char_raw)
            senses = parse_xhzd_definitions(raw_def)
            freq_info = freq_map.get(base_char, {'rank': '', 'raw': '', 'percentile': ''})
            
            for i, sense in enumerate(senses, 1):
                if char_raw not in char_counters: char_counters[char_raw] = 0
                char_counters[char_raw] += 1
                
                clean_id_base = char_raw.replace('（', '_').replace('）', '')
                card_id = f"{clean_id_base}_{char_counters[char_raw]}"
                
                definition = sense['def'].strip().rstrip('；').strip()
                definition = re.sub(r'另见.*?(?:。|；|$)', '', definition).strip()
                
                # Enrich definition with Jyutping info for context words
                definition = enrich_definition_with_jyutping(definition)
                
                hints = sense['hints']
                # Enrich hints as well
                hints = [enrich_definition_with_jyutping(h) for h in hints]
                
                # Extract bracketed words from definition as extra hints for context
                bracket_hints = re.findall(r'［(.*?)］', definition)
                all_hints_list = hints + bracket_hints
                
                hint_str = ""
                if all_hints_list:
                    cleaned_hints = [re.sub(r'另见.*', '', h).strip() for h in all_hints_list]
                    cleaned_hints = [h for h in cleaned_hints if h]
                    hint_str = " / ".join(cleaned_hints)
                elif card_id in hint_cache:
                    val = hint_cache[card_id]
                    if isinstance(val, str):
                        hint_str = val
                    elif isinstance(val, dict):
                        hint_str = val.get('hint') or val.get('hints') or ""
                
                if hint_str:
                    hint_str = re.sub(r'另见.*', '', hint_str).strip()
                
                applicable_variants = sense_map.get(0, []) + sense_map.get(i, [])
                if applicable_variants:
                    seen = set()
                    unique_vars = [x for x in applicable_variants if not (x in seen or seen.add(x))]
                    char_display = f"{base_char}（{'、'.join(unique_vars)}）"
                    all_variants_for_mc = [base_char] + unique_vars
                else:
                    char_display = base_char
                    all_variants_for_mc = [base_char]

                cedict_eng = get_best_cedict_english(base_char, definition, pinyin, cedict_data, cedict_reverse)
                final_eng = trans_cache.get(card_id, cedict_eng)
                if isinstance(final_eng, dict): 
                     final_eng = final_eng.get('eng') or final_eng.get('english') or ""
                if not isinstance(final_eng, str):
                    final_eng = ""
                
                # Get Jyutping
                jyutping = ""
                if card_id in jp_cache:
                    jyutping = jp_cache[card_id]
                else:
                    jyutping, _ = get_cantonese(char_display, hint_str)
                    if not jyutping:
                        for v in all_variants_for_mc:
                            if v in unihan_data and 'jyutping' in unihan_data[v]:
                                jyutping = unihan_data[v]['jyutping']
                                break
                
                # Safety: stick with only 1 reading for now
                if jyutping and isinstance(jyutping, str):
                    jyutping = jyutping.split(',')[0].strip()
                
                eng_text_for_mc = final_eng
                eng_keywords = set()
                if eng_text_for_mc:
                    eng_keywords = {w.lower() for w in re.split(r'[^\w\s]+', eng_text_for_mc) if len(w) > 2}
                
                mc = get_middle_chinese(all_variants_for_mc, pinyin, eng_keywords, baxter_data)
                mc_source = "BS" if mc else ""
                
                unihan_mc_vals = []
                unihan_hangul = []
                
                for v in all_variants_for_mc:
                    if v in unihan_data:
                        if 'mc' in unihan_data[v]:
                            unihan_mc_vals.append(unihan_data[v]['mc'])
                        if 'hangul' in unihan_data[v]:
                            unihan_hangul.append(unihan_data[v]['hangul'])
                            
                if not mc and unihan_mc_vals:
                    mc = " / ".join(sorted(list(set(unihan_mc_vals))))
                    mc_source = "Unihan"
                
                if mc and mc_source:
                    mc = f"{mc} ({mc_source})"
                    
                hangul = " / ".join(sorted(list(set(unihan_hangul))))
                
                # TTS Proxies
                py_tts = get_tts_proxy(pinyin, py_map, char_py_counts, freq_map)
                jp_tts = get_tts_proxy(jyutping, jp_map, char_jp_counts, freq_map)

                generated_rows.append({
                    'ID': card_id,
                    'Character': char_display,
                    'Hint': hint_str,
                    'Definition': definition,
                    'Pinyin': pinyin, 
                    'Jyutping': jyutping,
                    'py_pronunciation': py_tts,
                    'jp_pronunciation': jp_tts,
                    'MiddleChinese': mc,
                    'Hangul': hangul,
                    'English': final_eng,
                    'Frequency': freq_info['rank'],
                    'Level': level
                })

    if USE_LLM and jp_cache:
        save_json_cache(jp_cache, JP_CACHE_FILE)

    print(f"Saving {len(generated_rows)} cards to {OUTPUT_CSV}...")
    headers = [
        'ID', 'Character', 'Hint', 'Definition', 'Pinyin', 
        'Jyutping', 'py_pronunciation', 'jp_pronunciation',
        'MiddleChinese', 'Hangul', 'English', 
        'Frequency', 'Level'
    ]
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(generated_rows)
        
    print("Complete.")

if __name__ == '__main__':
    main()
