import pickle
import json
from pprint import pprint
import mysql.connector
from mysql.connector import Error
import chinese_converter
from hanziconv import HanziConv
import genanki
import pycantonese
import csv

data = pickle.load(open('wiki.pkl', 'rb'))

def get_conn():
    try:
        # Connect to the MySQL database
        connection = mysql.connector.connect(
            host='localhost',       # Replace with your host name
            port=3306,              # Replace with your port number if different
            user='root',   # Replace with your username
            password='debang', # Replace with your password
            database='hyzd' # Replace with your database name
        )
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            #print("Connected to MySQL Server version ", db_info)
            return connection
        
    except Error as e:
        print("Error while connecting to MySQL", e)

def close_conn(connection):
    if connection.is_connected():
        connection.cursor().close()
        connection.close()
        #print("MySQL connection is closed")

def load_word_table_into_db():
    conn = get_conn()
    cursor = conn.cursor()

    data = []
    
    for key, value in word_table.items():
        for v in value:
            data.append((key, v))

    sql = "INSERT INTO char_table (ch, id) VALUES (%s, %s)"
    
    cursor.executemany(sql, data)
    conn.commit()

    close_conn(conn)
        
    #records = cursor.fetchall()

def get_id_from_char(char):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM char_table WHERE ch = %s', (char,))
    rows = cursor.fetchall()
    
    id_values = [row[0] for row in rows]
    
    close_conn(conn)

    return id_values


def get_sounds(input_char):
    for i in get_id_from_char(input_char):
        print('INDEX: ' + str(i))
        if 'sounds' in data[i]:
            sounds = data[i]['sounds']
            for s in sounds:
                if 'tags' in s:
                    if ('Mandarin' in s['tags'] and 'Pinyin' in s['tags'] and ( len(s['tags']) == 2 or 'standard' in s['tags'])) and not any(x in s['zh-pron'] for x in ['⁰', '¹', '²', '³', '⁴', '⁵']):
                        print('PY: ' + s['zh-pron'])
                    if 'Cantonese' in s['tags'] and 'Jyutping' in s['tags']:
                        print('JP: ' + s['zh-pron'])
                    if 'Middle-Chinese' in s['tags']:
                        print('MC: ' + s['zh-pron'])


def get_emin(sounds, ipa=True):
    '''
    Returns a list of unique min dong (eastern min) pronunciations
    '''
    # Extract zh-pron and ipa where tags contain Min-Dong
    zh_pron_values = [(entry.get('zh-pron', None), entry.get('ipa', None)) for entry in sounds if 'Min-Dong' in entry.get('tags', [])]
    
    # Filter out None values
    zh_pron_values = [(zh_pron, ipa) for zh_pron, ipa in zh_pron_values if zh_pron is not None or ipa is not None]

    pronunciations = []
    
    for zh_pron, ipa_pron in zh_pron_values:
        if zh_pron is not None:
            pronunciations.append(zh_pron)
        if ipa == True and ipa_pron is not None:
            pronunciations.append(ipa_pron)
    
    return list(set(pronunciations))

def get_pinyin(sounds):
    for s in sounds:
        if 'tags' in s:
            if ('Mandarin' in s['tags'] and 'Pinyin' in s['tags'] and ( len(s['tags']) == 2 or 'standard' in s['tags'])) and not any(x in s['zh-pron'] for x in ['⁰', '¹', '²', '³', '⁴', '⁵']):
                return [s['zh-pron'].lower()]

def get_jp(sounds):
    for s in sounds:
        if 'tags' in s:
            if 'Cantonese' in s['tags'] and 'Jyutping' in s['tags']:
                return [s['zh-pron'].lower().replace('¹', '1').replace('²', '2').replace('³', '3')
                       .replace('⁴', '4').replace('⁵', '5').replace('⁶', '6')]

def get_mc(sounds):
    for s in sounds:
        if 'tags' in s:
            if 'Middle-Chinese' in s['tags']:
                return [s['zh-pron'].lower()]


def get_prons(ch):
    ch = chinese_converter.to_traditional(ch)
    char_prons = dict()
    i = 0 
    for index in get_id_from_char(ch):


        if 'sounds' in data[index]:
        
            sounds = data[index]['sounds']
            
            emin = get_emin(sounds, ipa=False)
            py = get_pinyin(sounds)
            jp = get_jp(sounds)
            mc = get_mc(sounds)
            
            # None if exact pronunciation already exists
            char_prons[i] = {
                'md': emin if emin not in [entry.get('md') for entry in char_prons.values()] else None,
                'py': py if py not in [entry.get('py') for entry in char_prons.values()] else None,
                'jp': jp if jp not in [entry.get('jp') for entry in char_prons.values()] else None,
                'mc': mc if mc not in [entry.get('mc') for entry in char_prons.values()] else None
            }
            
            i += 1
    
    filtered_char_prons = dict()
    
    i = 0
    
    for key, entry_list in char_prons.items():
        non_none_values = [(k, v) for k, v in entry_list.items() if v]
        if non_none_values:
            temp_dict = {'md': None, 'py': None, 'jp': None, 'mc': None}
            for k, v in non_none_values:
                 temp_dict[k] = v
            filtered_char_prons[i] = temp_dict
            i += 1
        
    return filtered_char_prons

def romanize(str):
    lo_romanization = []
    for char in str:
        lo_romanization.append(get_prons(char))

    return lo_romanization

def get_pron_with_py(ch, py):
    prons = get_prons(ch)
    for key, item in prons.items():
        if item['py']:
            if item['py'][0] in py:
                return item

    return {'jp': None, 'mc': None, 'md': None, 'py': None}
    

#A parser for the CC-Cedict. Convert the Chinese-English dictionary into a list of python dictionaries with "traditional","simplified", "pinyin", and "english" keys.

#Make sure that the cedict_ts.u8 file is in the same folder as this file, and that the name matches the file name on line 13.

#Before starting, open the CEDICT text file and delete the copyright information at the top. Otherwise the program will try to parse it and you will get an error message.

#Characters that are commonly used as surnames have two entries in CC-CEDICT. This program will remove the surname entry if there is another entry for the character. If you want to include the surnames, simply delete lines 59 and 60.

#This code was written by Franki Allegra in February 2020.

#open CEDICT file

with open('cedict_ts.u8') as file:
    text = file.read()
    lines = text.split('\n')
    dict_lines = list(lines)

#define functions

    def parse_line(line):
        parsed = {}
        if line == '':
            dict_lines.remove(line)
            return 0
        line = line.rstrip('/')
        line = line.split('/')
        if len(line) <= 1:
            return 0
        english = line[1]
        char_and_pinyin = line[0].split('[')
        characters = char_and_pinyin[0]
        characters = characters.split()
        traditional = characters[0]
        simplified = characters[1]
        pinyin = char_and_pinyin[1]
        pinyin = pinyin.rstrip()
        pinyin = pinyin.rstrip("]")
        parsed['traditional'] = traditional
        parsed['simplified'] = simplified
        parsed['pinyin'] = pinyin
        parsed['english'] = english
        list_of_dicts.append(parsed)

    def remove_surnames():
        for x in range(len(list_of_dicts)-1, -1, -1):
            if "surname " in list_of_dicts[x]['english']:
                if list_of_dicts[x]['traditional'] == list_of_dicts[x+1]['traditional']:
                    list_of_dicts.pop(x)
            
    def main():

        #make each line into a dictionary
        print("Parsing dictionary . . .")
        for line in dict_lines:
                parse_line(line)
        
        #remove entries for surnames from the data (optional):

        #print("Removing Surnames . . .")
        #remove_surnames()

        return list_of_dicts


        #If you want to save to a database as JSON objects, create a class Word in the Models file of your Django project:

        # print("Saving to database (this may take a few minutes) . . .")
        # for one_dict in list_of_dicts:
        #     new_word = Word(traditional = one_dict["traditional"], simplified = one_dict["simplified"], english = one_dict["english"], pinyin = one_dict["pinyin"], hsk = one_dict["hsk"])
        #     new_word.save()
        print('Done!')

list_of_dicts = []
parsed_dict = main()
print('done parsing CEDICT')


jp_and_mc_and_english = {}

with open('xhzd_corrected.csv', newline='', encoding='utf-8') as csvfile:

    spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')

    for row in spamreader:

        jyutping = ''
        mc = ''
        cur_char = ''
        english = ''
        
        if row[0][0] == ' ':
            cur_char = row[0][1]
        else:
            cur_char = row[0][0]
        
        pron = get_pron_with_py(HanziConv.toTraditional(cur_char), row[3])
        
        if not pron or 'jp' not in pron:
            # Generate jyutping for the word, filtering out None values
            jyutping_chunks = [
                chunk[1] for chunk in pycantonese.characters_to_jyutping(HanziConv.toTraditional(cur_char))
                if chunk[1] is not None
            ]
            jyutping1 = ' '.join(jyutping_chunks)
            jyutping = jyutping1
        elif pron['jp']:
            jyutping = pron['jp'][0]
        else:
            # Generate jyutping for the word, filtering out None values
            jyutping_chunks = [
                chunk[1] for chunk in pycantonese.characters_to_jyutping(HanziConv.toTraditional(cur_char))
                if chunk[1] is not None
            ]
            jyutping1 = ' '.join(jyutping_chunks)
            jyutping = jyutping1
    
        if pron['mc']:
            mc = pron['mc'][0]

        for entry in parsed_dict:
            if cur_char == entry['simplified']:
                english = entry['english']

        jp_and_mc_and_english[cur_char] = {'jp': jyutping,'mc': mc, 'en': english}

        if not jyutping:
            print(cur_char + ': ' + row[3])

# Store data (serialize)
with open('jp_mc_en.pkl', 'wb') as handle:
    pickle.dump(jp_and_mc_and_english, handle, protocol=pickle.HIGHEST_PROTOCOL)

print('done storing as pickle')

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
    {{MiddleChinese}}<br><br>
    {{Definition}}<br><br>
    {{English}}<br><br>
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
    {"name": "MiddleChinese"},
    {"name": "Definition"},
    {"name": "English"},
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

    i = 0
    
    for row in spamreader:

        cur_char = ''
        
        if row[0][0] == ' ':
            cur_char = row[0][1]
        else:
            cur_char = row[0][0]

        prons = jp_and_mc_and_english[cur_char]

        jyutping = prons['jp']
        mc = prons['mc']
        english = prons['en']
        
        # Add a card to the deck
        note = genanki.Note(
            model=my_model,
            fields=[row[0], row[3], jyutping, mc, row[6], english, row[5], row[4], row[1] + "页"] #fields=["What is the capital of France?", "Paris",'<img src="image.gif">'],) # add note to deck my_deck.add_note(note)
        )
        
        my_deck.add_note(note)

        if i % 1000 == 0:
            print(i)
    
        i += 1
    


# create package for deck
my_package = genanki.Package(my_deck)

# Optionally, add more cards here in a similar manner
#my_package.media_files = ['image.gif']

# Save the deck to a file
my_package.write_to_file('hanzi.apkg')

print("Deck has been created.")

