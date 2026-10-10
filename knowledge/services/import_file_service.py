from datetime import datetime
import logging, os.path, shutil, uuid
from typing import Tuple

from fastapi import UploadFile
from knowledge.core.devices import DEFAULT_DEVICE_ID, resolve_supported_device
from knowledge.core.paths import get_local_base_dir
from knowledge.processor.import_process.exceptions import FileProcessingError
from knowledge.processor.import_process.main_graph import kb_import_graph_app
from knowledge.utils.client.storage_clients import StorageClients
from knowledge.utils.task_util import add_running_task, add_done_task, update_task_status

logger = logging.getLogger(__name__)


class ImportFileService:

    def _get_date_dir(self):
        # "%Y%m%d"  年  月  日
        # %Y 四位    %y  两位
        return os.path.join(get_local_base_dir(), datetime.now().strftime("%Y%m%d"))

    def process_upload_file(self, file, device_id: str = DEFAULT_DEVICE_ID) -> Tuple[str, str, str]:
        """
            处理上传文件：
                1.生成task_id,构建归档目录
                2.标记upload_file节点为运行中
                3.保存文件到本地磁盘
                4.同步上传到MinIO
                5.标记upload_file节点完成
                6.返回task_id,file_dir,import_file_path

        :param file: 上文件
        :return: Tuple[str,str,str]
        """
        # The service is also an entry point for non-HTTP callers, so validate
        # before its first side effect as well.
        resolve_supported_device(device_id)

        # 1.生成task_id,构建归档目录
        date_dir = self._get_date_dir()
        task_id = str(uuid.uuid4().hex[:8])
        file_dir = os.path.join(date_dir, task_id)  # 将上传文件存放到指定临时目录

        # 2.标记upload_file节点为运行中
        add_running_task(task_id, "upload_file")

        # 3.保存文件到本地磁盘
        import_file_path = self._save_upload_file_to_local(file, file_dir)

        # 4.同步上传到MinIO
        self._save_upload_file_to_minio(import_file_path, file.filename)

        # 5.标记upload_file节点完成
        add_done_task(task_id, "upload_file")

        # 6.返回task_id,file_dir,import_file_path
        return task_id, file_dir, import_file_path

    def _save_upload_file_to_local(self, file: UploadFile, file_dir: str) -> str:
        """保存文件到本地磁盘临时目录"""
        # 1.创建文件的保存目录
        os.makedirs(file_dir, exist_ok=True)

        # 2.构建导入文件的路径
        import_file_dir = os.path.join(file_dir, file.filename)

        # 3.写入
        try:
            # "wb"：以二进制写入模式打开文件。
            with open(import_file_dir, "wb") as f:
                # 不同的操作系统以及不同python版本都可以分批次的写入，缓冲区大小： 1M
                shutil.copyfileobj(file.file, f)
        except IOError as e:
            logger.info(f"{file.filename}写入临时目录失败，原因：{str(e)}")
            raise FileProcessingError(message=f"{file.filename}写入临时目录失败，原因：{str(e)}")

        # 返回导入的文件完整路径
        return import_file_dir

    def _save_upload_file_to_minio(self, import_file_path, filename: str):
        """上传导入文件到MinIO服务器"""
        # 1.获取Minio客户端
        try:
            minio_client = StorageClients.get_minio_client()
        except ConnectionError as e:
            logger.error(f"获取Minio客户端失败，原因：{str(e)}")
            return

        # 2.获取Minio相关信息
        bucket_name = os.getenv("MINIO_BUCKET_NAME")
        object_name = f"origin_file/{datetime.now().strftime('%Y%m%d')}/{filename}"

        # 3.上传文件
        try:
            minio_client.fput_object(bucket_name, object_name, import_file_path)
        except Exception as e:
            logger.error(f"{filename}上传到Minio失败,原因：{str(e)}")

    def run_import_graph(self, task_id: str, file_dir: str, import_file_path: str,
                         device_id: str = DEFAULT_DEVICE_ID):
        """运行导入  Langgraph 流水线（后台异步执行任务）"""
        try:
            device = resolve_supported_device(device_id)
            update_task_status(task_id, "processing")
            global_graph_state = {
                "task_id": task_id,
                "file_dir": file_dir,
                "import_file_path": import_file_path,
                "device_id": device.device_id,
                "device_model": device.device_model,
            }
            for event in kb_import_graph_app.stream(global_graph_state):
                for node_name, state in event.items():
                    print(f"[{task_id}] Completed Node: {node_name}")

            update_task_status(task_id, "completed")
        except Exception as e:
            update_task_status(task_id, "failed")
            print(f"任务{task_id}执行失败，原因：{str(e)}")
