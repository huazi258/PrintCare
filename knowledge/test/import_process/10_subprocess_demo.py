import os
import subprocess
from pathlib import Path

# 问题原因
# 核心冲突：text=True 和 check=True 同时使用导致两个问题：
# 编码错误：text=True 在 Windows 上使用 GBK 编码读取输出，但 MinerU 输出 UTF-8 编码的中文
# 异常中断：check=True 在命令失败时立即抛出异常，无法看到错误详情
os.environ['MINERU_MODEL_SOURCE'] = 'modelscope'
os.environ['MODELSCOPE_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

print("✅ 环境变量已配置")
print(f"   MINERU_MODEL_SOURCE = {os.environ.get('MINERU_MODEL_SOURCE')}")
print(f"   MODELSCOPE_OFFLINE = {os.environ.get('MODELSCOPE_OFFLINE')}")
print(f"   HF_HOME = {os.environ.get('HF_HOME')}")
print()
# 方案1：使用 encoding='utf-8' 替代 text=True（推荐）
result = subprocess.run(
    [
        "mineru",
        "-p",
        r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\hak180产品安全手册.pdf",
        "-o",
        r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir2",
        "--backend",
        "pipeline"
    ],
    capture_output=True,  # 捕获输出
    encoding='utf-8',  # 指定 UTF-8 编码（Windows 下避免 GBK 问题）
    errors='replace',  # 遇到无法解码的字符用  替换
    check=False  # 不自动抛异常，手动检查
)

# 检查执行结果
if result.returncode == 0:
    print("✅ MinerU 执行成功！")
    print(result.stdout)
else:
    print(f"❌ MinerU 执行失败，返回码: {result.returncode}")
    print("标准输出:", result.stdout)
    print("错误输出:", result.stderr)

# ===============================================================

# === 关键：加载环境变量（模拟 PyCharm 运行 pdf_to_md.py 时的环境）===
# 方法1：直接读取 .env 文件并设置环境变量
# env_file = Path(__file__).parent.parent.parent / '.env'
# if env_file.exists():
#     with open(env_file, 'r', encoding='utf-8') as f:
#         for line in f:
#             line = line.strip()
#             if line and not line.startswith('#') and '=' in line:
#                 key, value = line.split('=', 1)
#                 os.environ[key.strip()] = value.strip()

# 方法2：显式设置关键环境变量（确保 MinerU 使用 ModelScope 离线模式）
# os.environ['MINERU_MODEL_SOURCE'] = 'modelscope'
# os.environ['MODELSCOPE_OFFLINE'] = '1'
# os.environ['HF_HUB_OFFLINE'] = '1'
# os.environ['TRANSFORMERS_OFFLINE'] = '1'
#
# print("✅ 环境变量已配置")
# print(f"   MINERU_MODEL_SOURCE = {os.environ.get('MINERU_MODEL_SOURCE')}")
# print(f"   MODELSCOPE_OFFLINE = {os.environ.get('MODELSCOPE_OFFLINE')}")
# print(f"   HF_HOME = {os.environ.get('HF_HOME')}")
# print()
# proc = subprocess.Popen(
#     # args=["mineru", "-p",
#     #  r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\hak180产品安全手册.pdf",
#     #  "-o",
#     #  r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir2",
#     #  "--backend",
#     #  "pipeline"],
#     args=["mineru", "-p", r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\hak180产品安全手册.pdf",
#           "-o", r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir5", "--backend", "pipeline"],
#     stdout=subprocess.PIPE,    # 捕获标准输出
#     stderr=subprocess.STDOUT,  # 合并错误到标准输出
#     text=True,
#     encoding="utf-8",
#     errors="replace",          # 遇到乱码时替换
#     bufsize=1                  # 行缓冲，实时输出
# )
#
# for line in proc.stdout:
#     print(line.rstrip())
#
# return_code = proc.wait()
# print(return_code)
