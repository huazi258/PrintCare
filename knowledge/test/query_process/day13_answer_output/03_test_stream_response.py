"""
 测试查询 API（流式）
"""

import requests
import sseclient

# 1. 提交查询
response = requests.post('http://localhost:8001/query', json={
    "query": "万用表怎么测电压？",
    "session_id": "test_001",
    "is_stream": True
})
task_id = response.json()['task_id']

# 2. 连接 SSE 流
url = f'http://localhost:8001/stream/{task_id}'
response = requests.get(url, stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    print(f"Event: {event.event}, Data: {event.data}")

"""
Event: progress, Data: {"status": "processing", "done_list": [], "running_list": ["确认问题产品"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品"], "running_list": []}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品"], "running_list": ["切片搜索"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品"], "running_list": ["切片搜索", "切片搜索(假设性文档)"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品"], "running_list": ["切片搜索", "切片搜索(假设性文档)", "网络搜索"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索"], "running_list": ["切片搜索(假设性文档)", "网络搜索"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索"], "running_list": ["切片搜索(假设性文档)"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)"], "running_list": []}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)"], "running_list": ["倒排融合"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)", "倒排融合"], "running_list": []}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)", "倒排融合"], "running_list": ["重排序"]}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)", "倒排融合", "重排序"], "running_list": []}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)", "倒排融合", "重排序"], "running_list": ["生成答案"]}
Event: delta, Data: {"delta": "使用"}
Event: delta, Data: {"delta": "RS"}
Event: delta, Data: {"delta": " PRO"}
Event: delta, Data: {"delta": " RS"}
Event: delta, Data: {"delta": "-12数字"}
Event: delta, Data: {"delta": "万用表测量"}
Event: delta, Data: {"delta": "电压的步骤如下"}
Event: delta, Data: {"delta": "：\n\n1. **"}
Event: delta, Data: {"delta": "检查表笔连接"}
Event: delta, Data: {"delta": "**：将红色"}
Event: delta, Data: {"delta": "表笔插入“"}
Event: delta, Data: {"delta": "VΩ”（"}
Event: delta, Data: {"delta": "电压/电阻）"}
Event: delta, Data: {"delta": "插孔，黑色"}
Event: delta, Data: {"delta": "表笔插入“"}
Event: delta, Data: {"delta": "COM”（公共"}
Event: delta, Data: {"delta": "）插孔。\n\n"}
Event: delta, Data: {"delta": "2. **选择"}
Event: delta, Data: {"delta": "电压类型及量"}
Event: delta, Data: {"delta": "程**：\n  "}
Event: delta, Data: {"delta": " - 若测量交流"}
Event: delta, Data: {"delta": "电压（AC），"}
Event: delta, Data: {"delta": "将功能转盘"}
Event: delta, Data: {"delta": "旋转至“V"}
Event: delta, Data: {"delta": " AC”位置。\n"}
Event: delta, Data: {"delta": "   - 若测量"}
Event: delta, Data: {"delta": "直流电压（DC"}
Event: delta, Data: {"delta": "），将功能转"}
Event: delta, Data: {"delta": "盘旋转至“"}
Event: delta, Data: {"delta": "V DC”位置"}
Event: delta, Data: {"delta": "。\n   - 若"}
Event: delta, Data: {"delta": "无法预估电压"}
Event: delta, Data: {"delta": "大小，建议先"}
Event: delta, Data: {"delta": "选择最大量程"}
Event: delta, Data: {"delta": "（如60"}
Event: delta, Data: {"delta": "0V），再"}
Event: delta, Data: {"delta": "逐步调低以"}
Event: delta, Data: {"delta": "获得更精确读"}
Event: delta, Data: {"delta": "数。\n\n3."}
Event: delta, Data: {"delta": " **并联接入"}
Event: delta, Data: {"delta": "电路**：将"}
Event: delta, Data: {"delta": "红色表笔接触"}
Event: delta, Data: {"delta": "被测电路的"}
Event: delta, Data: {"delta": "高电位端"}
Event: delta, Data: {"delta": "（如电源正"}
Event: delta, Data: {"delta": "极），黑色表"}
Event: delta, Data: {"delta": "笔接触低电"}
Event: delta, Data: {"delta": "位端（如"}
Event: delta, Data: {"delta": "电源负极或"}
Event: delta, Data: {"delta": "接地端），确保"}
Event: delta, Data: {"delta": "表笔与测量"}
Event: delta, Data: {"delta": "点接触良好。\n\n"}
Event: delta, Data: {"delta": "4. **读"}
Event: delta, Data: {"delta": "取数值**："}
Event: delta, Data: {"delta": "接通电路后"}
Event: delta, Data: {"delta": "，待显示屏显示"}
Event: delta, Data: {"delta": "稳定，读取"}
Event: delta, Data: {"delta": "屏幕上的电压值"}
Event: delta, Data: {"delta": "及单位（AC"}
Event: delta, Data: {"delta": "或DC）。若"}
Event: delta, Data: {"delta": "极性接反"}
Event: delta, Data: {"delta": "，直流电压测量"}
Event: delta, Data: {"delta": "时数值前会"}
Event: delta, Data: {"delta": "显示负号。\n\n"}
Event: delta, Data: {"delta": "5. **注意事项"}
Event: delta, Data: {"delta": "**：\n   -"}
Event: delta, Data: {"delta": " 测量前"}
Event: delta, Data: {"delta": "请确认电路已"}
Event: delta, Data: {"delta": "断开电源，"}
Event: delta, Data: {"delta": "避免在通电"}
Event: delta, Data: {"delta": "状态下操作。\n  "}
Event: delta, Data: {"delta": " - 正在"}
Event: delta, Data: {"delta": "打开或关闭电源"}
Event: delta, Data: {"delta": "时不要进行测量"}
Event: delta, Data: {"delta": "，以免瞬间高压"}
Event: delta, Data: {"delta": "损坏仪表。\n  "}
Event: delta, Data: {"delta": " - 交流电压"}
Event: delta, Data: {"delta": "测量时，若"}
Event: delta, Data: {"delta": "表笔未接触到"}
Event: delta, Data: {"delta": "插座内金属接口"}
Event: delta, Data: {"delta": "，可能导致读数"}
Event: delta, Data: {"delta": "为0，应"}
Event: delta, Data: {"delta": "检查接触情况。\n"}
Event: delta, Data: {"delta": "   - 最大"}
Event: delta, Data: {"delta": "可测交流/"}
Event: delta, Data: {"delta": "直流电压为6"}
Event: delta, Data: {"delta": "00V。\n\n"}
Event: delta, Data: {"delta": "【图片】\n"}
Event: delta, Data: {"delta": "<http://1"}
Event: delta, Data: {"delta": "92.1"}
Event: delta, Data: {"delta": "68.6"}
Event: delta, Data: {"delta": ".150"}
Event: delta, Data: {"delta": ":900"}
Event: delta, Data: {"delta": "0/knowledge-base"}
Event: delta, Data: {"delta": "-files/万用"}
Event: delta, Data: {"delta": "表RS-1"}
Event: delta, Data: {"delta": "2的使用/"}
Event: delta, Data: {"delta": "3e25"}
Event: delta, Data: {"delta": "7858"}
Event: delta, Data: {"delta": "115a"}
Event: delta, Data: {"delta": "629b"}
Event: delta, Data: {"delta": "9112"}
Event: delta, Data: {"delta": "ea2e2"}
Event: delta, Data: {"delta": "c753"}
Event: delta, Data: {"delta": "44a2"}
Event: delta, Data: {"delta": "c2d0"}
Event: delta, Data: {"delta": "1f2e"}
Event: delta, Data: {"delta": "6e11"}
Event: delta, Data: {"delta": "0ab28"}
Event: delta, Data: {"delta": "d418"}
Event: delta, Data: {"delta": "0971"}
Event: delta, Data: {"delta": "9fc43"}
Event: delta, Data: {"delta": "3.jpg>"}
Event: final, Data: {"answer": "使用RS PRO RS-12数字万用表测量电压的步骤如下：\n\n1. **检查表笔连接**：将红色表笔插入“VΩ”（电压/电阻）插孔，黑色表笔插入“COM”（公共）插孔。\n\n2. **选择电压类型及量程**：\n   - 若测量交流电压（AC），将功能转盘旋转至“V AC”位置。\n   - 若测量直流电压（DC），将功能转盘旋转至“V DC”位置。\n   - 若无法预估电压大小，建议先选择最大量程（如600V），再逐步调低以获得更精确读数。\n\n3. **并联接入电路**：将红色表笔接触被测电路的高电位端（如电源正极），黑色表笔接触低电位端（如电源负极或接地端），确保表笔与测量点接触良好。\n\n4. **读取数值**：接通电路后，待显示屏显示稳定，读取屏幕上的电压值及单位（AC或DC）。若极性接反，直流电压测量时数值前会显示负号。\n\n5. **注意事项**：\n   - 测量前请确认电路已断开电源，避免在通电状态下操作。\n   - 正在打开或关闭电源时不要进行测量，以免瞬间高压损坏仪表。\n   - 交流电压测量时，若表笔未接触到插座内金属接口，可能导致读数为0，应检查接触情况。\n   - 最大可测交流/直流电压为600V。\n\n【图片】\n<http://192.168.6.150:9000/knowledge-base-files/万用表RS-12的使用/3e257858115a629b9112ea2e2c75344a2c2d01f2e6e110ab28d41809719fc433.jpg>"}
Event: progress, Data: {"status": "processing", "done_list": ["确认问题产品", "切片搜索", "网络搜索", "切片搜索(假设性文档)", "倒排融合", "重排序", "生成答案"], "running_list": []}

"""