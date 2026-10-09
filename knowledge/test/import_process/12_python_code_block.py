import re

lines = [
    "# 第一章",  # ✓ 匹配
    "## 1.1 概述",  # ✓ 匹配
    "  ### 缩进标题",  # ✓ 匹配（允许前导空格）
    "正文内容",  # ✗ 不匹配
    "```代码```",
    "#标签",  # ✗ 不匹配（# 后需要空格）
    "####### 七级",  # ✗ 不匹配（最多6级）
]
heading_re = re.compile(r"^\s*#{1,6}\s+.+")

in_fence = False  # 是否在代码块内     fence 围栏

for line in lines:
    if line.strip().startswith("```") or line.strip().startswith("~~~"):
        in_fence = not in_fence
        print(f"{line}代码围栏")
        continue

    is_heading = (not in_fence) and heading_re.match(line)
    print(f"{line} {'✓ 匹配' if is_heading else '✗ 不匹配'}")
