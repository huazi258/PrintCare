import os.path
from typing import Optional

import uvicorn

from fastapi.responses import FileResponse
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.params import Depends
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from knowledge.core.deps import get_import_file_service
from knowledge.core.devices import UnsupportedDeviceError, resolve_supported_device
from knowledge.core.paths import get_front_page_dir
from knowledge.schema.upload_schema import UploadResponse, TaskStatusResponse
from knowledge.services.import_file_service import ImportFileService
from knowledge.utils.task_util import get_task_info


# 1.创建fastapi实例
# 2.注册路由
# 3.利用uvicorn服务器启动fastapi
def create_app():
    app = FastAPI()

    # 跨域配置(允许前端跨域访问)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由注册
    register_router(app)

    # 挂载前端静态资源
    """
    取决于 import.html 中是否引用了其他静态资源（JS/CSS/图片等）：
    ✅ 如果 import.html 是纯 HTML（没有引用外部 JS/CSS）→ 不需要，只写路由就够了
    ✅ 如果 import.html 引用了 front/ 目录下的 JS/CSS 等资源 → 必须写，否则浏览器加载这些资源时会 404
    简单说：路由负责"打开页面"，mount 负责"加载页面里的 JS/CSS 等资源"。两者配合使用，页面才能正常工作。
    """
    # http://localhost:8000/front/p4.jpg
    front_page_dir = get_front_page_dir()
    if front_page_dir and os.path.exists(front_page_dir):
        app.mount("/front", StaticFiles(directory=front_page_dir))

    return app


def register_router(app):

    @app.get("/import.html")
    async def import_root():
        """返回导入界面"""
        return FileResponse(path=os.path.join(get_front_page_dir(), "import.html"))

    @app.post("/upload", response_model=UploadResponse)
    async def upload_file(backGround_tasks: BackgroundTasks,
                          importFileService: ImportFileService = Depends(get_import_file_service),
                          device_id: Optional[str] = Form(default=None),
                          file: UploadFile = File(...)):
        """Post请求处理  接收上传文件"""

        # Validate the client-supplied identifier before any file, object-store,
        # or background-task side effect.  Display names are always server-owned.
        try:
            device = resolve_supported_device(device_id)
        except UnsupportedDeviceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # 1. 上传文件 （本地 + MinIO）
        task_id, file_dir, import_file_path = importFileService.process_upload_file(file, device.device_id)

        # 2. 将耗时的图谱流程放入后台任务，异步处理
        backGround_tasks.add_task(
            importFileService.run_import_graph,
            task_id,
            file_dir,
            import_file_path,
            device.device_id,
        )

        # return {
        #     "task_id": "abc-123"
        # }
        return UploadResponse(message="文件上传成功", task_id=task_id)

    # async def 异步函数，支持高并发，不阻塞主线程
    # file: UploadFile 参数类型注解，UploadFile 是 FastAPI 提供的文件对象，包含文件名、内容等
    # = File(...) 告诉 FastAPI 这个参数来自请求体中的文件字段（... 表示必填）
    @app.get("/status/{task_id}", response_model=TaskStatusResponse)
    async def get_status(task_id: str):
        """Get 请求处理    路径参数自动注入"""
        # return {
        #     "status": "processing",
        #     "done_list": ["上传文件", "检查文件", "PDF转Markdown"],
        #     "running_list": ["文档切分"],
        #     "durations": {
        #         "检查文件": 0.01,
        #         "PDF转Markdown": 58.23,
        #         "文档切分": 2.15
        #     }
        # }
        task_info = get_task_info(task_id=task_id)
        return TaskStatusResponse(**task_info)


# 直接启动，不要debug启动，否则报错,见笔记
if __name__ == "__main__":
    uvicorn.run(app=create_app(), host="localhost", port=8000, log_level="info")
