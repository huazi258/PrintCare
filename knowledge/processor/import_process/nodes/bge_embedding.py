import json
from pathlib import Path
from typing import List, Dict, Any

from knowledge.processor.import_process.base import BaseNode, T, setup_logging
from knowledge.processor.import_process.config import get_config
from knowledge.processor.import_process.exceptions import ValidationError
from knowledge.utils.client.ai_clients import AIClients


class BgeEmbeddingChunksNode(BaseNode):
    """
    主要职责：
    1.获取所有chunks拼接要向量的内容
    2.批量嵌入chunk的 (embedding_content :  item_name + chunk.get('content'))
    3.将所有chunk嵌入后的向量值，存储到列表中，在返回给下一个节点用
    """

    name = "bge_embedding_chunks_node"

    def process(self, state: T) -> T:
        # 1.参数校验
        validated_chunks, config = self._validate_get_inputs(state)

        # 2.获取批量嵌入的阈值
        embedding_batch_chunk_size = getattr(config, "embedding_batch_size", 16)

        # 3. 准备分批嵌入
        total_length = len(validated_chunks)
        final_chunks = []
        for i in range(0, total_length, embedding_batch_chunk_size):
            batch = validated_chunks[i:i + embedding_batch_chunk_size]
            batch_chunks = self._process_batch_chunks(batch, i, total_length)
            final_chunks.extend(batch_chunks)

        # 4.更新&返回state
        state['chunks'] = final_chunks
        return state

    def _validate_get_inputs(self, state):
        """验证参数"""
        self.log_step("step1", "数据校验")
        config = get_config()
        chunks = state.get("chunks")
        if not chunks or not isinstance(chunks, list):
            raise ValidationError(f"chunks为空或者无效", self.name)
        self.logger.info(f"chunks数量：{len(chunks)}")
        return chunks, config

    def _process_batch_chunks(self, batch: List[Dict[str, Any]], start_index: int, total_length: int):
        """处理批量chunks"""
        # 1.循环处理chunk 中需要嵌入的内容，内容拼接=  item_name + \n content
        embedding_contents = []
        for _, chunk in enumerate(batch):
            item_name = chunk.get("item_name")
            content = chunk.get("content")
            embedding_content = f"{item_name}\n{content}"
            embedding_contents.append(embedding_content)

        # 2.批量嵌入
        try:
            bge_m3_client = AIClients.get_bge_m3_client()
            embedding_result = bge_m3_client.encode_documents(documents=embedding_contents)
            if not embedding_result:
                self.logger.warning(f"嵌入后结果不存在")
                return batch
        except Exception as e:
            self.logger.warning(f"生成嵌入向量失败:{str(e)}")

        # 3.循环处理所有chunk的向量，以及注入到每一个chunk中
        for index, chunk in enumerate(batch):
            dense_vector = embedding_result['dense'][index].tolist()
            csr_array = embedding_result['sparse']
            start_index = csr_array.indptr[index]
            end_index = csr_array.indptr[index + 1]
            token_id = csr_array.indices[start_index:end_index].tolist()
            weight = csr_array.data[start_index:end_index].tolist()
            sparse_voctor = dict(zip(token_id, weight))
            chunk['dense_vector'] = dense_vector
            chunk['sparse_vector'] = sparse_voctor

        self.logger.info(f"开始批量处理 chunk  嵌入；批次{start_index + 1}-{start_index + len(batch)}/{total_length}")

        # 返回处理结果
        return batch


# ================================================================== #
#                        测试代码                                     #
# ================================================================== #
if __name__ == "__main__":
    setup_logging()
    base_temp_dir = Path(
        r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto")
    input_path = base_temp_dir / "chunks2.json"
    output_path = base_temp_dir / "chunks_vector2.json"
    if not input_path.exists():
        print(f"找不到输入文件:{input_path}")
    with open(input_path, 'r', encoding="utf-8") as f:
        content = json.load(f)

    state = {
        "chunks": content
    }

    node_bge_embedding = BgeEmbeddingChunksNode()
    process_result = node_bge_embedding.process(state)
    with open(output_path, 'w', encoding="utf-8") as f:
        json.dump(process_result, f, ensure_ascii=False, indent=4)
    print(f"向量生成测试完成,结果已成功保存到:\n{output_path}")
