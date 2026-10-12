import asyncio
import os.path
import uuid

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from starlette.background import BackgroundTasks

from starlette.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.responses import JSONResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

from knowledge.core.deps import get_diagnosis_service, get_query_service
from knowledge.core.devices import UnsupportedDeviceError, resolve_supported_device
from knowledge.core.paths import get_front_page_dir
from knowledge.schema.diagnosis_schema import (
    DiagnosisContinueRequest,
    DiagnosisEndRequest,
    DiagnosisFeedbackRequest,
    DiagnosisStartRequest,
)
from knowledge.schema.query_schema import QueryRequest, QueryTaskStatusResponse
from knowledge.services.diagnosis_service import DiagnosisExecutionError, DiagnosisService
from knowledge.services.query_service import QueryService
from knowledge.utils.sse_util import create_sse_queue, sse_generator
from knowledge.utils.diagnosis_session_util import (
    DiagnosisSessionConflictError,
    DiagnosisSessionNotFoundError,
    DiagnosisSessionStateError,
    DiagnosisSessionStorageError,
)
from knowledge.utils.task_util import get_task_info, get_task_owner, get_task_result, task_exists


_VISITOR_COOKIE = "printcare_visitor_id"
_VISITOR_HEADER = "X-Visitor-ID"


def _visitor_id(request: Request, *, allow_create: bool) -> tuple[str, bool]:
    """Resolve the anonymous browser ID from header, cookie, or SSE query."""
    value = (
        request.headers.get(_VISITOR_HEADER)
        or request.cookies.get(_VISITOR_COOKIE)
        or request.query_params.get("visitor_id")
    )
    if isinstance(value, str) and value.strip():
        return value.strip(), False
    if allow_create:
        return str(uuid.uuid4()), True
    raise HTTPException(status_code=422, detail="缺少匿名访客标识")


def _visitor_response(
    payload: dict, visitor_id: str, created: bool, *, status_code: int = 200
) -> JSONResponse:
    response = JSONResponse(content=jsonable_encoder(payload), status_code=status_code)
    if created:
        response.set_cookie(
            _VISITOR_COOKIE,
            visitor_id,
            httponly=True,
            samesite="lax",
        )
    return response


def _diagnosis_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DiagnosisSessionNotFoundError):
        return HTTPException(status_code=404, detail="诊断会话不存在或不属于当前访客")
    if isinstance(exc, (DiagnosisSessionConflictError, DiagnosisSessionStateError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (DiagnosisSessionStorageError, DiagnosisExecutionError)):
        return HTTPException(status_code=503, detail="诊断服务暂时不可用，请稍后重试")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="诊断服务发生未预期错误")


def _require_task_visitor(task_id: str, request: Request) -> None:
    owner = get_task_owner(task_id)
    owner_visitor = owner.get("visitor_id")
    if not owner_visitor:
        return
    visitor_id, _ = _visitor_id(request, allow_create=False)
    if visitor_id != owner_visitor:
        # Do not disclose whether another anonymous visitor owns this task.
        raise HTTPException(status_code=404, detail="查询任务不存在或已失效")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(title="查询服务器", description="知识库查询服务")

    # 解决跨域问题
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源
        allow_credentials=True,  # 允许携带请求头
        allow_methods=["*"],  # 允许所有方法
        allow_headers=["*"],  # 允许所有头部
    )

    # 注册路由
    register_routers(app)

    front_page_dir = get_front_page_dir()
    if front_page_dir and os.path.exists(front_page_dir):
        app.mount("/front", StaticFiles(directory=front_page_dir))


    return app


def register_routers(app: FastAPI):
    @app.get("/chat.html")
    async def chat_page():
        return FileResponse(os.path.join(get_front_page_dir(), "chat.html"))

    @app.post("/query")
    async def query(request: QueryRequest,
                    http_request: Request,
                    background_task: BackgroundTasks,
                    service: QueryService = Depends(get_query_service),
                    diagnosis_service: DiagnosisService = Depends(get_diagnosis_service)):
        # 设备必须在创建任务前由服务端校验。显示名称不来自客户端。
        try:
            device = resolve_supported_device(request.device_id)
        except UnsupportedDeviceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if request.mode == "diagnosis":
            visitor_id, created_visitor = _visitor_id(http_request, allow_create=True)
            try:
                if request.diagnosis_id is None:
                    session, _ = diagnosis_service.start_session(
                        visitor_id,
                        DiagnosisStartRequest(
                            device_id=device.device_id,
                            original_problem=request.original_problem or "",
                        ),
                        request.request_id or "",
                    )
                    inference_request_id = f"start:{request.request_id}"
                else:
                    if request.resume_unresolved:
                        session = diagnosis_service.repository.resume_unresolved(
                            request.diagnosis_id,
                            visitor_id,
                            request.request_id or "",
                            request.expected_revision or 0,
                        )
                        inference_request_id = f"resume:{request.request_id}"
                    else:
                        session, _ = diagnosis_service.submit_answers(
                            visitor_id,
                            DiagnosisContinueRequest(
                                diagnosis_id=request.diagnosis_id,
                                answers=request.answers or [],
                                request_id=request.request_id or "",
                                expected_revision=request.expected_revision or 0,
                            ),
                        )
                        inference_request_id = f"continue:{request.request_id}"
                expected_revision = session["revision"]
                task_id = service.generate_task_id(visitor_id=visitor_id, mode="diagnosis")
            except Exception as exc:
                error = _diagnosis_http_error(exc)
                return _visitor_response(
                    {"detail": error.detail},
                    visitor_id,
                    created_visitor,
                    status_code=error.status_code,
                )

            task_kwargs = {
                "diagnosis_id": session["diagnosis_id"],
                "visitor_id": visitor_id,
                "expected_revision": expected_revision,
                "inference_request_id": inference_request_id,
                "task_id": task_id,
                "is_stream": request.is_stream,
            }
            if request.is_stream:
                create_sse_queue(task_id)
                background_task.add_task(diagnosis_service.run_background_task, **task_kwargs)
                return _visitor_response(
                    {
                        "message": "诊断流程已启动，请通过 SSE 获取已持久化结果",
                        "task_id": task_id,
                        "diagnosis_id": session["diagnosis_id"],
                        "revision": expected_revision,
                    },
                    visitor_id,
                    created_visitor,
                )

            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, lambda: diagnosis_service.run_task(**task_kwargs)
                )
            except Exception as exc:
                error = _diagnosis_http_error(exc)
                return _visitor_response(
                    {"detail": error.detail},
                    visitor_id,
                    created_visitor,
                    status_code=error.status_code,
                )
            response_payload = diagnosis_service.session_payload(result.session)
            response_payload.update({"task_id": task_id, "idempotent": result.idempotent})
            if result.running:
                response_payload["processing"] = True
                response_payload["active_task_id"] = result.active_task_id
            return _visitor_response(response_payload, visitor_id, created_visitor)

        visitor_id, created_visitor = _visitor_id(http_request, allow_create=True)

        # 1.获取session_id
        session_id = request.session_id or service.generate_session_id()

        # 2.获取任务Id
        task_id = service.generate_task_id(visitor_id=visitor_id, mode="qa")

        # 3.开启流式
        if request.is_stream:
            # 3.1 必须在返回响应前创建队列，否则前端请求/stream 时 队列不存在
            create_sse_queue(task_id)

            # 3.2 后台运行Graph
            background_task.add_task(
                service.run_query_graph,
                session_id,
                task_id,
                request.query,
                True,
                device.device_id,
                request.mode,
                visitor_id=visitor_id,
            )

            # 3.3 返回响应
            return _visitor_response(
                {"message": "查询流程已启动，请稍候...", "task_id": task_id, "session_id": session_id},
                visitor_id,
                created_visitor,
            )

        # 4.非流式
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: service.run_query_graph(
                session_id,
                task_id,
                request.query,
                False,
                device.device_id,
                request.mode,
                visitor_id=visitor_id,
            ),
        )

        # 5.获取答案
        answer = service.get_answer(task_id)

        # 6.返回答案
        return _visitor_response(
            {"message": "处理完成", "session_id": session_id, "answer": answer, "task_id": task_id},
            visitor_id,
            created_visitor,
        )

    @app.get("/status/{task_id}", response_model=QueryTaskStatusResponse)
    async def get_status(task_id: str, request: Request):
        """返回当前进程内查询任务的进度和已有结果。"""
        if not task_exists(task_id):
            raise HTTPException(status_code=404, detail="查询任务不存在或已失效")
        _require_task_visitor(task_id, request)

        task_info = get_task_info(task_id)
        image_urls = get_task_result(task_id, "image_urls", [])
        if not isinstance(image_urls, list):
            image_urls = []

        return {
            **task_info,
            "answer": get_task_result(task_id, "answer", ""),
            "error": get_task_result(task_id, "error", None),
            "image_urls": image_urls,
            "diagnosis": get_task_result(task_id, "diagnosis", None),
        }

    @app.get("/history/{session_id}")
    async def get_history(
        session_id: str,
        http_request: Request,
        limit: int = 50,
        service: QueryService = Depends(get_query_service),
    ):
        visitor_id, _ = _visitor_id(http_request, allow_create=False)
        try:
            history_items = service.get_history(session_id, visitor_id, limit)
            if not history_items:
                raise HTTPException(status_code=404, detail="会话历史不存在或不属于当前访客")
            return {"session_id": session_id, "items": history_items}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="获取历史记录失败") from exc

    @app.delete("/history/{session_id}")
    async def clear_chat_history(
        session_id: str,
        http_request: Request,
        service: QueryService = Depends(get_query_service),
    ):
        visitor_id, _ = _visitor_id(http_request, allow_create=False)
        count = service.clear_history(session_id, visitor_id)
        if count <= 0:
            raise HTTPException(status_code=404, detail="会话历史不存在或不属于当前访客")
        return {"message": "历史记录清除成功", "deleted_count": count}

    @app.get("/stream/{task_id}")
    async def stream(task_id: str, request: Request):
        """SSE实时返回结果"""
        if not task_exists(task_id):
            raise HTTPException(status_code=404, detail="查询任务不存在或已失效")
        _require_task_visitor(task_id, request)
        return StreamingResponse(
            sse_generator(task_id, request), media_type="text/event-stream"
        )

    @app.get("/diagnoses")
    async def list_diagnoses(
        request: Request,
        limit: int = 50,
        diagnosis_service: DiagnosisService = Depends(get_diagnosis_service),
    ):
        visitor_id, _ = _visitor_id(request, allow_create=False)
        try:
            sessions = diagnosis_service.repository.list_sessions(visitor_id, limit)
            return {"items": [diagnosis_service.session_payload(item) for item in sessions]}
        except Exception as exc:
            raise _diagnosis_http_error(exc) from exc

    @app.get("/diagnoses/{diagnosis_id}")
    async def get_diagnosis(
        diagnosis_id: str,
        request: Request,
        diagnosis_service: DiagnosisService = Depends(get_diagnosis_service),
    ):
        visitor_id, _ = _visitor_id(request, allow_create=False)
        try:
            session = diagnosis_service.repository.get_session(diagnosis_id, visitor_id)
            if session is None:
                raise DiagnosisSessionNotFoundError()
            return diagnosis_service.session_payload(session)
        except Exception as exc:
            raise _diagnosis_http_error(exc) from exc

    @app.post("/diagnoses/{diagnosis_id}/feedback")
    async def submit_diagnosis_feedback(
        diagnosis_id: str,
        payload: DiagnosisFeedbackRequest,
        request: Request,
        diagnosis_service: DiagnosisService = Depends(get_diagnosis_service),
    ):
        visitor_id, _ = _visitor_id(request, allow_create=False)
        try:
            session = diagnosis_service.repository.set_feedback(
                diagnosis_id, visitor_id, payload.status, payload.expected_revision
            )
            return diagnosis_service.session_payload(session)
        except Exception as exc:
            raise _diagnosis_http_error(exc) from exc

    @app.post("/diagnoses/{diagnosis_id}/end")
    async def end_diagnosis(
        diagnosis_id: str,
        payload: DiagnosisEndRequest,
        request: Request,
        diagnosis_service: DiagnosisService = Depends(get_diagnosis_service),
    ):
        visitor_id, _ = _visitor_id(request, allow_create=False)
        try:
            session = diagnosis_service.repository.transition_status(
                diagnosis_id, visitor_id, "ended", payload.expected_revision
            )
            return diagnosis_service.session_payload(session)
        except Exception as exc:
            raise _diagnosis_http_error(exc) from exc

    @app.delete("/diagnoses/{diagnosis_id}")
    async def delete_diagnosis(
        diagnosis_id: str,
        request: Request,
        diagnosis_service: DiagnosisService = Depends(get_diagnosis_service),
    ):
        visitor_id, _ = _visitor_id(request, allow_create=False)
        try:
            if not diagnosis_service.repository.delete_session(diagnosis_id, visitor_id):
                raise DiagnosisSessionNotFoundError()
            return {"message": "诊断会话已删除", "diagnosis_id": diagnosis_id}
        except Exception as exc:
            raise _diagnosis_http_error(exc) from exc


if __name__ == "__main__":
    uvicorn.run(app=create_app(), host="localhost", port=8001, log_level="info")
