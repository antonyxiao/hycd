import csv

INPUT_CSV = 'hanzi_cards_complete.csv'
MISSING_JP_FILE = 'missing_jyutping.txt'

def main():
    missing_jp_count = 0
    missing_hint_count = 0
    total_count = 0
    
    missing_jp_entries = []

    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_count += 1
                
                # Check Jyutping
                if not row['Jyutping'].strip():
                    missing_jp_count += 1
                    missing_jp_entries.append(f"{row['ID']}: {row['Character']}")
                
                # Check Hint
                if not row['Hint'].strip():
                    missing_hint_count += 1

        with open(MISSING_JP_FILE, 'w', encoding='utf-8') as f:
            for entry in missing_jp_entries:
                f.write(entry + '\n')

        print(f"Total Cards: {total_count}")
        print(f"Missing Jyutping: {missing_jp_count}")
        print(f"Missing Hints: {missing_hint_count}")
        print(f"List of characters without Jyutping saved to {MISSING_JP_FILE}")

    except FileNotFoundError:
        print(f"Error: {INPUT_CSV} not found.")

if __name__ == '__main__':
    main()

