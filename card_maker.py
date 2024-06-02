import genanki
import json
import pycantonese
import csv

with open('xhzd.csv', newline='') as csvfile:

    spamreader = csv.reader(csvfile, delimiter=',')

    i = 0

    for row in spamreader:
        i += 1
        print(row[0])
        

# Create a new Anki deck with a unique ID and a name
my_deck = genanki.Deck(
  deck_id=123456789,
  name="idoms",
)

# Define a model (template) for the cards
# A model specifies the fields and card format
my_model = genanki.Model(
  model_id=123456789,
  name="Basic Model",
  fields=[
    {"name": "Question"},
    {"name": "Answer"},
    #{"name": "image"},
  ],
  templates=[
    {
      "name": "Card 1",
      "qfmt": "{{Question}}", # Question format
      "afmt": "{{FrontSide}}<hr id='answer'>{{Answer}}", # Answer format
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
  """,
)

f = open('idiom.json',)
data = json.load(f)

for entry in data:
    # Add a card to the deck
    note = genanki.Note(
      model=my_model,
      fields=[]
      #fields=["What is the capital of France?", "Paris",'<img src="image.gif">'],
    )

    # add note to deck
    my_deck.add_note(note)

# create package for deck
my_package = genanki.Package(my_deck)

# Optionally, add more cards here in a similar manner
#my_package.media_files = ['image.gif']

# Save the deck to a file
my_package.write_to_file('idoms.apkg')

print("Deck has been created.")
