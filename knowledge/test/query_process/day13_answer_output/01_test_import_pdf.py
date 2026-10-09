"""
 测试导入 API
"""
import requests
import os

# 上传文件
# 字段名    文件名      文件对象(完整路径+文件名)
files = [('file', ('H3C LA2608室内无线网关 用户手册-6W100-整本手册.pdf',
                   open(
                       'E:\\我的课件[Python]\\08_掌柜智库2\\2.资料\\pdf文档\\doc\\H3C LA2608室内无线网关 用户手册-6W100-整本手册.pdf',
                       'rb'), 'application/pdf'))]
response = requests.post('http://localhost:8000/upload', files=files)
print(response.json())
# {"message": "文件上传成功", "task_id": "xxx-xxx-xxx"}

# 查询状态
task_id = response.json()['task_id']
status = requests.get(f'http://localhost:8000/status/{task_id}')
print(status.json())
# {"status": "processing", "done_list": ["上传文件"], "running_list": ["检查文件"]}


# {'message': '文件上传成功', 'task_id': '431e8627'}
# {'status': 'processing', 'done_list': ['上传文件', 'entry'], 'running_list': ['PDF转Markdown'], 'durations': {'entry': 0.0}}
