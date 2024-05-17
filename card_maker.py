import genanki
import json
import pycantonese
import chinese_converter
import csv

# Create a new Anki deck with a unique ID and a name
my_deck = genanki.Deck(
  deck_id=123456790,
  name="hanzi",
)

answer_side = """{{FrontSide}}<hr id='answer'>
    {{Pinyin}}<br>
    {{Jyutping}}<br><br>
    {{Definition}}<br><br>
    {{Stroke}} {{Level}} {{Page}}
    """
# Define a model (template) for the cards
# A model specifies the fields and card format
my_model = genanki.Model(
  model_id=123456790,
  name="Basic Model",
  fields=[
    {"name": "Character"},
    {"name": "Pinyin"},
    {"name": "Jyutping"},
    {"name": "Definition"},
    {"name": "Stroke"},
    {"name": "Level"},
    {"name": "Page"},
    #{"name": "image"},
  ],templates=[
    {
      "name": "Card 1",
      "qfmt": "<span class='char'>{{Character}}</span>", # Question format
      "afmt": answer_side, # Answer format
      #"afmt": "{{FrontSide}}<hr id='answer'>{{Answer}}<br>{{image}}", # Answer format
    },
  ],
  css="""
  .card {
   font-family: arial;
   font-size: 20px;
   text-align: center;
   color: black;
   background-color: white;
  }

  .char {
    font-size: 200%;
  }
  """
)


with open('xhzd.csv', newline='', encoding='utf-8') as csvfile:

    spamreader = csv.reader(csvfile, delimiter=',')

    for row in spamreader:
        
        # Generate jyutping for the word, filtering out None values
        jyutping_chunks = [
            chunk[1] for chunk in pycantonese.characters_to_jyutping(chinese_converter.to_traditional(row[0][0]))
            if chunk[1] is not None
        ]
        jyutping = ' '.join(jyutping_chunks)

        # Add a space after each number in the Jyutping string
        jyutping = ''.join(char + ' ' if char.isdigit() else char for char in jyutping).strip()



        # Add a card to the deck
        note = genanki.Note(
            model=my_model,
            fields=[row[0], row[3], jyutping, row[6], row[5], row[4], row[1] + "页"] #fields=["What is the capital of France?", "Paris",'<img src="image.gif">'],) # add note to deck my_deck.add_note(note)
        )
        
        my_deck.add_note(note)

# create package for deck
my_package = genanki.Package(my_deck)

# Optionally, add more cards here in a similar manner
#my_package.media_files = ['image.gif']

# Save the deck to a file
my_package.write_to_file('hanzi.apkg')

print("Deck has been created.")
