import csv

# Read the corrections from correct.txt into a dictionary
corrections = {}
with open('correct.txt', mode='r', encoding='utf-8') as file:
    reader = csv.DictReader(file, delimiter='\t')
    for row in reader:
        corrections[row['zi']] = row['py']

# Read the content of xhzd.csv, correct the pinyin, and write to a new file
with open('xhzd.csv', mode='r', encoding='utf-8') as infile, open('xhzd_corrected.csv', mode='w', encoding='utf-8', newline='') as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)
    
    for row in reader:
        zi = row[0]
        if zi in corrections:
            row[3] = corrections[zi]  # Correct the pinyin in the 4th column
        writer.writerow(row)

print("Corrections have been applied and saved to 'xhzd_corrected.csv'.")

