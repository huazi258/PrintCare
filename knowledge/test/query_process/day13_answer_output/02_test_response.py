"""
 测试查询 API（非流式
"""

import requests

response = requests.post('http://localhost:8001/query', json={
    "query": "万用表怎么测电压？",
    "session_id": "test_001",
    "is_stream": False
})
print(response.json())
# {'message': '处理完成', 'session_id': 'test_001', 'answer': '我不确定您指的是哪款产品。, 您是在询问以下产品吗: RS PRO RS-12 数字万用表、HAK 180 扫描仪？'}


response = requests.post('http://localhost:8001/query', json={
    "query": "RS PRO RS-12 数字万用表",
    "session_id": "test_001",
    "is_stream": False
})
print(response.json())
#{'message': '处理完成', 'session_id': 'test_001', 'answer': '使用RS PRO RS-12数字万用表测量电压的步骤如下：\n\n1. **检查表笔连接**：将红色表笔插入“VΩ”（电压/电阻）插孔，黑色表笔插入“COM”（公共）插孔。\n\n2. **选择电压类型及量程**：\n   - 若测量交流电压（AC），将功能转盘旋转至“V AC”位置。\n   - 若测量直流电压（DC），将功能转盘旋转至“V DC”位置。\n   - 若无法预估电压大小，建议先选择最大量程（如600V），再逐步调低以获得更精确读数。\n\n3. **并联接入电路**：将红色表笔接触被测电路的高电位端（如电源正极），黑色表笔接触低电位端（如电源负极或接地端），确保表笔与测量点接触良好。\n\n4. **读取数值**：接通电路后，待显示屏显示稳定，读取屏幕上的电压值及单位（AC或DC）。若极性接反，直流电压测量时数值前会显示负号。\n\n5. **注意事项**：\n   - 测量前请确认电路已断开电源，避免在通电状态下操作。\n   - 正在打开或关闭电源时不要进行测量，以免瞬间高压损坏仪表。\n   - 交流电压测量时，若表笔未接触到插座内金属接口，可能导致读数为0，应检查接触情况。\n   - 最大可测交流/直流电压为600V。\n\n【图片】\n<http://192.168.6.150:9000/knowledge-base-files/万用表RS-12的使用/3e257858115a629b9112ea2e2c75344a2c2d01f2e6e110ab28d41809719fc433.jpg>'}