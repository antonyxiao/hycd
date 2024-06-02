import requests
import json
import csv

def invoke(action, params):
    request = {'action': action, 'version': 6, 'params': params}
    response = requests.post('http://localhost:8765', json=request)
    return json.loads(response.text)

def load_freq_table(filepath):
    freq = {}
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            freq[row[1].strip()] = row[0].strip()
    return freq

# Update a field in a card
def update_card(card_id, field_name, field_value):
    return invoke('updateNoteFields', {
        'note': {
            'id': card_id,
            'fields': {
                field_name: field_value
            }
        }
    })


# Example: choose a specific deck
deck_name = "hanzi"  # Replace with your deck's name

# Get cards in the deck
deck_cards = invoke('findCards', {'query': f'deck:"{deck_name}"'})

# Fetch detailed information for each card
cards_info = invoke('cardsInfo', {'cards': deck_cards['result']})

char_freq_table = load_freq_table('CharFreq-Combined.csv')

for card in cards_info['result']:
    char = card['fields']['Character']['value'][0].lower().strip()
    
    if char in char_freq_table:
        freq_num = char_freq_table[char]

        print(char + freq_num)
        update_card(card['note'], 'Frequency', freq_num)
        

