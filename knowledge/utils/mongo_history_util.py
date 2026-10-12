import logging
from typing import List, Dict, Any
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo import DESCENDING

from knowledge.utils.client.storage_clients import StorageClients

logger = logging.getLogger(__name__)


def _get_collection() -> Collection:
    """获取 chat_message 集合"""
    return StorageClients.get_mongo_db()["chat_message"]  # "chat_message"表名


def save_chat_message(
        session_id: str,
        visitor_id: str,
        role: str,
        text: str,
        rewritten_query: str = "",
        item_names: List[str] = None,
        sources: List[Dict[str, Any]] = None,
        message_id: str = None,
) -> str:
    """
    MongoDB的写入操作
    新增(message_id如果为空) or  修改（message_id不为空）
    Args:
        session_id:
        visitor_id:
        role:
        text:
        rewritten_query:
        item_names:
        sources:
        message_id:

    Returns:

    """
    if not isinstance(visitor_id, str) or not visitor_id.strip():
        raise ValueError("缺少历史记录所属匿名访客标识")

    ts = datetime.now().timestamp()

    # 1. 构建记录结构
    document = {
        "session_id": session_id,  # 会话id
        "visitor_id": visitor_id.strip(),  # 服务端匿名访客归属
        "role": role,  # 角色
        "text": text,  # 内容
        "rewritten_query": rewritten_query,  # 重写后问题
        "item_names": item_names or [],  # 商品名列表
        "ts": ts,  # 时间戳
    }
    if sources:
        document["sources"] = sources

    # 2. 获取集合[客户端 db collection]
    collection = _get_collection()
    if message_id:
        collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document},
        )
        return message_id
    else:
        result = collection.insert_one(document)
        return str(result.inserted_id)


def get_recent_messages(session_id: str, visitor_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    if not isinstance(visitor_id, str) or not visitor_id.strip():
        return []
    try:
        cursor = (
            _get_collection()
            .find({"session_id": session_id, "visitor_id": visitor_id.strip()})
            .sort("ts", DESCENDING)
            .limit(limit)
        )
        # 先按倒序取最近 N 条，再在内存中恢复为旧消息到新消息的顺序。
        return list(reversed(list(cursor)))
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return []


def clear_history(session_id: str, visitor_id: str) -> int:
    if not isinstance(visitor_id, str) or not visitor_id.strip():
        return 0
    try:
        result = _get_collection().delete_many({"session_id": session_id, "visitor_id": visitor_id.strip()})
        logger.info("Deleted %s messages for visitor-owned session", result.deleted_count)
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error clearing history for session {session_id}: {e}")
        return 0

def update_message_item_names(ids_to_update, confirmed: List[str]) -> int:
    """仅为尚未确认商品名的指定历史记录回填 ``item_names``。"""
    if not confirmed:
        return 0

    object_ids = []
    seen_ids = set()
    for message_id in ids_to_update:
        try:
            object_id = message_id if isinstance(message_id, ObjectId) else ObjectId(str(message_id))
        except (InvalidId, TypeError, ValueError):
            logger.warning("Skip invalid history message id while backfilling item names: %r", message_id)
            continue

        if object_id not in seen_ids:
            object_ids.append(object_id)
            seen_ids.add(object_id)

    if not object_ids:
        return 0

    try:
        result = _get_collection().update_many(
            {
                "_id": {"$in": object_ids},
                "$or": [
                    {"item_names": {"$exists": False}},
                    {"item_names": []},
                ],
            },
            {"$set": {"item_names": list(confirmed)}},
        )
        return result.modified_count
    except Exception:
        logger.exception("Failed to backfill item_names for history messages")
        return 0
