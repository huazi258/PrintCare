from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from knowledge.schema.diagnosis_schema import DiagnosisAnswerInput


class QueryRequest(BaseModel):
    """查询请求模型"""
    query: Optional[str] = Field(default=None, description="普通问答内容")
    session_id: Optional[str] = Field(default=None, description="普通问答会话ID")
    is_stream: bool = Field(default=False, description="是否流式输出")
    device_id: Optional[str] = Field(
        default=None,
        description="设备稳定标识；缺省时兼容旧客户端并使用 Creality K1",
    )
    mode: Literal["qa", "diagnosis"] = Field(
        default="qa",
        description="业务模式；qa 为普通问答，diagnosis 为结构化诊断",
    )
    original_problem: Optional[str] = Field(default=None, description="发起诊断时的原始故障描述")
    diagnosis_id: Optional[str] = Field(default=None, description="继续诊断时的会话标识")
    answers: Optional[List[DiagnosisAnswerInput]] = Field(default=None, description="本轮批量答案")
    request_id: Optional[str] = Field(default=None, description="诊断请求幂等标识")
    expected_revision: Optional[int] = Field(default=None, ge=0, description="诊断会话预期版本")
    resume_unresolved: bool = Field(default=False, description="继续一条用户标记为未解决的诊断")

    @model_validator(mode="after")
    def validate_mode_payload(self) -> "QueryRequest":
        if self.mode == "qa":
            if not isinstance(self.query, str) or not self.query.strip():
                raise ValueError("qa 模式必须提供非空 query")
            return self

        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("diagnosis 模式必须提供非空 request_id")
        if self.diagnosis_id is None:
            if not isinstance(self.original_problem, str) or not self.original_problem.strip():
                raise ValueError("发起诊断必须提供非空 original_problem")
            if not isinstance(self.device_id, str) or not self.device_id.strip():
                raise ValueError("发起诊断必须提供 device_id")
            if self.answers is not None:
                raise ValueError("发起诊断不能提交 answers")
            return self

        if not self.diagnosis_id.strip():
            raise ValueError("diagnosis_id 不能为空")
        if self.expected_revision is None:
            raise ValueError("继续诊断必须提供 expected_revision")
        if self.original_problem is not None or self.device_id is not None:
            raise ValueError("继续诊断不能覆盖原始故障或设备归属")
        if self.resume_unresolved:
            if self.answers:
                raise ValueError("恢复未解决诊断时不能同时提交 answers")
            return self
        if not self.answers:
            raise ValueError("继续诊断必须提交至少一个答案")
        return self


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
    diagnosis: Optional[Dict] = None
