import ToJyutping

words = [
    "生辰", "出生", # sang1
    "生芽", "生根", # sang1
    "生活", "生物", # sang1
    "生火", "生炉子", # ?
    "生肉", "生水", "夹生饭", # saang1
    "生瓜", # saang1
    "生人", "生字", # saang1
    "生手", # saang1
    "生皮", "生药", # saang1
    "学生", "师生", # saang1
    "老生", "小生" # saang1
]

print(f"{'Word':<10} | {'ToJyutping Result'}")
print("-" * 40)

for word in words:
    try:
        res = ToJyutping.get_jyutping_list(word)
        print(f"{word:<10} | {res}")
    except Exception as e:
        print(f"{word:<10} | Error: {e}")
