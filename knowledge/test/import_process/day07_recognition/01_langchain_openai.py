from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

import os
from dotenv import load_dotenv
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# 1.创建 LLM客户端
llm = ChatOpenAI(
    model="qwen-flash",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    temperature=0.9,
    base_url=os.getenv("OPENAI_API_BASE"),
)

# 2. 构建消息
messages = [
    SystemMessage(content="您是商品识别专家,只输出字符串"),
    HumanMessage(content="请从以下信息中识别商品名称?R12万用表如何使用")
]

# 3. 调用并获取响应
response = llm.invoke(messages)

item_name = response.content.strip()
print(item_name)


"""
R12万用表
Disconnected from server
Exception in thread Thread-1 (tracing_control_thread_func):
Traceback (most recent call last):
  File "C:\Server\Python\Python312\Lib\threading.py", line 1052, in _bootstrap_inner
    self.run()
  File "C:\Server\Python\Python312\Lib\threading.py", line 989, in run
    self._target(*self._args, **self._kwargs)
  File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\langsmith\_internal\_background_thread.py", line 619, in tracing_control_thread_func
    ).start()
      ^^^^^^^
  File "C:\Server\Python\Python312\Lib\threading.py", line 971, in start
    _start_new_thread(self._bootstrap, ())
RuntimeError: can't create new thread at interpreter shutdown


错误分析
好消息：程序已成功输出 R12万用表，说明 API 调用已修复成功！
剩余问题：RuntimeError: can't create new thread at interpreter shutdown
原因：langsmith 库的后台追踪线程在 Python 解释器关闭时尝试创建新线程，但此时解释器已不允许创建线程。这是 langsmith 的已知问题，不影响程序功能。

方案一：禁用 LangSmith 追踪（推荐，最简单）
在脚本开头添加环境变量禁用追踪：
os.environ["LANGCHAIN_TRACING_V2"] = "false"
"""