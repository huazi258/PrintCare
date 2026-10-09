class Person:

    def __init__(self, name: str, age: int, city: str = "Unknown"):
        self.name = name
        self.age = age
        self.city = city

    def __repr__(self):
        return f"Person(name={self.name!a},age={self.age!r},city={self.city!r})"
        #return f"Person(name={self.name!a},age={self.age!r},city={self.city!r})"
        #Person(name='\u5f20\u4e09',age=22,city='Unknown')
    def __eq__(self, other):
        if not isinstance(other, Person):
            return False
        return (self.name == other.name and self.age == other.age
                and self.city == other.city)

from dataclasses import dataclass
@dataclass(frozen=True) #冰冻   只读属性,不允许修改
class User:
    name:str
    age:int
    city:str="Unknown"


if __name__ == "__main__":
    p1 = Person("张三", 22)
    print(p1)

    u1 = User("丽思",18)
    print(u1)
    #u1.name = "丽思2"