# knowledge/processor/query_process/state.py

"""查询流程状态类型定义

定义完整的查询状态结构和辅助函数。
"""

from typing import TypedDict, List
import copy


class QueryGraphState(TypedDict):
    """查询流程图状态。

    包含整个查询流程中传递的所有数据。
    """
    session_id: str              # 会话ID
    task_id: str                  # 任务ID
    message_id: str               # 消息ID
    original_query: str           # 原始查询
    device_id: str                # 服务端确认的设备稳定标识
    device_model: str             # 服务端确认的设备显示名
    mode: str                     # qa / diagnosis
    diagnosis_id: str             # MongoDB 诊断会话标识（T2-03）
    diagnosis_facts: list         # 已确认诊断事实（T2-03）
    diagnosis_answer_history: list  # 已答诊断问题历史（T2-03）
    clarification_count: int      # 已持久化的追问轮数
    diagnosis_candidate: dict     # 未经 T2-05 引用验证的候选决策
    diagnosis_validated: dict     # 已通过 T2-05 校验的内部决策
    diagnosis_validation_passed: bool  # 候选是否原样通过校验
    diagnosis_validation_error: dict  # 引用或安全校验拒绝原因
    diagnosis_system_error: dict  # 模型/解析系统失败，不等同资料不足
    diagnosis_status: str         # 诊断内部状态
    diagnosis_message: str        # 诊断内部状态说明
    embedding_chunks: list        # 向量检索结果
    hyde_embedding_chunks: list   # HyDE检索结果
    rrf_chunks: list              # RRF融合后的切片
    web_search_docs: list         # 网页搜索结果
    reranked_docs: list           # 重排序后的文档
    prompt: str                   # 提示词
    answer: str                   # 答案
    item_names: List[str]         # 商品名称
    rewritten_query: str          # 重写查询
    history: list                 # 历史对话
    is_stream: bool               # 是否流式输出


# ==================== 默认状态 ====================

DEFAULT_STATE: QueryGraphState = {
    "session_id": "",
    "task_id": "",
    "message_id": "",
    "original_query": "",
    "device_id": "",
    "device_model": "",
    "mode": "qa",
    "diagnosis_id": "",
    "diagnosis_facts": [],
    "diagnosis_answer_history": [],
    "clarification_count": 0,
    "diagnosis_candidate": {},
    "diagnosis_validated": {},
    "diagnosis_validation_passed": False,
    "diagnosis_validation_error": {},
    "diagnosis_system_error": {},
    "diagnosis_status": "",
    "diagnosis_message": "",
    "embedding_chunks": [],
    "hyde_embedding_chunks": [],
    "rrf_chunks": [],
    "web_search_docs": [],
    "reranked_docs": [],
    "prompt": "",
    "answer": "",
    "item_names": [],
    "rewritten_query": "",
    "history": [],
    "is_stream": False,
}


def create_default_state(**overrides) -> QueryGraphState:
    """创建默认状态，支持字段覆盖。

    Args:
        **overrides: 要覆盖的字段键值对。

    Returns:
        新的状态实例，包含默认值和覆盖值。
    """
    state = copy.deepcopy(DEFAULT_STATE)
    state.update(overrides)
    return state


def get_default_state() -> QueryGraphState:
    """获取默认状态副本。"""
    return copy.deepcopy(DEFAULT_STATE)


# 兼容旧版变量名
graph_default_state = DEFAULT_STATE
