import os

from minio import Minio

# 初始化客户端
client = Minio(
    "192.168.6.150:9000",
    os.environ["MINIO_ACCESS_KEY"],
    os.environ["MINIO_SECRET"],
    secure=False  # 是否使用https
)

if not client.bucket_exists("mybucket"):
    client.make_bucket("mybucket")

# 上传文件
client.fput_object(
    bucket_name="mybucket",
    object_name="images/p1.jpg",  # Object名称含路径
    file_path="d:/temp/p1.jpg",  # 上传的本地文件路径
    content_type="image/jpeg"  # MIME类型
)

# 获取文件路径
url = f"http://192.168.6.150:9000/mybucket/images/p1.jpg"
print(url)
