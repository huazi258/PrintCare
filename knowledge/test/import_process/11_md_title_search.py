import re

heading_re = re.compile(r"^\s*#{1,6}\s+.+")

lines = [
    "# 第一章",  # ✓ 匹配
    "## 1.1 概述",  # ✓ 匹配
    "  ### 缩进标题",  # ✓ 匹配（允许前导空格）
    "正文内容",  # ✗ 不匹配
    "#标签",  # ✗ 不匹配（# 后需要空格）
    "####### 七级",  # ✗ 不匹配（最多6级）
]


for line in lines:
    if heading_re.match(line):
        print(f"{line} ✓ 匹配")
# 第一章 ✓ 匹配
## 1.1 概述 ✓ 匹配
  ### 缩进标题 ✓ 匹配