from FlagEmbedding import FlagReranker

reranker = FlagReranker(
    # model_name_or_path="BAAI/bge-reranker-large",
    model_name_or_path="D:\\ai_models\\modelscope_cache\\models\\BAAI\\BAAI\\bge-reranker-large",
    device="cuda",  # GPU 加速
    use_fp16=True  # 半精度推理
)

# 计算相关性得分
pairs = [
    ["什么是万用表？", "万用表是一种测量电压、电流、电阻的仪器"],
    ["什么是万用表？", "今天天气很好"]
]
scores = reranker.compute_score(pairs)
# 输出: [0.9234, 0.0156]  高分 = 高相关
print(scores)
#[7.8984375, -9.484375]
"""
Exception ignored in: <function ResourceTracker.__del__ at 0x000002A1C07D0900>
Traceback (most recent call last):
  File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 80, in __del__
  File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 89, in _stop
  File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 102, in _stop_locked
AttributeError: '_thread.RLock' object has no attribute '_recursion_count'

错误原因
这是 multiprocess 库在程序退出时 GC（垃圾回收）调用 ResourceTracker.__del__ 的已知兼容性问题。

修改源码解决问题：

D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py
第102行在 _stop_locked 方法中，程序退出时 __del__ → _stop → _stop_locked 触发，而 Windows 的 _thread.RLock 没有 _recursion_count 方法。
修复方式：与第127行保持一致，使用 getattr 兜底：
 if getattr(self._lock, "_recursion_count", int)() > 1:
 
 ⚠️ 注意：这是直接修改第三方库源码，升级 multiprocess 后会被覆盖。如果后续升级库版本仍存在问题，建议结合之前在 ducment_split.py 中的猴子补丁方案一起使用。
"""