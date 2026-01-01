import csv
import json
import requests
import re
import os
import threading
import concurrent.futures
import time

# Configuration
INPUT_CSV = 'hanzi_cards_complete.csv'
HINT_CACHE_FILE = 'hint_cache.json'
OPENROUTER_API_KEY = "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"
BATCH_SIZE = 20
MAX_WORKERS = 10

def load_json_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_json_cache(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
                # Extract base char if complex variant "台（臺）" -> "台"
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

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"{INPUT_CSV} not found.")
        return

    # 1. Load Data
    rows = []
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    cache = load_json_cache(HINT_CACHE_FILE)
    
    # 2. Identify Missing Hints
    missing_items = []
    for row in rows:
        if not row.get('Hint', '').strip():
            # If in cache, use it directly (don't need to generate)
            if row['ID'] in cache:
                val = cache[row['ID']]
                if isinstance(val, str) and val.strip():
                    row['Hint'] = val
                    continue
                elif isinstance(val, dict):
                     hint_str = val.get('hint') or val.get('hints') or ""
                     if isinstance(hint_str, str) and hint_str.strip():
                         row['Hint'] = hint_str
                         continue
            
            # Still missing? Queue for generation
            if not row.get('Hint', '').strip():
                missing_items.append({
                    'id': row['ID'],
                    'char': row['Character'],
                    'def': row['Definition']
                })

    print(f"Found {len(missing_items)} items still missing hints.")
    
    if not missing_items:
        print("No items to generate.")
    else:
        # 3. Generate
        batches = [missing_items[i:i + BATCH_SIZE] for i in range(0, len(missing_items), BATCH_SIZE)]
        total_batches = len(batches)
        
        lock = threading.Lock()
        
        def process_batch(batch, idx):
            results = generate_hints_batch(batch, idx+1)
            if results:
                with lock:
                    cache.update(results)
                    save_json_cache(cache, HINT_CACHE_FILE)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for i, batch in enumerate(batches):
                futures.append(executor.submit(process_batch, batch, i))
                time.sleep(0.1)
            concurrent.futures.wait(futures)
            
        # 4. Apply new hints to rows
        # Reload cache to be sure
        cache = load_json_cache(HINT_CACHE_FILE)
        filled_count = 0
        for row in rows:
            if not row.get('Hint', '').strip() and row['ID'] in cache:
                val = cache[row['ID']]
                hint_str = ""
                if isinstance(val, str):
                    hint_str = val
                elif isinstance(val, dict):
                    hint_str = val.get('hint') or val.get('hints') or ""
                
                if hint_str:
                    row['Hint'] = hint_str
                    filled_count += 1
        
        print(f"Filled {filled_count} newly generated hints.")

    # 5. Save CSV
    with open(INPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print("Done updating CSV.")

if __name__ == '__main__':
    main()
