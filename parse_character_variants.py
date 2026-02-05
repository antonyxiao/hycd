#!/usr/bin/env python3
"""
Parse character variants from hanzi_cards_complete.csv

This script parses the Character column to extract variant information and creates
new columns for simplified characters, traditional characters, and various types
of variant characters.

Parsing rules:
- Main pattern: `主字（variants）` where variants can contain:
  - Characters without prefix = traditional (繁体字)
  - *char = standard variant (《通用规范汉字表》异体字)
  - **char = external variant (表外异体字)
  - △char = has separate dictionary entry
  - ①②③... or ①—⑤ = definition-specific
  - 、separates multiple variants
"""

import csv
import json
import re
from pathlib import Path


def parse_definition_range(range_str):
    """
    Parse definition number ranges like '①②③' or '①—⑤' or '⑦—⑬'
    Returns a list of definition numbers.
    """
    # Mapping of circled numbers to integers
    circled_nums = {
        '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
        '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
        '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
        '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20
    }

    if not range_str:
        return []

    # Check for range pattern like ①—⑤ or ⑦—⑬
    range_match = re.match(r'([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])—([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])', range_str)
    if range_match:
        start = circled_nums.get(range_match.group(1), 0)
        end = circled_nums.get(range_match.group(2), 0)
        return list(range(start, end + 1))

    # Otherwise, extract individual circled numbers
    nums = []
    for char in range_str:
        if char in circled_nums:
            nums.append(circled_nums[char])
    return nums


def parse_single_variant(variant_str):
    """
    Parse a single variant entry (one character with its markers).
    Returns a dict with:
    - character: the actual character
    - is_traditional: True if no * prefix (regular traditional)
    - is_standard_variant: True if single * prefix
    - is_external_variant: True if double ** prefix
    - has_separate_entry: True if △ marker present
    - definition_nums: list of definition numbers this applies to
    """
    result = {
        'character': None,
        'is_traditional': False,
        'is_standard_variant': False,
        'is_external_variant': False,
        'has_separate_entry': False,
        'definition_nums': []
    }

    if not variant_str:
        return result

    # Strip whitespace
    variant_str = variant_str.strip()

    # Extract definition numbers at the beginning
    # Pattern: circled numbers or ranges like ①②③ or ①—⑤
    def_pattern = r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳—]+)'
    def_match = re.match(def_pattern, variant_str)
    if def_match:
        def_str = def_match.group(1)
        result['definition_nums'] = parse_definition_range(def_str)
        variant_str = variant_str[len(def_str):]

    # Check for separate entry marker △
    if '△' in variant_str:
        result['has_separate_entry'] = True
        variant_str = variant_str.replace('△', '')

    # Check for variant markers (order matters: ** before *)
    if variant_str.startswith('**'):
        result['is_external_variant'] = True
        variant_str = variant_str[2:]
    elif variant_str.startswith('*'):
        result['is_standard_variant'] = True
        variant_str = variant_str[1:]
    else:
        # No asterisk means traditional character
        result['is_traditional'] = True

    # The remaining string should be the character
    result['character'] = variant_str.strip() if variant_str.strip() else None

    return result


def parse_character_column(char_str):
    """
    Parse the Character column which has format like:
    - 锕（錒）
    - 庵（*菴）
    - 挨（**捱）
    - 鞍（△*鞌）
    - 飙（飆、**飇、**飈）
    - 干（⑦—⑬△乾、⑦—⑬*乹）

    Returns a dict with parsed information.
    """
    result = {
        'simplified': None,
        'traditional': [],
        'variant_standard': [],
        'variant_external': [],
        'has_separate_entry': [],
        'definition_specific': {}  # Maps definition numbers to variants
    }

    if not char_str:
        return result

    # Check if there are parentheses containing variants
    # Pattern: main_char（variant_content）
    paren_match = re.match(r'^([^（）]+)（([^）]*)）$', char_str)

    if paren_match:
        main_char = paren_match.group(1).strip()
        variant_content = paren_match.group(2).strip()
        result['simplified'] = main_char

        # Split variants by 、
        variants = variant_content.split('、')

        for variant in variants:
            parsed = parse_single_variant(variant)

            if parsed['character']:
                # Track definition-specific variants
                if parsed['definition_nums']:
                    for def_num in parsed['definition_nums']:
                        def_key = str(def_num)
                        if def_key not in result['definition_specific']:
                            result['definition_specific'][def_key] = []

                        variant_info = {
                            'character': parsed['character'],
                            'type': 'traditional' if parsed['is_traditional'] else
                                   'standard_variant' if parsed['is_standard_variant'] else
                                   'external_variant',
                            'has_separate_entry': parsed['has_separate_entry']
                        }
                        result['definition_specific'][def_key].append(variant_info)

                # Also add to the appropriate general category
                if parsed['has_separate_entry']:
                    if parsed['character'] not in result['has_separate_entry']:
                        result['has_separate_entry'].append(parsed['character'])

                if parsed['is_traditional']:
                    if parsed['character'] not in result['traditional']:
                        result['traditional'].append(parsed['character'])
                elif parsed['is_standard_variant']:
                    if parsed['character'] not in result['variant_standard']:
                        result['variant_standard'].append(parsed['character'])
                elif parsed['is_external_variant']:
                    if parsed['character'] not in result['variant_external']:
                        result['variant_external'].append(parsed['character'])
    else:
        # No parentheses - just the main character
        result['simplified'] = char_str.strip()

    return result


def parse_id_column(id_str):
    """
    Parse the ID column which has format like:
    - 锕_錒_1
    - 坝_③垻、壩_3
    - 干_⑦—⑬△乾、⑦—⑬*乹、⑦—⑬*亁_7

    Returns the variant info embedded in the ID.
    """
    result = {
        'definition_specific': {}
    }

    if not id_str:
        return result

    # Pattern: char_variants_num where variants may contain definition markers
    # Remove the trailing _number
    parts = id_str.rsplit('_', 1)
    if len(parts) < 2:
        return result

    # The middle part contains variant info
    main_parts = parts[0].split('_', 1)
    if len(main_parts) < 2:
        return result

    variant_str = main_parts[1]

    # Split by 、
    variants = variant_str.split('、')

    for variant in variants:
        parsed = parse_single_variant(variant)

        if parsed['character'] and parsed['definition_nums']:
            for def_num in parsed['definition_nums']:
                def_key = str(def_num)
                if def_key not in result['definition_specific']:
                    result['definition_specific'][def_key] = []

                variant_info = {
                    'character': parsed['character'],
                    'type': 'traditional' if parsed['is_traditional'] else
                           'standard_variant' if parsed['is_standard_variant'] else
                           'external_variant',
                    'has_separate_entry': parsed['has_separate_entry']
                }
                result['definition_specific'][def_key].append(variant_info)

    return result


def main():
    input_file = Path('/home/antony/hycd/hanzi_cards_complete.csv')
    output_file = Path('/home/antony/hycd/hanzi_cards_parsed.csv')

    # Read input CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Define new columns
    new_columns = [
        'Simplified',
        'Traditional',
        'Variant_Standard',
        'Variant_External',
        'Has_Separate_Entry',
        'Definition_Specific'
    ]

    # Create new fieldnames list with new columns after 'Character'
    new_fieldnames = []
    for fn in fieldnames:
        new_fieldnames.append(fn)
        if fn == 'Character':
            new_fieldnames.extend(new_columns)

    # Process each row
    processed_rows = []
    for row in rows:
        char_value = row.get('Character', '')
        id_value = row.get('ID', '')

        parsed = parse_character_column(char_value)
        id_parsed = parse_id_column(id_value)

        # Merge definition_specific from ID column (it's more complete)
        if id_parsed['definition_specific']:
            for def_key, variants in id_parsed['definition_specific'].items():
                if def_key not in parsed['definition_specific']:
                    parsed['definition_specific'][def_key] = []
                # Add variants from ID column that aren't already present
                existing_chars = {v['character'] for v in parsed['definition_specific'][def_key]}
                for v in variants:
                    if v['character'] not in existing_chars:
                        parsed['definition_specific'][def_key].append(v)

        # Create new row with additional columns
        new_row = {}
        for fn in fieldnames:
            new_row[fn] = row.get(fn, '')

        # Add parsed values
        new_row['Simplified'] = parsed['simplified'] or ''
        new_row['Traditional'] = '|'.join(parsed['traditional']) if parsed['traditional'] else ''
        new_row['Variant_Standard'] = '|'.join(parsed['variant_standard']) if parsed['variant_standard'] else ''
        new_row['Variant_External'] = '|'.join(parsed['variant_external']) if parsed['variant_external'] else ''
        new_row['Has_Separate_Entry'] = '|'.join(parsed['has_separate_entry']) if parsed['has_separate_entry'] else ''
        new_row['Definition_Specific'] = json.dumps(parsed['definition_specific'], ensure_ascii=False) if parsed['definition_specific'] else ''

        processed_rows.append(new_row)

    # Write output CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(processed_rows)

    print(f"Processed {len(processed_rows)} rows")
    print(f"Output written to {output_file}")

    # Print some statistics
    stats = {
        'total': len(processed_rows),
        'with_traditional': sum(1 for r in processed_rows if r['Traditional']),
        'with_standard_variant': sum(1 for r in processed_rows if r['Variant_Standard']),
        'with_external_variant': sum(1 for r in processed_rows if r['Variant_External']),
        'with_separate_entry': sum(1 for r in processed_rows if r['Has_Separate_Entry']),
        'with_definition_specific': sum(1 for r in processed_rows if r['Definition_Specific'])
    }

    print("\nStatistics:")
    print(f"  Total rows: {stats['total']}")
    print(f"  With traditional variants: {stats['with_traditional']}")
    print(f"  With standard variants (*): {stats['with_standard_variant']}")
    print(f"  With external variants (**): {stats['with_external_variant']}")
    print(f"  With separate entry (△): {stats['with_separate_entry']}")
    print(f"  With definition-specific variants: {stats['with_definition_specific']}")


if __name__ == '__main__':
    main()
