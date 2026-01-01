import csv
import re
import pickle
import genanki
import pycantonese
from hanziconv import HanziConv

# Configuration
DECK_ID = 20231229
DECK_NAME = "Hanzi Split Definitions"
MODEL_ID = 20231230
MODEL_NAME = "Hanzi Split Model"
INPUT_CSV = 'xhzd_corrected.csv'
CEDICT_FILE = 'cedict_ts.u8'
OUTPUT_PKG = 'hanzi_split.apkg'

# ---------------------------------------------------------
# 1. CEDICT Parsing (for English Reference)
# ---------------------------------------------------------
print("Parsing CEDICT...")
cedict_data = {}

def parse_cedict():
    with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or line.strip() == '':
                continue
            # Format: Traditional Simplified [pin yin] /English/Definitions/
            # We map Simplified -> English String
            parts = line.rstrip('/').split('/')
            if len(parts) <= 1:
                continue
            
            english = "; ".join(parts[1:])
            
            # Extract char section
            header = parts[0]
            # header: Trad Simp [Pinyin]
            match = re.match(r'(\S+)\s+(\S+)\s+\[(.*)\]', header)
            if match:
                trad, simp, pinyin = match.groups()
                # Store by simplified char
                if simp not in cedict_data:
                    cedict_data[simp] = []
                cedict_data[simp].append(english)

try:
    parse_cedict()
    print(f"Loaded {len(cedict_data)} CEDICT entries.")
except FileNotFoundError:
    print("Warning: CEDICT file not found. English definitions will be empty.")

# ---------------------------------------------------------
# 2. Helper Functions
# ---------------------------------------------------------

def get_cantonese_from_hint(target_char, hint_str):
    """
    Uses pycantonese to get jyutping for the target char within a context word.
    hint_str: e.g. "～色" or "真相大～"
    target_char: e.g. "白"
    """
    if not hint_str:
        return None
    
    # Reconstruct the word
    word = hint_str.replace('～', target_char)
    
    try:
        # Convert to Traditional for pycantonese (it works best with Trad)
        word_trad = HanziConv.toTraditional(word)
        target_char_trad = HanziConv.toTraditional(target_char)
        
        # Segment and transcribe
        # pycantonese might treat the whole string as a sentence or word
        # We assume the hint is a word/phrase
        jyutping_list = pycantonese.characters_to_jyutping(word_trad)
        # jyutping_list is list of (char, jyutping) tuples
        
        # Find the target char index
        # Note: 'word' might have the char multiple times, we assume the '～' position corresponds
        # But '～' is gone. We need to match indices.
        
        # Simple strategy: iterate and find the one that matches target_char
        # If multiple, it's ambiguous, but usually hints are short compounds.
        
        candidates = []
        for char, jp in jyutping_list:
            # Check against Traditional char
            if char == target_char_trad and jp:
                candidates.append(jp)
        
        if candidates:
            return candidates[0] # Return the first match
            
    except Exception:
        pass
    
    return None

def parse_definitions(def_text):
    """
    Splits the definition text into a list of dictionaries:
    [{'def': '...', 'hints': '...'}, ...]
    """
    # 1. Split by newlines that start with a number or just newlines
    # xhzd uses ❶, ❷...
    # We also want to exclude [Compound] entries which usually start with ［
    
    lines = def_text.split('\n')
    parsed_defs = []
    
    current_def = ""
    current_hints = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if it's a compound definition (Start with ［)
        if line.startswith('［') or line.startswith('['):
            continue # Skip compounds for the character card
            
        # Check if it's a new numbered definition
        # Matches ❶, ❷, or just starts with number?
        # xhzd_corrected: ❶...
        is_new_def = re.match(r'^[❶-❿0-9]\.?', line)
        
        if is_new_def or (len(parsed_defs) == 0 and not current_def):
            # Save previous if exists
            if current_def:
                parsed_defs.append({'def': current_def, 'hints': current_hints})
                current_def = ""
                current_hints = []
            
            # Start new
            # Remove the number marker
            clean_line = re.sub(r'^[❶-❿0-9]\.?\s*', '', line)
            
            # Extract Hints (after colon ：)
            # Format: Definition：Hint1|Hint2
            if '：' in clean_line:
                def_part, hint_part = clean_line.split('：', 1)
                current_def = def_part.replace('"', '').strip() # cleanup quotes
                # Hints are separated by |
                current_hints = [h.strip() for h in hint_part.replace('。', '').split('|')]
            else:
                current_def = clean_line.replace('"', '').strip()
        else:
            # Continuation of previous definition?
            # Or just append to current
             current_def += " " + line

    # Append last
    if current_def:
        parsed_defs.append({'def': current_def, 'hints': current_hints})
        
    return parsed_defs

# ---------------------------------------------------------
# 3. Anki Deck Setup
# ---------------------------------------------------------

my_model = genanki.Model(
  MODEL_ID,
  MODEL_NAME,
  fields=[
    {'name': 'CardId'}, # Unique ID to prevent dupes if needed
    {'name': 'Character'},
    {'name': 'Hint'},
    {'name': 'Definition'},
    {'name': 'Pinyin'},
    {'name': 'Jyutping'},
    {'name': 'English'},
  ],
  templates=[
    {
      'name': 'Definition Recall',
      'qfmt': """
      <div class="char">{{Character}}</div>
      <div class="hint">Hint: {{Hint}}</div>
      """,
      'afmt': """
      {{FrontSide}}
      <hr id="answer">
      <div class="def">Definition: {{Definition}}</div>
      <div class="pron">
        Pinyin: {{Pinyin}}<br>
        Jyutping: {{Jyutping}}
      </div>
      <br>
      <div class="eng">{{English}}</div>
      """,
    },
  ],
  css="""
  .card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }
  .char { font-size: 48px; font-weight: bold; color: #b33; }
  .hint { font-style: italic; color: #666; font-size: 18px; margin-bottom: 10px; }
  .def { font-weight: bold; margin: 10px 0; }
  .pron { color: #007; }
  .eng { font-size: 14px; color: #555; text-align: left; margin-top: 20px; border-top: 1px solid #ccc; padding-top: 5px; }
  """
)

my_deck = genanki.Deck(DECK_ID, DECK_NAME)

# ---------------------------------------------------------
# 4. Main Processing
# ---------------------------------------------------------
print("Processing CSV...")

with open(INPUT_CSV, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    
    count = 0
    for row in reader:
        # Expected row format (from xhzd.csv/corrected):
        # [0]Character, [1]Page, [2]Pos, [3]Pinyin, [4]Level, [5]Strokes, [6]Definition
        
        if len(row) < 7:
            continue
            
        char = row[0].strip()
        pinyin = row[3].strip()
        raw_def = row[6]
        
        # Skip header if present
        if char == '字头' or char == '吖': # '吖' is actually data, strict check
            if '释文' in raw_def:
                continue

        # Parse definitions
        senses = parse_definitions(raw_def)
        
        # Get English (join all entries for this char)
        english_def = "<br>".join(cedict_data.get(char, []))
        
        # Fallback Jyutping (character based only)
        # We need this if no hints work
        fallback_jp = ""
        try:
             # Convert to trad for pycantonese
             trad_char = HanziConv.toTraditional(char)
             jp_list = pycantonese.characters_to_jyutping(trad_char)
             if jp_list and jp_list[0][1]:
                 fallback_jp = jp_list[0][1]
        except:
            pass

        sense_idx = 0
        for sense in senses:
            sense_idx += 1
            definition = sense['def']
            hints = sense['hints']
            
            # Format Hint String
            hint_display = " / ".join(hints) if hints else "(No hint)"
            
            # Determine Jyutping using Hint Context
            best_jp = fallback_jp
            if hints:
                # Try the first hint
                context_jp = get_cantonese_from_hint(char, hints[0])
                if context_jp:
                    best_jp = context_jp
            
            # Create Note
            # Fields: CardId, Character, Hint, Definition, Pinyin, Jyutping, English
            note = genanki.Note(
                model=my_model,
                fields=[
                    f"{char}_{pinyin}_{sense_idx}", # Unique ID
                    char,
                    hint_display,
                    definition,
                    pinyin,
                    best_jp,
                    english_def
                ]
            )
            my_deck.add_note(note)
            count += 1

print(f"Generated {count} cards.")
genanki.Package(my_deck).write_to_file(OUTPUT_PKG)
print(f"Deck saved to {OUTPUT_PKG}")
