from pymilvus import MilvusClient, DataType
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

"""样例代码"""

# 1.连接
client = MilvusClient(uri="http://192.168.6.150:19530")

# 2.建集合

schema = client.create_schema()
schema.add_field(
    field_name="pk",
    datatype=DataType.VARCHAR,
    is_primary=True,
    auto_id=True,
    max_length=100
)
schema.add_field(
    field_name="file_title",
    datatype=DataType.VARCHAR,
    max_length=100
)
schema.add_field(
    field_name="item_name",
    datatype=DataType.VARCHAR,
    max_length=65535
)
schema.add_field(
    field_name="dense_vector",
    datatype=DataType.FLOAT_VECTOR,
    dim=1024
)
schema.add_field(
    field_name="sparse_vector",
    datatype=DataType.SPARSE_FLOAT_VECTOR
)
index_param = client.prepare_index_params()
index_param.add_index(
    field_name="dense_vector",
    index_name="dense_vector_index",
    index_type="AUTOINDEX",
    metric_type="COSINE"
)
index_param.add_index(
    field_name="sparse_vector",
    index_name="sparse_vector_index",
    index_type="SPARSE_INVERTED_INDEX",
    metric_type="IP"
)

client.create_collection(collection_name="kb_item_name_v1", schema=schema, index_params=index_param)

# 3. 插入数据



import os
from dotenv import load_dotenv

load_dotenv()

# 1. 加载 BGE-M3 模型生成真实向量
bge_m3 = BGEM3EmbeddingFunction(
    model_name=os.getenv("BGE_M3_PATH", r"D:\ai_models\modelscope_cache\models\BAAI\bge-m3"),
    device="cpu",
    use_fp16=False,
)

# 2. 生成嵌入向量
item_name = "RS-12数字万用表"
embeddings = bge_m3.encode_documents([item_name])

# 3. 提取向量
dense_vector = embeddings["dense"][0].tolist()  # 1024维
sparse_matrix = embeddings["sparse"]
start_idx = sparse_matrix.indptr[0]
end_idx = sparse_matrix.indptr[1]
token_ids = sparse_matrix.indices[start_idx:end_idx].tolist()
weights = sparse_matrix.data[start_idx:end_idx].tolist()
sparse_vector = dict(zip(token_ids, weights))

print(f"dense_vector 维度: {len(dense_vector)}")
print(f"sparse_vector: {sparse_vector}")

data = {
    "file_title": "万用表的使用",
    "item_name": "RS-12数字万用表",
    "dense_vector": dense_vector, #[0.12, -0.03],
    "sparse_vector": sparse_vector #{6: 0.015, 1173: 0.186}
}
# 4.搜索
client.insert(collection_name="kb_item_name_v1", data=[data])

