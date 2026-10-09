from pydantic import BaseModel, Field, ValidationError
from scripts.regsetup import description


class Student(BaseModel):
    name: str = Field(..., description="姓名")
    age: int = Field(..., description="年龄")
    score: float = Field(default=0.0, description="成绩")


# 1.正常创建
s1 = Student(name="张三", age=22, score=95.5)
print(s1)  # name='张三' age=22 score=95.5
print(type(s1))  # <class '__main__.Student'>

# TypeError: BaseModel.__init__() takes 1 positional argument but 3 were given
# Pydantic 的 BaseModel 不支持位置参数初始化，必须使用关键字参数。

# 2.转成字典
print(s1.model_dump())  # {'name': '张三', 'age': 22, 'score': 95.5}
print(type(s1.model_dump()))  # <class 'dict'>
# 3.转成 JSON 字符串
print(s1.model_dump_json())  # {"name":"张三","age":22,"score":95.5}
print(type(s1.model_dump_json()))  # <class 'str'>

# 4.自动类型转换:  字符串“23” -> int 23
s2 = Student(name="丽思", age="23")
print(s2.age)
print(type(s2.age))  # <class 'int'>

# 5.类型校验失败： 直接报错
# try:
#     s3 = Student(name="王五",age="不是数字")
# except ValidationError as e:
#     print(e)
# 1 validation error for Student
# age
#   Input should be a valid integer, unable to parse string as an integer [type=int_parsing, input_value='不是数字', input_type=str]
#     For further information visit https://errors.pydantic.dev/2.13/v/int_parsing

# 6.缺少必要字段
# try:
#     s4 = Student(age=18)
# except ValidationError as e:
#     print(e)
# 1 validation error for Student
# name
#   Field required [type=missing, input_value={'age': 18}, input_type=dict]
#     For further information visit https://errors.pydantic.dev/2.13/v/missing

# 7.多余字段自动丢弃
s5 = Student(name="赵六", age=22, hobby="篮球")
print(s5.model_dump()) #{'name': '赵六', 'age': 22, 'score': 0.0}

# 8. 从字段创建(模拟后端返回数据)
data = {"name": "孙琦", "age": 19, "score": 99.9, "email": "sun7@163.com"}
s6 = Student(**data) #name='孙琦' age=19 score=99.9
print(s6)
