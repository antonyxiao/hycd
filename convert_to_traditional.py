#!/usr/bin/env python3
"""
Convert Hint and Definition columns to Traditional Chinese using OpenCC.
Uses s2t (Simplified to Traditional) conversion with phrase-based disambiguation.
"""

import csv
from pathlib import Path
from opencc import OpenCC

def main():
    input_file = Path('/home/antony/hycd/hanzi_cards_parsed.csv')
    output_file = Path('/home/antony/hycd/hanzi_cards_traditional.csv')

    # Initialize OpenCC with s2t (simplified to traditional)
    cc = OpenCC('s2t')

    # Read input CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)

    # Define new columns to add after existing ones
    new_columns = ['Hint_Traditional', 'Definition_Traditional']

    # Insert new columns after their source columns
    new_fieldnames = []
    for fn in fieldnames:
        new_fieldnames.append(fn)
        if fn == 'Hint':
            new_fieldnames.append('Hint_Traditional')
        elif fn == 'Definition':
            new_fieldnames.append('Definition_Traditional')

    # Process each row
    processed_rows = []
    total = len(rows)

    for i, row in enumerate(rows):
        if (i + 1) % 1000 == 0:
            print(f"Processing row {i + 1}/{total}...")

        # Create new row with all existing fields
        new_row = {fn: row.get(fn, '') for fn in fieldnames}

        # Convert Hint and Definition to Traditional
        hint = row.get('Hint', '')
        definition = row.get('Definition', '')

        new_row['Hint_Traditional'] = cc.convert(hint) if hint else ''
        new_row['Definition_Traditional'] = cc.convert(definition) if definition else ''

        processed_rows.append(new_row)

    # Write output CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(processed_rows)

    print(f"\nProcessed {len(processed_rows)} rows")
    print(f"Output written to {output_file}")

    # Show some examples
    print("\n=== Sample conversions ===")
    for row in processed_rows[:5]:
        if row['Hint'] != row['Hint_Traditional']:
            print(f"Hint: {row['Hint']}")
            print(f"  ->  {row['Hint_Traditional']}")
        if row['Definition'] != row['Definition_Traditional']:
            print(f"Def:  {row['Definition'][:50]}...")
            print(f"  ->  {row['Definition_Traditional'][:50]}...")
        print()


if __name__ == '__main__':
    main()
