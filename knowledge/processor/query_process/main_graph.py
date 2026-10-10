import os



os.environ["LANGCHAIN_TRACING_V2"] = "false"

# knowledge/processor/query_process/main_graph.py

"""查询流程主图

使用 LangGraph 构建知识库查询工作流。
"""

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from dotenv import load_dotenv

from knowledge.processor.query_process.state import QueryGraphState
from knowledge.processor.query_process.nodes.answer_output import AnswerOutputNode
from knowledge.processor.query_process.nodes.item_name_confirm import ItemNameConfirmNode
from knowledge.processor.query_process.nodes.vector_search import VectorSearchNode
from knowledge.processor.query_process.nodes.hyde_search import HyDeSearchNode
from knowledge.processor.query_process.nodes.rrf import RrfNode
from knowledge.processor.query_process.nodes.rerank import RerankNode
from knowledge.processor.query_process.nodes.web_search_mcp import WebSearchMcpNode
from knowledge.processor.query_process.nodes.diagnosis_placeholder import DiagnosisPlaceholderNode
# 加载环境变量
load_dotenv()


def route_after_item_confirm(state: QueryGraphState) -> str:
    """商品名称确认后的路由逻辑。

    两种受支持模式均复用本地检索链；只有 qa 可继续进入 Web MCP。
    无效模式 fail-closed 到诊断占位节点，避免意外放宽为联网检索。

    Args:
        state: 查询图状态。

    Returns:
        下一个节点名称。
    """
    mode = state.get("mode", "qa")
    if mode not in {"qa", "diagnosis"}:
        return "diagnosis_placeholder"
    if state.get("answer"):
        return "answer_output" if mode == "qa" else "diagnosis_placeholder"
    return "multi_search"


def route_search_branches(state: QueryGraphState) -> list[str]:
    """按模式选择并行检索分支，诊断模式不调度 Web MCP 节点。"""
    if state.get("mode", "qa") == "qa":
        return ["search_embedding", "search_embedding_hyde", "web_search_mcp"]
    if state.get("mode") == "diagnosis":
        return ["search_embedding", "search_embedding_hyde"]
    return []


def route_after_rerank(state: QueryGraphState) -> str:
    """Route the shared post-rerank evidence to the selected business mode."""
    if state.get("mode", "qa") == "qa":
        return "answer_output"
    return "diagnosis_placeholder"


def create_query_graph() -> CompiledStateGraph:
    """创建查询流程图。

    Returns:
        编译后的 StateGraph 实例。

    流程结构::

        item_name_confirm
              │
              ├── (有答案) ──────────────────────────> answer_output
              │                                            │
              └── (无答案)                                  │
                   │                                       │
                   v                                       │
              multi_search                                 │
                   │                                       │
             ┌─────┼──────────┐                            │
             │     │          │                            │
             v     v          v                            │
        embedding  hyde    web_mcp (qa only)               │
             │     │          │                            │
             └─────┼──────────┘                            │
                   │                                       │
                   v                                       │
                 join                                      │
                   │                                       │
                   v                                       │
                  rrf                                      │
                   │                                       │
                   v                                       │
                rerank                                     │
                   │                                       │
                   v                                       │
          answer_output / diagnosis_placeholder <──────────┘
                   │
                   v
                  END

    Returns:
        编译后的 StateGraph 实例。
    """
    # 1. 定义LangGraph工作流
    workflow = StateGraph(QueryGraphState)

    # 2. 实例化节点
    nodes = {
        "item_name_confirm": ItemNameConfirmNode(),
        "multi_search": lambda x: x,   # 虚拟节点（分发）
        "search_embedding": VectorSearchNode(),
        "search_embedding_hyde": HyDeSearchNode(),
        "web_search_mcp": WebSearchMcpNode(),
        "join": lambda x: {},  # 虚拟节点（汇合）
        "rrf": RrfNode(),
        "rerank": RerankNode(),
        "answer_output": AnswerOutputNode(),
        "diagnosis_placeholder": DiagnosisPlaceholderNode(),
    }

    # 3. 添加节点
    for name, node in nodes.items():
        workflow.add_node(name, node)

    # 4. 设置入口点
    workflow.set_entry_point("item_name_confirm")

    # 5. 添加条件边：商品名称确认后根据是否有答案路由
    workflow.add_conditional_edges(
        "item_name_confirm",
        route_after_item_confirm,
        {
            "multi_search": "multi_search",
            "answer_output": "answer_output",
            "diagnosis_placeholder": "diagnosis_placeholder",
        }
    )

    # 6. 按模式并行分发：diagnosis 永远不调度 Web MCP。
    workflow.add_conditional_edges(
        "multi_search",
        route_search_branches,
        ["search_embedding", "search_embedding_hyde", "web_search_mcp"],
    )

    # 7. 多路搜索汇合
    workflow.add_edge("search_embedding", "join")
    workflow.add_edge("search_embedding_hyde", "join")
    workflow.add_edge("web_search_mcp", "join")

    # 8. 顺序边
    workflow.add_edge("join", "rrf")
    workflow.add_edge("rrf", "rerank")
    workflow.add_conditional_edges(
        "rerank",
        route_after_rerank,
        {
            "answer_output": "answer_output",
            "diagnosis_placeholder": "diagnosis_placeholder",
        },
    )
    workflow.add_edge("answer_output", END)
    workflow.add_edge("diagnosis_placeholder", END)

    # 9. 返回可运行的状态
    return workflow.compile()


# 创建全局图实例
query_app = create_query_graph()


if __name__ == "__main__":
    from knowledge.processor.query_process.base import setup_logging

    setup_logging()

    print("=" * 60)
    print("开始测试: 查询流程主图 (main_graph)")
    print("=" * 60)

    # 测试场景：商品名明确，走完整 pipeline
    print("\n【场景】: 商品名明确，走完整 pipeline")
    print("-" * 60)

    mock_state_1 = {
        "original_query": "RS-12 数字万用表如何测量直流电压？",
        "session_id": "test_session_main_graph",
        "task_id": "test_task_001",
        "is_stream": False,
    }

    print(f"  查询: {mock_state_1['original_query']}")
    print(f"  session_id: {mock_state_1['session_id']}")

    result_1 = query_app.invoke(mock_state_1) #只能看到最后结果
    #result_1 = query_app.stream(mock_state_1) #可以查看到每一个节点的输出
    #与LLM中的llm.invoke()和 llm.stream()的作用不同。llm.stream()表示流式输出。

    print(f"\n  【结果】:")
    print(f"  商品名: {result_1.get('item_names')}")
    print(f"  重写查询: {result_1.get('rewritten_query')}")
    answer_1 = result_1.get("answer", "")
    print(f"  答案: {answer_1[:200]}..." if len(answer_1) > 200 else f"  答案: {answer_1}")

"""
    invoke vs stream 的区别：

    对比项            invoke                          stream
    ----------------------------------------------------------------------
    返回方式          一次性返回最终结果                 逐步返回每个节点的输出
    返回类型          dict（完整最终状态）              生成器，逐个产出 (节点名, 节点输出)
    适用场景          不需要中间过程，只要最终答案        需要实时进度、流式展示中间步骤
"""
