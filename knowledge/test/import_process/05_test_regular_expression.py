"""
Regular Expression : 正则表达式 测试

![alt文本](图片路径)

# 示例
![万用表正面图](images/image_0.png)
![](./images/photo.jpg)

"""

import re

md_conent = "我是一个MD文档，我的内容是![万用表正面图1](images/image_0.png)这个样子的，我的内容是![万用表正面图2](images/image_1.png)这个样子的内嵌图片！"

pattern = r"!\[(.*?)\]\((.*?)\)"

matches = re.findall(pattern, md_conent)
print(matches)

image_filename = "image_0.png"
specific_pattern = r"!\[.*?\]\(.*?" + re.escape(image_filename) + r".*?\)"

matches = re.findall(specific_pattern,md_conent)
print(matches)
