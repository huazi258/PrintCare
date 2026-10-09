from pathlib import Path

from uvicorn.config import is_dir

path = Path(r'D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto\万用表RS-12的使用.md')

name = path.name # '万用表RS-12的使用.md'
stem = path.stem # '万用表RS-12的使用'
suffix = path.suffix # '.md'
parentPath = path.parent # 'D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto'
print(name)
print(stem)
print(suffix)
print(parentPath)

if  path.is_file():
    print('是文件')
elif path.is_dir():
    print('是目录')
else:
    print(' Neither a file nor a directory')
    
if path.exists():
    print('存在')
else:
    print('不存在')

