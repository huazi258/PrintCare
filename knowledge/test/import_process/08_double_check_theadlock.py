"""
并发安全与双重检查锁机制
"""
import threading




class User:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def _get_or_create(cls, attr_name, lock, factory):
        # 第一次检查（无锁，快速路径）  -- 99% 的调用在这里就返回了
        instance = getattr(cls, attr_name, None)
        if instance is not None:
            return instance

        with lock:
            # 第二次检查（有锁，防止并发重复创建）
            instance = getattr(cls, attr_name, None)
            if instance is not None:
                return instance
            instance = factory()
            setattr(cls, attr_name, instance)
            return instance

user = User._get_or_create("_instance", User._lock, lambda: User())
print(user)
