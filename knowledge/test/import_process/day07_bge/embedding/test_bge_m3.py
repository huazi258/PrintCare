from pymilvus.model.hybrid import BGEM3EmbeddingFunction

#  GPU设置True
# bge_m3_ef = BGEM3EmbeddingFunction(
#     #model_name='BAAI/day07_bge-m3', # Specify the model name
#     model_name=r'D:\ai_models\modelscope_cache\models\BAAI\day07_bge-m3', # Specify the model name
#     device='cuda:0', # Specify the device to use, e.g., 'cpu' or 'cuda:0'
#     use_fp16=True # Specify whether to use fp16. Set to `False` if `device` is `cpu`.
# )

# CPU设置False
bge_m3_ef = BGEM3EmbeddingFunction(
    # model_name='BAAI/day07_bge-m3', # Specify the model name
    model_name=r'D:\ai_models\modelscope_cache\models\BAAI\bge-m3',  # Specify the model name
    device='cpu',  # Specify the device to use, e.g., 'cpu' or 'cuda:0'
    use_fp16=False  # Specify whether to use fp16. Set to `False` if `device` is `cpu`.
)

print(bge_m3_ef)
# 嵌入对象（query or document）encode_queries  # 用户问题嵌入（批量文档） or encode_documents() # 文档内容嵌入（一个文档）
vector_result = bge_m3_ef.encode_queries(queries=['我是中国人'])
print(vector_result)

#稠密向量
# 1. 稠密向量
dense = vector_result.get("dense")[0].tolist() #[-0.0019392839167267084, 0.00953724142163992, -0.0359557680785656, ...]
shape = vector_result.get("dense")[0].shape #(1024,)
dtype = vector_result.get("dense")[0].dtype #float32

#稀疏向量
# 2. 稀疏向量(token_id: 权重)--->{"token_id":"权重","token_id":"权重"，"token_id":权重}---》Milvus用户稀疏向量的结构必须是一个字典且key:必须是token_id value：必须是权重
sparse = vector_result.get("sparse")  # 压缩矩阵
# <Compressed Sparse Row sparse array of dtype 'float64'
# 	with 3 stored elements and shape (1, 250002)>
#   Coords	Values
#   (0, 6)	0.1512526422739029
#   (0, 28309)	0.3007478713989258
#   (0, 75224)	0.3262038230895996
print(dense)
print(shape)
print(dtype)
print(sparse)

"""  稠密稀疏向量
{
    'dense': [array([-0.00193928,  0.00953724, -0.03595577, ..., -0.03505819,-0.05228406, -0.01769409], shape=(1024,), dtype=float32)], 
    'sparse': <Compressed Sparse Row sparse array of dtype 'float64'
	with 3 stored elements and shape (1, 250002)>}
"""


"""
        //============================
        Connected to server 127.0.0.1:52214
        start to install package: datasets

        [notice] A new release of pip is available: 26.1.1 -> 26.1.2
        [notice] To update, run: python.exe -m pip install --upgrade pip
        successfully installed package: datasets
        start to install package: FlagEmbedding>=1.3.3

        [notice] A new release of pip is available: 26.1.1 -> 26.1.2
        [notice] To update, run: python.exe -m pip install --upgrade pip
        successfully installed package: FlagEmbedding>=1.3.3
        //============================
"""

# 总结: 这不是 bug,程序实际上已经成功完成了所有操作并正常退出,只是退出时的资源清理产生了警告信息。
# <pymilvus.model.hybrid.bge_m3.BGEM3EmbeddingFunction object at 0x0000027EA8DEC530>
# You're using a XLMRobertaTokenizerFast tokenizer. Please note that with a fast tokenizer, using the `__call__` method is faster than using a method to encode the text followed by a call to the `pad` method to get a padded encoding.
# {'dense': [array([-0.00193928,  0.00953724, -0.03595577, ..., -0.03505819,
#        -0.05228406, -0.01769409], shape=(1024,), dtype=float32)], 'sparse': <Compressed Sparse Row sparse array of dtype 'float64'
# 	with 3 stored elements and shape (1, 250002)>}
# Disconnected from server
# Exception ignored in: <function ResourceTracker.__del__ at 0x0000027F141084A0>
# Traceback (most recent call last):
#   File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 80, in __del__
#   File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 89, in _stop
#   File "D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\.venv\Lib\site-packages\multiprocess\resource_tracker.py", line 102, in _stop_locked
# AttributeError: '_thread.RLock' object has no attribute '_recursion_count'




"""
encode_queries vs encode_documents 区别
BGE-M3 采用非对称检索策略，两个方法会在文本前添加不同的指令前缀（instruction prefix），让模型知道当前编码的是"问题"还是"文档"，从而生成更适合匹配的向量。
方法               用途          适用场景         输入参数名
----------------------------------------------------------
encode_queries   编码查询文本    用户搜索问题      queries
encode_documents 编码文档内容    入库存储的文档    documents
"""