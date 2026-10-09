"""
PDF转MD节点
使用MinerU将PDF文档转换为MarkDown格式
"""
import json
import subprocess
import time
from pathlib import Path
from typing import Tuple

from knowledge.processor.import_process.base import BaseNode, setup_logging, T
from knowledge.processor.import_process.state import ImportGraphState
from knowledge.processor.import_process.exceptions import ValidationError, FileProcessingError, PdfConversionError


class PdfToMdNode(BaseNode):
    """
    PDF转MD节点
    调用MinerU命令将PDF转换为Markdown,支持实时输出转换日志
    """

    name = "pdf_to_md_node"

    def process(self, state: T) -> T:
        """
        执行pdf转换
        :param state: 图状态
        :return: 更新后的图状态（包含：md_path）
        """

        # 1.对参数校验
        import_file_path, file_dir_path = self._validate_state_inputs_path(state)

        # 2.利用MinerU解析pdf为md
        processed_code = self._execute_mineru(import_file_path, file_dir_path)
        if processed_code != 0:
            raise PdfConversionError("pdf转md失败", self.name)

        # 3.获取md的path
        md_path = self._get_md_paths(import_file_path, file_dir_path)

        # 4.更新state字典的md_path字段
        state["md_path"] = md_path

        # 5.返回更新后的state
        return state

    def _validate_state_inputs_path(self, state) -> Tuple[Path, Path]:
        """
        验证输入路径
        :param state: 该节点接收到的状态
        :return: (import_file_path_obj,file_dir_path_obj)元组
        """

        self.log_step("step1", "对状态的路径输入参数进行校验")

        # 1.获取pdf文件路径
        import_file_path = state.get("import_file_path", "")

        # 2.获取解析后的输出目录
        file_dir = state.get("file_dir", "")

        # 3.判断文件是否存在
        if not import_file_path:
            raise ValidationError("解析的文件不存在", self.name)

        # 4.用Path标准化路径
        import_file_path_obj = Path(import_file_path)

        # 5.校验是一个真实的路径
        if not import_file_path_obj.exists():
            raise FileProcessingError("解析的文件路径不是真实存在路径", self.name)

        # 6.判断输出目录是否为空,就取输入文件的目录作为输出目录
        if not file_dir:
            file_dir = import_file_path_obj.parent

        # 7.用Path标准化路径
        file_dir_obj = Path(file_dir)

        # 8.打印日志
        self.log_step(f"解析的pdf文件完成路径：{import_file_path}")
        self.log_step(f"解析后MD文件输出目录：{file_dir}")

        return (import_file_path_obj, file_dir_obj)  # 返回元组

    def _execute_mineru(self, import_file_path: Path, file_dir_path: Path) -> int:
        """
        执行mineru命令将pdf转换为md
        :param import_file_path: 解析的pdf文件全路径
        :param file_dir_path: 解析后md的存储目录
        :return: 命令执行结果状态码  0 表示成功
        """
        self.log_step("step2", "执行MinerU解析 PDF to MarkDown")

        # 1.构建命令
        # cmd = [ "mineru","-p",str(import_file_path),"-o",str(file_dir_path),"--source","local"]
        cmd = ["mineru", "-p", str(import_file_path), "-o", str(file_dir_path), "--backend", "pipeline", "--device", "cpu"]

        process_start_time = time.time()

        # 2.执行命令 （子进程执行命令）
        proc = subprocess.Popen(
            args=cmd,
            stdout=subprocess.PIPE,  # 子进程执行命令的日志输出回流
            stderr=subprocess.STDOUT,  # 子进程执行命令的错误日志输出回流
            errors="replace",  # 遇到乱码时替换
            text=True,  # 输出的内容是字符串，不是二级制字节
            encoding="utf-8",  # 指定中文字符串编码
            bufsize=1  # 按行缓存，只要缓冲区一行满了就输出，模拟实时效果
        )

        # 3.打印子进程日志信息
        for line in proc.stdout:
            self.logger.info(f"执行mineru产生的日志: {line}")

        # 4.等待子进程执行完成
        processed_code = proc.wait()

        process_end_time = time.time()

        if processed_code == 0:
            self.logger.info(
                f"执行mineru解析PDF文件成功{import_file_path.name}，耗时：{process_end_time - process_start_time:.2f}秒")
        else:
            self.logger.error(f"执行mineru解析PDF文件失败{import_file_path.name}，错误码processed_code：{processed_code}")

        # 返回状态码
        return processed_code

    def _get_md_paths(self, import_file_path, file_dir_path):
        """
        获取PDF解析成MD后的MD文件的实际路径
        :param import_file_path: 被解析的PDF文件路径，全路径(路径+文件名)
        :param file_dir_path: 指定的Pdf解析后的MD存储路径
        :return: 实际的MD文件全路径(路径+文件名)
        """
        # pdf文件的名称，不含扩展名和路径
        file_name = import_file_path.stem
        # D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\hak180产品安全手册\auto\hak180产品安全手册.md
        md_path = file_dir_path / file_name / "auto" / f"{file_name}.md"
        return str(md_path)


# *******************************************************************#
#                  测试                                              #
# *******************************************************************#

if __name__ == "__main__":
    setup_logging()
    pdf_to_md_node = PdfToMdNode()
    pdf_to_md_node_init_state = {
        "import_file_path": r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用.pdf",
        "import_file_path": r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用.pdf",
        "file_dir": r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir2"
    }
    processed_result = pdf_to_md_node.process(pdf_to_md_node_init_state)
    print(json.dumps(processed_result, indent=4, ensure_ascii=False))


"""
2026-05-31 22:07:08 - import.pdf_to_md_node - INFO - 执行mineru解析PDF文件成功万用表RS-12的使用.pdf，耗时：112.43秒
{
    "import_file_path": "D:\\workspace\\python\\PythonProject\\shopkeeper_brain\\knowledge\\processor\\import_process\\temp_dir\\万用表RS-12的使用.pdf",
    "file_dir": "D:\\workspace\\python\\PythonProject\\shopkeeper_brain\\knowledge\\processor\\import_process\\temp_dir",
    "md_path": "D:\\workspace\\python\\PythonProject\\shopkeeper_brain\\knowledge\\processor\\import_process\\temp_dir\\万用表RS-12的使用\\auto\\万用表RS-12的使用.md"
}
"""