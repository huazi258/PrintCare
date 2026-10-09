from pymilvus.model.hybrid import BGEM3EmbeddingFunction

# 1.加载模型
bge_m3 = BGEM3EmbeddingFunction(
    model_name=r"D:\ai_models\modelscope_cache\models\BAAI\bge-m3",
    # device="cpu",
    # use_fp16=False,
    device="cuda:0",
    use_fp16=True,
)
# 2.生成嵌入向量
embeddings = bge_m3.encode_documents(["RS-12 数字万用表"])

# 3.提取向量
dense_vector = embeddings["dense"][0].tolist()
# 稀疏矩阵
sparse_matrix = embeddings["sparse"]

# 4.从CSR矩阵提取稀疏向量
"""
Compressed Sparse Row (CSR) 是一种用于高效存储‌稀疏矩阵‌（大部分元素为0的矩阵）的数据结构，通过仅存储非零元素及其位置信息，显著节省内存并优化行访问运算
核心组成
CSR 格式由三个一维数组构成：

data‌：按行优先顺序存储所有‌非零元素的值‌。
indices‌：存储每个非零元素对应的‌列索引‌。
indptr‌（行指针）：长度为“行数 + 1”，记录每行非零元素在 data 中的‌起始位置‌。第 i 行的非零元素范围为 data[indptr[i] : indptr[i+1]]。
"""
start_idx = sparse_matrix.indptr[0]
end_idx = sparse_matrix.indptr[1]
token_ids = sparse_matrix.indices[start_idx:end_idx].tolist()
weights = sparse_matrix.data[start_idx:end_idx].tolist()
sparse_vector = dict(zip(token_ids, weights))  # dict(int,float)
print(sparse_vector)
#{6: 0.00864410400390625, 1173: 0.1337890625, 3895: 0.1800537109375, 5873: 0.2437744140625, 9955: 0.264404296875, 18912: 0.218017578125, 28406: 0.1630859375}