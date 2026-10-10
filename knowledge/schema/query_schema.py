from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(..., description="查询内容")
    session_id: Optional[str] = Field(..., description="会话ID")
    is_stream: bool = Field(..., description="是否流式输出")
    device_id: Optional[str] = Field(
        default=None,
        description="设备稳定标识；缺省时兼容旧客户端并使用 Creality K1",
    )
    mode: Literal["qa", "diagnosis"] = Field(
        default="qa",
        description="业务模式；当前仅开放 qa，diagnosis 预留给后续版本",
    )


class QueryResponse(BaseModel):
    """查询响应模型"""
    message: str
    session_id: str
    answer: str
    task_id:str


class StreamSubmitResponse(BaseModel):
    """流式提交响应模型"""
    message: str
    session_id: str
    task_id: str


class QueryTaskStatusResponse(BaseModel):
    """查询任务状态响应。"""
    status: str
    running_list: List[str] = Field(default_factory=list)
    done_list: List[str] = Field(default_factory=list)
    durations: Dict[str, float] = Field(default_factory=dict)
    answer: str = ""
    error: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
