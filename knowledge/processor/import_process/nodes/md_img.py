"""
MarkDown图片处理节点

将 MarkDownImageNode 中逻辑拆分为四个职责单一的协作类，统一调度
"""
import base64
import dataclasses
import logging
import re
import time
from collections import deque
from pathlib import Path
from typing import Tuple, Set, List, Optional, Dict, Deque

from openai import OpenAI

from knowledge.processor.import_process.base import BaseNode, setup_logging
from knowledge.processor.import_process.config import get_config
from knowledge.processor.import_process.exceptions import StateFieldError, FileProcessingError, ImageProcessingError
from knowledge.processor.import_process.state import ImportGraphState
from knowledge.utils.client.ai_clients import AIClients
from knowledge.utils.client.storage_clients import StorageClients


# -- 定义数据模型 --
# 未来直接实例化，不用写__init__  __repr__方法
@dataclasses.dataclass
class ImageContext:
    """
    图片在Markdown中上下文信息
    """
    heading: str
    pre_text: str  # 图片上方的正文内容
    post_text: str  # 图片下方的正文内容


@dataclasses.dataclass
class ImageInfo:
    """
    一张图片的完整信息
    """
    name: str  # 图片文件名，如“abc.jpg”   作为存储图片摘要的字典容器key
    path: str  # 图片完整路径，如“/home/user/abc.jpg”   vlm要用，minio要用
    context: ImageContext  # 图片在Markdown中的上下文信息   VLM要用


# -- 1.文件读写 & 备份 --
class MdFileHandler:
    """
    主要职责：
        1.读取md内容、md_path、图片日志
        2.备份新的md_content（方便测试观看）
    """

    def __init__(self, logger: logging.Logger, node_name: str):
        self.logger = logger
        self.node_name = node_name

    def read_md(self, state) -> Tuple[str, Path, Path]:

        md_path = state.get("md_path", "")
        if not md_path:
            raise StateFieldError(node_name=self.node_name, field_name="md_path", expected_type=str)
        """
        Path(md_path) 的作用是将字符串形式的文件路径转换为 pathlib.Path 对象，这样可以利用 Python 的 pathlib 模块提供的面向对象的路径操作方法。
        具体来说，在这段代码中：
        标准化路径处理：将字符串路径转换为 Path 对象后，可以使用统一的方法进行路径操作，而不必担心不同操作系统之间的路径分隔符差异（Windows 使用 \，Unix/Linux 使用 /）
        方便的文件系统操作：转换后的 md_path_obj 可以直接调用如 .exists()、.parent、.name 等属性和方法来检查文件是否存在、获取父目录、获取文件名等
        更安全的路径拼接：在第63行可以看到 image_dir = md_path_obj.parent / "images"，这里使用了 / 运算符来安全地拼接路径，避免了手动拼接字符串可能带来的问题
        跨平台兼容性：Path 对象会自动处理不同操作系统的路径格式，使代码更具可移植性
        这种处理方式比传统的字符串路径操作更加清晰、安全和易于维护。
        """
        md_path_obj = Path(md_path)  # Path标准化
        if not md_path_obj.exists():
            raise FileProcessingError(f"md文件路径无效：{md_path}", node_name=self.node_name)
        with open(md_path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
        image_dir = md_path_obj.parent / "images"
        return md_content, md_path_obj, image_dir

    def backup_md(self, md_path_obj: Path, new_md_content: str) -> str:
        self.logger.info(f"正在备份md文件：{md_path_obj}")
        new_file_path = md_path_obj.with_name(f"{md_path_obj.stem}_new{md_path_obj.suffix}")
        try:
            with open(new_file_path, "w", encoding="utf-8") as f:
                f.write(new_md_content)
            self.logger.info(f"备份成功：{new_file_path}")
        except IOError as e:
            self.logger.error(f"备份失败：{new_file_path}:{e}")
            raise ImageProcessingError(message=f"备份失败：{new_file_path}:{e}", node_name=self.node_name)
        return str(new_file_path)

# -- 2.图片扫描 & 上下文提取 --
class ImageScanner:
    """
    主要职责：
        1.根据图片目录，得到该目录下的有效的图片文件，目录和非图片排除
        2.去md文件中找到图片的位置
        3.获取该图片的上下文内容，给VLM模型提供图片上下文信息，帮助模型识别图片更加准确
        4.最终组装所有图片的上下文内容(List)
    """

    def __init__(self, logger):
        self.logger = logger

    def scan_img_dir(self, image_dir: Path, md_content: str, image_extensions: Set[str], context_length: int) -> List[
        ImageInfo]:
        """
        核心逻辑：
        1.扫描指定图片目录下的所有文件
        2.遍历每个图片去MD文件中获取位置
        2.1 获取上文信息
        2.2 获取下文信息
        3.将每个图片上下文放到最终封装ImageInfo的容器中
        4.将容器返回
        :param image_dir: 图片目录
        :param md_content: MD内容
        :param image_extensions: 扩展名
        :param context_length: 上下文的长度，各自最大长度不能超过200
        :return: List[ImageInfo]
        """
        image_list: List[ImageInfo] = []
        for img_path in Path(image_dir).iterdir():
            if not img_path.is_file():
                self.logger.warning(f"图片目录下存在非文件：{img_path}")
                continue
            if img_path.suffix.lower() not in image_extensions:
                self.logger.warning(f"图片目录下存在非图片文件：{img_path}")
                continue
            ctx = self._find_context(md_content, img_path.name, context_length)
            if ctx is None:
                self.logger.warning(f"MD文件中未找到图片：{img_path.name}的引用")
                continue
            image_list.append(ImageInfo(img_path.name, str(img_path), ctx))
        self.logger.info(f"找到了{len(image_list)}张图片")
        return image_list

    # def _find_context(self, md_content: str, img_name: str, max_chars: int = 200) -> ImageContext or None:
    def _find_context(self, md_content: str, img_name: str, max_chars: int = 200) -> Optional[ImageContext]:
        """找到图片在MD中第一次出现位置的上下文，找不到返回None"""
        pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(img_name) + r".*?\)")
        md_lines = md_content.split("\n")
        for line_idx, line in enumerate(md_lines):
            if not pattern.search(line):
                continue

            # 向上：找最近标题，取标题到图片之间的内容作为上文
            prev_title, prev_boundary = self._find_heading_above(md_lines, line_idx)
            pre_content = md_lines[prev_boundary + 1:line_idx]
            img_pre = self._extract_limited_context(pre_content, max_chars, direction="front")

            # 向下：找下一个标题，取图片到标题之间的内容作为下文
            next_boundary = self._find_heading_below(md_lines, line_idx)
            post_content = md_content[line_idx + 1: next_boundary]
            img_post = self._extract_limited_context(post_content, max_chars, direction="end")

            # 返回图片上下文信息
            return ImageContext(
                heading=prev_title,  # 标题
                pre_text=img_pre,  # 上文
                post_text=img_post  # 下文
            )
        return None

    # 静态方法参数不能有self,否则导致参数数量不匹配
    @staticmethod
    def _find_heading_above(md_lines: List[str], from_idx: int) -> Tuple[str, int]:
        """从from_idx向上查找最近的标题"""
        """
        range(from_idx - 1, -1, -1) 生成一个递减的索引序列,用于反向遍历:
        起始值: from_idx - 1 (从指定位置的前一个元素开始)
        结束值: -1 (不包含-1,实际到索引0停止)
        步长: -1 (每次递减1,向前遍历)
        示例: 若 from_idx = 5,则生成序列 [4, 3, 2, 1, 0],实现从后往前查找。
        """
        for i in range(from_idx - 1, -1, -1):
            if re.match(r"^#{1,6}\s+", md_lines[i]):
                return md_lines[i], i
        return "", -1

    @staticmethod
    def _find_heading_below(md_lines: List[str], from_idx: int) -> int:
        """从from_idx向下查找下一个标题"""
        for i in range(from_idx + 1, len(md_lines), 1):
            # Python 3.12+ 对正则表达式中的转义序列检查更严格。\s 在普通字符串中会被识别为无效转义序列，应使用原始字符串（raw string）避免此警告。
            if re.match(r"^#{1,6}\s+", md_lines[i]):
                return i
        return len(md_lines)

    @staticmethod
    def _extract_limited_context(pre_content: List[str], max_chars: int, direction: str) -> str:
        """按段落分割，按direction方向贪心装填，保持段落完整性"""
        """
        这个函数用于从Markdown文本中提取有限长度的上下文内容,保持段落完整性。
            工作流程:
            1. 段落分割阶段
            遍历所有行,识别空白行或其他图片标记(![...](...))作为段落分隔符
            将连续的非空行组合成一个段落
            所有段落存入 paragraphs 列表
            2. 方向处理
            direction == "front": 向前提取(图片上方的内容),需要反转段落顺序
            其他方向: 向后提取(图片下方的内容),保持原顺序
            3. 贪心装填阶段
            按段落顺序累加,直到总字符数超过 max_chars
            保证段落完整性,不会截断段落
            如果已有选中段落且超出限制,则停止添加
            4. 结果组装
            如果是向前提取,再次反转选中的段落恢复正确顺序
            用双换行符 \n\n 连接所有选中段落并返回
        """
        current_paragraph: List[str] = []  # 临时存储当前正在构建的段落的行
        paragraphs: List[str] = []  # 存储所有已完成的段落

        for line in pre_content:
            is_blank_line = not line.strip()
            is_other_image = re.match(r"^!\[.*?\]\(.*?\)$", line.strip())
            if is_blank_line or is_other_image:
                if current_paragraph:
                    paragraphs.append("\n".join(current_paragraph))
                    current_paragraph = []
                continue
            current_paragraph.append(line)
        if current_paragraph:
            paragraphs.append("\n".join(current_paragraph))
        if direction == "front":
            paragraphs.reverse()  # 就近优先

        total = 0  # 累计字符数
        selected: List[str] = []  # 存储选中的段落

        for para in paragraphs:
            if total + len(para) > max_chars and selected:
                break
            selected.append(para)
            total += len((para))

        if direction == "front":
            selected.reverse()  # 与原文顺序一致

        return "\n\n".join(selected)  # 折行并空行


# -- 3.VLM 图片摘要生成 --
class VLMSummarizer:
    """
    主要职责：
        主要根据图片和图片上下文，让VLM生成图片摘要识别
    """

    def __init__(self, logger):
        self.logger = logger

    # 返回    图片名称  和  图片摘要  的字典
    def summarize_all(self, document_title: str, image_list: List[ImageInfo], vl_model: str,
                      requests_per_minute: int) -> Dict[str, str]:
        summaries: Dict[str, str] = {}
        requests_timestamps: Deque[float] = deque()

        try:
            client = AIClients.get_openai()
        except Exception as e:
            self.logger.warning(f"VLM不可用,跳过图片摘要生成:{e}")
            for img in image_list:
                summaries[img.name] = "图片描述默认值"
            return summaries

        for img in image_list:
            self._enforce_rate_limit(requests_timestamps, requests_per_minute)
            summaries[img.name] = self._summarize_one(client, vl_model, document_title, img)
        self.logger.info(f"生成{len(summaries)}张图片摘要")
        return summaries

    def _summarize_one(self, client: OpenAI, vl_model: str, document_title: str, img: ImageInfo) -> str:
        """
        调用VLM模型，获取图片摘要
        :param client: VLM模型客户端对象
        :param vl_model: 模型名称
        :param document_title: md文件名称
        :param img: ImageInfo  图片信息
        :return: 摘要信息
        """

        # 使用列表推导式从图片上下文的三个属性中筛选出非空字符串。
        parts = [p for p in (img.context.heading, img.context.pre_text, img.context.post_text) if p]
        final_context = "\n".join(parts) if parts else "暂无可用上下文"
        try:
            with open(img.path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return "暂无图片"

        try:
            resp = client.chat.completions.create(
                model=vl_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"任务：为Markdown文档中的图片生成一个简短的中文标题。\n"
                                f"背景信息：\n"
                                f"  1. 所属文档标题：\"{document_title}\"\n"
                                f"  2. 图片上下文：{final_context}\n"
                                f"请结合图片内容和上述上下文信息，"
                                f"用中文简要总结这张图片的内容，"
                                f"生成一个精准的中文标题（不要包含图片二字）。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}"
                            },
                        },
                    ],
                }],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            self.logger.warning(f"图片摘要生成失败 {img.path}: {e}")
            return "图片描述"

    def _enforce_rate_limit(self, timestamps: Deque[float], max_requests: int, window: int = 60):
        """
        欢动窗口速率限制算法，用于控制API请求频率
        :param timestamps:   双端队列，存储每次请求的时间戳，Deque支持高效的头部删除和尾部添加操作
        :param max_requests:  最大的请求数量。最多每分钟处理图片摘要的请求数量。超过限制时自动暂停
        :param window:  时间窗口 默认60秒，一分钟。只保留最近60秒内的请求。
        """
        # 获取当前系统时间
        now = time.time()
        # 当前队列不为空，而且队列中的第一个时间戳超过了时间窗口，则删除队列中的第一个时间戳
        while timestamps and now - timestamps[0] >= window:
            timestamps.popleft()
        # 档期队列长度超过最大请求数量，则暂停一段时间
        if len(timestamps) >= max_requests:
            # 等待时间 = 时间窗口 - (当前时间 - 第一个时间戳)
            sleep_duration = window - (now - timestamps[0])
            if sleep_duration > 0:
                self.logger.info(f"达到速率限制，暂停{sleep_duration:.2f}秒...")
                time.sleep(sleep_duration)
            # 重新清理并记录
            # 休眠后再次清理过期时间戳
            now = time.time()
            while timestamps and now - timestamps[0] >= window:
                timestamps.popleft()
        # 将当前请求时间加入队列
        timestamps.append(now)


# -- 4.MinIO上传 & 内容替换--
class ImageUploader:
    """
    主要职责：
        1.将本地图片上传到Minio,得到Minio上图片的访问地址
        2.替换 md图片的地址
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def upload_and_replace(self, document_name, md_content, images_summaries, image_list, minio_bucket,
                           minio_base_url) -> str:
        """
        MinIO上传，正则替换MD内容。返回新的MD文档内容
        :param document_name:  MD文档名称
        :param md_content:  MD文档内容
        :param images_summaries:  图片-摘要
        :param image_list: 图片列表
        :param minio_bucket: 桶
        :param minio_base_url: MinIO的地址
        :return: 新的MD内容
        """
        remote_urls = self._upload_all(document_name, image_list, minio_bucket, minio_base_url)

        new_md_content = self._replace_in_md(md_content, images_summaries, remote_urls)

        return new_md_content

    def _upload_all(self, document_name: str, image_list: List[ImageInfo], minio_bucket: str, minio_base_url: str) -> \
            List[str]:
        """上传图片"""
        remote_urls: Dict[str, str] = {}
        try:
            minio_client = StorageClients.get_minio_client()
        except Exception as e:
            self.logger.warning(f"MinIO不可用,所有图片保留本地路径：{e}")
            for img in image_list:
                remote_urls[img.name] = img.path
            return remote_urls

        for img in image_list:
            object_name = f"{document_name}/{img.name}"
            try:
                minio_client.fput_object(minio_bucket, object_name, img.path)
                remote_url = (f"{minio_base_url}/{minio_bucket}/{object_name}")
                self.logger.info(f"图片上传成功：{img.name}")
                remote_urls[img.name] = remote_url
            except Exception as e:
                self.logger.warning(f"图片上传失败：{img.name},保留本地路径")
                remote_urls[img.name] = img.path
        self.logger.info(f"成功上传{len(remote_urls)}张图片到MinIO")
        return remote_urls

    def _replace_in_md(self, md_content: str, images_summaries: Dict[str, str], remote_urls: List[str]) -> str:
        """替换MD中图片引用为远程URL + 摘要"""
        pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")

        def replacer(match: re.Match) -> str:
            original_path = match.group(2).strip()
            file_name_in_md = Path(original_path).name
            for img_name, summery in images_summaries.items():
                if file_name_in_md == img_name:
                    return f"![{summery}]({remote_urls[img_name]})"
            return match.group(0)  # 如果没有找到匹配的图片，返回原始匹配的完整字符串（即保持不变）。

        # 使用 pattern.sub() 方法对 md_content 进行替换，对所有匹配的图片调用 replacer 函数，返回处理后的完整 Markdown 文本。
        return pattern.sub(replacer, md_content)


# --定义主节点--
class MarkDownImageNode(BaseNode):
    """
    编排调度
    """
    name = "md_img_node"

    def __init__(self):
        super().__init__()
        self.file_handler = MdFileHandler(self.logger, self.name)
        self.scanner = ImageScanner(self.logger)
        self.summarizer = VLMSummarizer(self.logger)
        self.uploader = ImageUploader(self.logger)

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        处理逻辑，主要职责：
            1.得到四个类的实例对象
            2.分别调用四个实例对象的处理方法
        """

        config = get_config()

        self.log_step("step1", "读取MD文件内容,路径以及图片的目录...")
        # 1.读取文件,如果没有图片路径，直接返回内容
        md_content, md_path_obj, image_dir = self.file_handler.read_md(state)
        if not image_dir.exists():
            self.logger.warning(f"文件{md_path_obj.name}暂无图片要处理")
            state['md_content'] = md_content
            return state

        # 2.扫描图片 & 提取上下文
        self.log_step("step2", "准备开始扫描图片目录")
        image_list: List[ImageInfo] = self.scanner.scan_img_dir(image_dir, md_content,
                                                                image_extensions=config.image_extensions,
                                                                context_length=config.img_content_length)

        # 3.VLM生成摘要
        self.log_step("step3", "VLM生成图片摘要")
        summaries = self.summarizer.summarize_all(
            document_title=md_path_obj.name,  # MD文件名称
            image_list=image_list,  # MD中图片列表
            vl_model=config.vl_model,  # VLM模型名称
            requests_per_minute=config.requests_per_minute  # 每分钟请求次数限制
        )
        print(summaries)

        """
        {'01ff135dc95789f7cb428c34df92a77869db4f4e70b83d663d1c485a17e416c1.jpg': '万用表RS-12直流电流测量接线示意图（10A档位）', 
        '10d2f007e02047a07d46e75a81db7f96811916c0f5ff662fa23ce215dadcbbe1.jpg': '蜂鸣器功能符号指示', 
        '115adcddd73aeacbccd21861a542e8c23f78937f8680317548ea8393bcb0801b.jpg': '中文说明书标识', 
        '347706d8e5045d76f78334438c01c4b148a953dfe5c5f2f33b1fd269c1be2b1e.jpg': '最大量程接线端子标识', 
        '3e257858115a629b9112ea2e2c75344a2c2d01f2e6e110ab28d41809719fc433.jpg': '交流电压测量时表笔正确连接至被测电路的示意图', 
        '632c904bcd8e56179b983586935012e73ba69ee4aa5182e0afd784c11dd24816.jpg': '直流电流测量接线示意图（注意10A档位测量时间不超过30秒）', 
        '7c6088f1ec1b6fa8cb22a3cb79e54c078a31eedca587efda91bb8e8c14021df5.jpg': '万用表RS-12各部件标识示意图', 
        '9cfeb4ba44a7b657a15c5adae9ef70dbe187ae36f6a29b51ff71406e133b2f74.jpg': '安全警示标志', 
        '9e644c97f29cff6b9e2c1e64c7c4ccfddbf01e67dbf9ba2441f312db1b509f83.jpg': '高压危险警示符号', 
        'b3c6d4adad3a88b2cffb81c839603e1da5d0c88856602c66e02c91ec28ff2a89.jpg': '安全标识符号示意图', 
        'c71754d5d170bdaf9ef786ead1e68e3236f35d0de513bbcebe36b701a6a9543f.jpg': 'RS-12数字万用表正面面板结构示意图', 
        'c9b6e9c07a46004ce4b65c5bfcb1e9007526352174e4354f0a60ba812f2e62d2.jpg': 'RS PRO品牌标识', 
        'de9dde2732fe81a213e8fd32e98b790548145c7c796ec443d5f6f0cb576cd3e1.jpg': '万用表电阻测量接线示意图'}
        """

        # 4.上传& 替换
        self.log_step("step4", "上传和替换MD图片")
        new_md_content = self.uploader.upload_and_replace(
            document_name=md_path_obj.stem,  # MD文件名称，不含扩展名
            md_content=md_content,  # MD文件内容
            images_summaries=summaries,  # 图片摘要  图片名称=图片摘要
            image_list=image_list,  # 图片列表
            minio_bucket=config.minio_bucket,  # MinIO存储桶名称
            minio_base_url=config.get_minio_base_url(),  # MinIO访问地址
        )

        # 5.备份
        self.file_handler.backup_md(md_path_obj, new_md_content)

        # 6.更新并返回
        state["md_content"] = new_md_content

        return state


if __name__ == "__main__":
    """
    测试
    """
    setup_logging()
    node = MarkDownImageNode()
    state = {
        "md_path": r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto\万用表RS-12的使用.md"
    }
    node.process(state)
