import csv
import json
import requests
import time
import os
import re
import concurrent.futures
import threading

# --- CONFIGURATION ---
OPENROUTER_API_KEY = "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"
INPUT_FILE = 'hanzi_cards.csv'
OUTPUT_FILE = 'hanzi_cards_translated.csv'
PROGRESS_FILE = 'translation_cache.json'
BATCH_SIZE = 50 
MAX_WORKERS = 10  # Number of concurrent requests. Increase to 10-20 for more speed if API allows.

# Thread-safe cache and lock
cache = {}
cache_lock = threading.Lock()

def save_cache():
    with cache_lock:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

def call_llm_batch(batch_items):
    """
    Sends a batch to DeepSeek V3 via OpenRouter.
    """
    prompt = f"""
    Translate these Chinese dictionary entries into concise, natural English definitions.
    For each entry, provide ONE string that captures the primary meaning.
    
    Return ONLY a JSON object where keys are the 'id' and values are the English strings.
    Do NOT use newlines within the English strings.

    Entries:
    {json.dumps(batch_items, ensure_ascii=False)}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/gemini-3-flash-preview",
        "messages": [
            {"role": "system", "content": "You are a professional dictionary translator. Output only valid JSON objects. No markdown, no preamble."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=120
        )
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
        
        raw_content = response.json()['choices'][0]['message']['content']
        clean_content = re.sub(r'^```json\s*|\s*```$', '', raw_content.strip(), flags=re.MULTILINE)
        data = json.loads(clean_content, strict=False)
        
        if isinstance(data, dict):
            return data
        return {"error": "Invalid JSON format from LLM"}
            
    except Exception as e:
        return {"error": str(e)}

def worker(batch_rows, batch_num, total_batches):
    llm_input = [
        {'id': r['ID'], 'char': r['Character'], 'pinyin': r['Pinyin'], 'def': r['Definition']}
        for r in batch_rows
    ]

    print(f"Starting batch {batch_num}/{total_batches}...")
    
    retries = 2
    while retries >= 0:
        result = call_llm_batch(llm_input)
        
        if "error" not in result:
            with cache_lock:
                cache.update(result)
            save_cache()
            print(f"Completed batch {batch_num}/{total_batches}.")
            return True
        else:
            print(f"Error in batch {batch_num} (Retries left: {retries}): {result['error']}")
            retries -= 1
            time.sleep(5)
            
    return False

def main():
    global cache
    if not os.path.exists(INPUT_FILE):
        print(f"{INPUT_FILE} not found.")
        return

    # 1. Load progress
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"Loaded {len(cache)} existing translations from cache.")
        except:
            print("Warning: Could not load cache, starting fresh.")

    # 2. Read all rows
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    to_process = [r for r in rows if r['ID'] not in cache]
    total_to_translate = len(to_process)
    
    if total_to_translate == 0:
        print("All items already translated.")
    else:
        # 3. Create Batches
        batches = [to_process[i : i + BATCH_SIZE] for i in range(0, total_to_translate, BATCH_SIZE)]
        total_batches = len(batches)
        print(f"Processing {total_to_translate} cards in {total_batches} batches with {MAX_WORKERS} parallel workers...")

        # 4. Threaded Execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(worker, batches[i], i+1, total_batches) for i in range(total_batches)]
            concurrent.futures.wait(futures)

    # 5. Final Export
    print("Writing final translated CSV...")
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if row['ID'] in cache:
                val = cache[row['ID']]
                if not isinstance(val, str):
                    val = json.dumps(val, ensure_ascii=False)
                row['English'] = val
            writer.writerow(row)

    print(f"Done! Created {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
