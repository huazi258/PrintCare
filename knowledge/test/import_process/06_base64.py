
import base64

with open("D:/temp/p1.jpg","rb") as f:
    binary_data = f.read() #读取原始的二进制数据
    base64_byte = base64.b64encode(binary_data)  #进行base64编码
    base64_string = base64_byte.decode("utf-8") #转换为字符串
    print(base64_string)
print('------------')
binary_data = base64.b64decode(base64_string)
print(binary_data)


