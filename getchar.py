import pickle
import json

# f = open('char_detail.json')
# f = open('wiki.json')

# data = json.load(f)
# pickle.dump(data, open('wiki.pkl', 'wb'))

# word_table = dict()

# for i in range(len(data)):
#     word = data[i]['word']
#     if word in word_table:
#         word_table[word].append(i)
#     else:
#         word_table[word] = [i]


# pickle.dump(word_table, open('word_table.pkl', 'wb'))

data = pickle.load(open('wiki.pkl', 'rb'))
word_table = pickle.load(open('word_table.pkl', 'rb'))

def get_sounds(input_char):
    for i in word_table[input_char]:
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


get_sounds('天')

# print(json.dumps(data[274], indent=2, ensure_ascii=False))


# html_content='''



# '''

# tml_file_path = 'character_details.html'

# with open(html_file_path, 'w') as file:
#     file.write(html_content)



