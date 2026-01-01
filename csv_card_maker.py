import csv
import re
import sys
import collections
import unicodedata

# Try imports for advanced features
try:
    import pycantonese
    from hanziconv import HanziConv
    HAS_NLP = True
except ImportError:
    HAS_NLP = False
    print("Warning: 'pycantonese' or 'hanziconv' not found. Contextual Jyutping generation will be disabled.")
    print("To enable, run: pip install pycantonese hanziconv")

# Configuration
INPUT_CSV = 'xhzd_corrected.csv'
CEDICT_FILE = 'cedict_ts.u8'
FREQ_FILE = 'CharFreq-Combined.csv'
OUTPUT_CSV = 'hanzi_cards.csv'

CIRCLE_MAP = {c: i+1 for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩")}

STOPWORDS = {
    'a', 'an', 'the', 'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'but', 'and', 'or', 'as', 'if',
    'so', 'than', 'that', 'this', 'these', 'those', 'from', 'up', 'down', 'out', 'into', 'over', 'under',
    'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now'
}

# ---------------------------------------------------------
# 1. Load Frequency Data
# ---------------------------------------------------------
print("Loading Frequency Data...")
char_freq = {}
try:
    with open(FREQ_FILE, 'r', encoding='utf-8') as f:
        freq_reader = csv.reader(f)
        for row in freq_reader:
            if len(row) >= 2:
                char_freq[row[1]] = row[0]
except FileNotFoundError:
    print("Warning: Frequency file not found.")

# ---------------------------------------------------------
# 2. CEDICT Parsing
# ---------------------------------------------------------
print("Parsing CEDICT...")
cedict_data = {} 
cedict_reverse = collections.defaultdict(set) 

def extract_keywords(text):
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.lower().split()
    return {w for w in words if w not in STOPWORDS and len(w) > 1}

def parse_cedict():
    try:
        with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or line.strip() == '':
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
                    
                    keywords = extract_keywords(english_raw)
                    cedict_reverse[simp].update(keywords)
                    
        print(f"Loaded {len(cedict_data)} CEDICT entries.")
    except FileNotFoundError:
        print("Warning: CEDICT file not found.")

parse_cedict()

# ---------------------------------------------------------
# 3. Logic & Helpers
# ---------------------------------------------------------

def pinyin_marks_to_numbers(pinyin_str):
    return unicodedata.normalize('NFKD', pinyin_str).encode('ASCII', 'ignore').decode('ASCII').lower()

def score_definition(target_eng_def, chinese_def_tokens):
    score = 0
    target_keywords = extract_keywords(target_eng_def)
    
    for cn_token in chinese_def_tokens:
        if cn_token in cedict_reverse:
            potential_eng_keywords = cedict_reverse[cn_token]
            overlap = target_keywords.intersection(potential_eng_keywords)
            score += len(overlap)
    
    if '姓' in chinese_def_tokens and 'surname' in target_keywords:
        score += 10
    
    for token in chinese_def_tokens:
        if len(token) == 1 and '\u4e00' <= token <= '\u9fff': 
             if token in target_eng_def: 
                 score += 5
                 
    return score

def get_best_english(char, xhzd_def, xhzd_pinyin):
    if char not in cedict_data:
        return ""
    
    candidates = cedict_data[char]
    xhzd_loose = pinyin_marks_to_numbers(xhzd_pinyin)
    
    pinyin_filtered = []
    for cand in candidates:
        cand_loose = ''.join([c for c in cand['pinyin'] if not c.isdigit()])
        if xhzd_loose == cand_loose:
             pinyin_filtered.append(cand)
             
    if not pinyin_filtered:
        current_candidates = candidates
    else:
        current_candidates = pinyin_filtered
        
    if len(current_candidates) == 1:
        return current_candidates[0]['eng']
        
    cn_tokens = re.findall(r'[\u4e00-\u9fff]+', xhzd_def)
    
    scored_candidates = []
    for cand in current_candidates:
        score = score_definition(cand['eng'], cn_tokens)
        scored_candidates.append((score, cand['eng']))
        
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score = scored_candidates[0][0]
    
    if best_score == 0:
        unique_defs = sorted(list(set([c['eng'] for c in current_candidates])))
        return "<br>".join(unique_defs)
    
    winners = [c[1] for c in scored_candidates if c[0] == best_score]
    return "<br>".join(sorted(list(set(winners))))

def get_cantonese_from_hint(target_char_full, hint_str):
    if not HAS_NLP or not hint_str:
        return None
    
    primary_char = re.sub(r'（.*?）', '', target_char_full).strip()
    
    word = hint_str.replace('～', primary_char)
    try:
        word_trad = HanziConv.toTraditional(word)
        target_char_trad = HanziConv.toTraditional(primary_char)
        jyutping_list = pycantonese.characters_to_jyutping(word_trad)
        
        candidates = []
        for char, jp in jyutping_list:
            if char == target_char_trad and jp:
                candidates.append(jp)
        
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return None

def clean_definition_text(text):
    text = re.sub(r'另见.*?(?:。|；|$)', '', text)
    return text.strip().rstrip('；').strip()

def parse_complex_variants(char_raw):
    match = re.search(r'^(.*?)（(.*?)）$', char_raw)
    if not match:
        return {}, char_raw
    
    base_char = match.group(1)
    variant_str = match.group(2)
    sense_map = collections.defaultdict(list)
    
    parts = variant_str.split('、')
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

def parse_definitions(def_text):
    def_text = re.sub(r'([❶-❿])', r'\n\1', def_text)
    lines = def_text.split('\n')
    parsed_defs = []
    current_def = ""
    current_hints = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for start marker
        is_new_def = re.match(r'^[❶-❿0-9]\.?', line)
        
        # If it's a compound line AND we already have a definition, skip it to avoid cluttering hints.
        # BUT if we have NO definitions yet, keep it so the card isn't empty.
        if (line.startswith('［') or line.startswith('[')) and (len(parsed_defs) > 0 or current_def):
             continue
        
        if is_new_def or (len(parsed_defs) == 0 and not current_def):
            if current_def:
                parsed_defs.append({'def': current_def, 'hints': current_hints})
                current_def = ""
                current_hints = []
            
            clean_line = re.sub(r'^[❶-❿0-9]\.?\s*', '', line)
            
            parts = clean_line.split('：', 1)
            is_valid_split = False
            if len(parts) == 2:
                left_part = parts[0]
                if left_part.count('（') == left_part.count('）'):
                    is_valid_split = True
            
            if is_valid_split:
                current_def = parts[0].replace('"', '').strip()
                current_hints = [h.strip() for h in parts[1].replace('。', '').split('|')]
            else:
                current_def = clean_line.replace('"', '').strip()
        else:
             current_def += " " + line

    if current_def:
        parsed_defs.append({'def': current_def, 'hints': current_hints})
        
    return parsed_defs

# ---------------------------------------------------------
# 4. Main Processing
# ---------------------------------------------------------
print(f"Processing {INPUT_CSV} to {OUTPUT_CSV}...")

with open(INPUT_CSV, newline='', encoding='utf-8') as csv_in, \
     open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csv_out:
    
    reader = csv.reader(csv_in)
    writer = csv.writer(csv_out)
    writer.writerow(['ID', 'Character', 'Hint', 'Definition', 'Pinyin', 'Jyutping', 'English', 'Frequency', 'Level'])
    
    count = 0
    char_counters = {}

    for row in reader:
        if len(row) < 7: continue
            
        char_raw = row[0].strip()
        pinyin = row[3].strip()
        level = row[4].strip()
        raw_def = row[6]
        
        if char_raw == '字头' or (char_raw == '吖' and '释文' in raw_def):
            continue
        
        sense_map, base_char = parse_complex_variants(char_raw)
        freq = char_freq.get(base_char, "")
        senses = parse_definitions(raw_def)
        
        fallback_jp = ""
        if HAS_NLP:
            try:
                 trad_char = HanziConv.toTraditional(base_char)
                 jp_list = pycantonese.characters_to_jyutping(trad_char)
                 if jp_list and jp_list[0][1]:
                     fallback_jp = jp_list[0][1]
            except:
                pass

        for i, sense in enumerate(senses, 1):
            if char_raw not in char_counters:
                char_counters[char_raw] = 0
            char_counters[char_raw] += 1
            current_id_num = char_counters[char_raw]

            definition = clean_definition_text(sense['def'])
            hints = sense['hints']
            english_def = get_best_english(base_char, definition, pinyin)
            hint_display = " / ".join(hints) if hints else ""
            
            applicable = sense_map.get(0, []) + sense_map.get(i, [])
            if applicable:
                seen = set()
                unique_app = [x for x in applicable if not (x in seen or seen.add(x))]
                char_display = f"{base_char}（{'、'.join(unique_app)}）"
            else:
                char_display = base_char
            
            best_jp = fallback_jp
            if hints:
                context_jp = get_cantonese_from_hint(char_display, hints[0])
                if context_jp:
                    best_jp = context_jp
            
            clean_id_base = char_raw.replace('（', '_').replace('）', '')
            card_id = f"{clean_id_base}_{current_id_num}"
            
            writer.writerow([
                card_id,
                char_display,
                hint_display,
                definition,
                pinyin,
                best_jp,
                english_def,
                freq,
                level
            ])
            count += 1

print(f"Done! Generated {count} cards in {OUTPUT_CSV}.")
