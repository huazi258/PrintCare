import logging
import uuid
from typing import List, Dict, Any

from knowledge.processor.query_process.main_graph import query_app
from knowledge.utils.mongo_history_util import clear_history, get_recent_messages
from knowledge.utils.task_util import create_task, get_task_result, set_task_result, update_task_status, \
    TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_PROCESSING

logger = logging.getLogger(__name__)


class QueryService:

    def run_query_graph(self, session_id, task_id, user_query: str, is_stream: bool):
        """执行LangGraph 查询流程
        注意：流式模式的 SSE 队列由路由层在调用前创建
        """
        try:
            # 1.更新任务状态
            update_task_status(task_id, TASK_STATUS_PROCESSING)

            # 2.构建初始化状态
            default_state = {
                "original_query": user_query,
                "session_id": session_id,
                "task_id": task_id,
                "is_stream": is_stream
            }

            # 3.执行查询图谱
            query_app.invoke(default_state)

            # 4.成功，记录完成
            update_task_status(task_id, TASK_STATUS_COMPLETED)
        except Exception as e:
            # 5.失败，记录失败
            logger.error(f"启动查询流程执行失败：{e}")
            set_task_result(task_id, "error", str(e))
            update_task_status(task_id, TASK_STATUS_FAILED)

    def generate_session_id(self) -> str:
        return str(uuid.uuid4())

    def get_answer(self, task_id: str) -> str:
        return get_task_result(task_id, "answer", "")

    def get_history(self, session_id: str, limit: int) -> List[Dict[str, Any]]:
        records = get_recent_messages(session_id, limit)
        return [
            {
                "_id": str(r.get("_id", "")),
                "session_id": r.get("session_id", ""),
                "role": r.get("role", ""),
                "text": r.get("text", ""),  # 问题
                "rewritten_query": r.get("rewritten_query", ""),  # 问题重写
                "item_names": r.get("item_names", []),  # 问题答案
                "ts": r.get("ts")
            } for r in records
        ]

    def clear_history(self, session_id: str) -> int:
        return clear_history(session_id)

    def generate_task_id(self):
        task_id = str(uuid.uuid4().hex[:8])
        create_task(task_id)
        return task_id
