import requests
import json
import csv

def invoke(action, params):
    request = {'action': action, 'version': 6, 'params': params}
    response = requests.post('http://localhost:8765', json=request)
    return json.loads(response.text)

def load_jp_table(filepath):
    jp_dict = {}
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            jp_dict[row[0].strip()] = row[1].strip()
    return jp_dict

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

jp_table = load_jp_table('jp_table.csv')

for card in cards_info:
    fields = card['fields']
    jyutping = fields['Jyutping'].lower().strip()
    
    if jyutping in jp_table:
        jpchar_append = jp_table[jyutping]

        update_card(card['note'], 'JPChar', jpchar_append)

