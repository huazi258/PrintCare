from langchain_text_splitters import RecursiveCharacterTextSplitter

text = "苹果的颜色是红色的[SEP]香蕉的颜色是黄色的[SEP]橘子的颜色是橙色的"

splitter = RecursiveCharacterTextSplitter(
    separators=["[SEP]"],
    chunk_size=1,
    chunk_overlap=0,
    keep_separator=False
    #keep_separator=True
)
print(splitter.split_text(text))

#['苹果的颜色是红色的', '香蕉的颜色是黄色的', '橘子的颜色是橙色的']
#['苹果的颜色是红色的', '[SEP]香蕉的颜色是黄色的', '[SEP]橘子的颜色是橙色的']