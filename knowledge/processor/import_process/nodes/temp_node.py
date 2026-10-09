
from knowledge.processor.import_process.base import T,BaseNode,setup_logging


class TempNode(BaseNode):
    def process(self, state: T) -> T:
        """
        节点处理逻辑
        """
        self.log_step("temp_node","开始执行了")

if __name__ == "__main__":

    setup_logging()

    # 方式一
    temp_node = TempNode()

    #调用方式1
    #temp_node.process(None)

    #调用方式2
    temp_node(None)