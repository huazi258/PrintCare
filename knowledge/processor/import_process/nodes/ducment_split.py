import sys
import atexit


def _patch_multiprocess_resource_tracker():
    try:
        from multiprocess.resource_tracker import ResourceTracker
        _original_del = ResourceTracker.__del__

        def _safe_del(self):
            try:
                _original_del(self)
            except (AttributeError, TypeError):
                pass

        ResourceTracker.__del__ = _safe_del
    except ImportError:
        pass


atexit.register(_patch_multiprocess_resource_tracker)


import json
import os
import re
from typing import Tuple, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from knowledge.processor.import_process.base import BaseNode, setup_logging
from knowledge.processor.import_process.config import get_config
from knowledge.utils.markdown_util import MarkdownTableLinearizer


class DocumentSplitNode(BaseNode):
    """
    文档切分节点
    处理流程：
        1.读md内容, 参数校验, 换行符统计
        2.按标题切割
    """

    name = "document_split_node"

    def process(self, state: dict) -> dict:
        # 获取配置
        config = get_config()

        # 1.校验参数
        md_content, file_title, max_content_length, min_content_length = self._validate_state(state, config)

        # 2.根据标题切割，得到段落
        sections = self._split_by_headings(md_content, file_title)

        # 3.切分与合并
        final_chunks = self._split_and_merge(sections, max_content_length, min_content_length)

        # 4.组装
        chunks = self._assemble_chunks(final_chunks)

        # 5.更新state
        state['chunks'] = chunks

        # 6.备份
        self._backup_chunks(state, chunks)

        # 返回状态
        return state

    def _validate_state(self, state, config) -> Tuple[str, str, int, int]:
        """
        校验参数,换行符统一
        :param state:
        :param config:
        :return:
        """
        # 1.打印日志
        self.log_step("step1", "参数校验以及获取文档内容")

        # 2.获取文档内容
        md_content = state.get("md_content")

        # 3.统一换行符
        if md_content:
            md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")

        # 4.获取文件标题
        file_title = state.get("file_title")

        # 5.校验最大最小值 不能小于0，而且min < max   ValueError
        if config.max_content_length < 0 or config.min_content_length < 0 or config.min_content_length > config.max_content_length:
            raise ValueError(f"切片长度参数校验失败，请检查参数配置")

        # 6.返回数据
        return md_content, file_title, config.max_content_length, config.min_content_length

    def _split_by_headings(self, md_content, file_title) -> List[dict]:
        """
        根据 h1 - h6 标题切分
        :param md_content:
        :param file_title:
        :return:
            sections: 列表，每个元素格式
            {
                "title": "# 第一章",
                "body": "正文内容...",
                "file_title": "万用表",
                "parent_title": "# 第一章"
            }
        """
        self.log_step("step2", "按照标题开始切分文档")

        # 1.定义变量
        in_fence = False  # 是否在代码围栏中
        hierarchy = [""] * 7  # 7个长度，第一个为空
        body_line = []
        sections = []
        current_title = ""
        current_level = 0

        # 2.定义正则表达式
        heading_re = re.compile(r"^\s*(#{1,6})\s+(.+)")

        # 3.切分
        content_lines = md_content.split("\n")

        def _flush():
            """封装section对象"""
            body = "\n".join(body_line)
            if current_title or body:
                parent_title = ""
                # 获取父级标题
                for i in range(current_level - 1, 0, -1):
                    if hierarchy[i]:
                        parent_title = hierarchy[i]
                        break
                if not parent_title:
                    parent_title = current_title if current_title else file_title
                return sections.append({
                    "title": current_title if current_title else file_title,
                    "body": body,
                    "file_title": file_title,
                    "parent_title": parent_title
                })

        for content_line in content_lines:

            # 判断是否存在代码围栏
            if content_line.strip().startswith("```") or content_line.strip().endswith("~~~"):
                in_fence = not in_fence

            # 匹配标题
            match = heading_re.match(content_line) if not in_fence else None
            if match:
                _flush()
                level = len(match.group(1))  # 标题级别
                current_level = level
                current_title = content_line
                hierarchy[level] = current_title

                # 清空下级标题
                for i in range(level + 1, 7):
                    hierarchy[i] = ""  # 不管是否有数据直接清空，不用做判断

                body_line = []
            else:
                # 除了标题行以外全部收集起来
                body_line.append(content_line)

        _flush()

        return sections

    def _split_and_merge(self, sections, max_content_length, min_content_length):
        # 1.先切长的
        current_sections = []
        for section in sections:
            # 使用extend将切分结果合并到current_sections列表
            current_sections.extend(self.split_long_section(section, max_content_length))

        # 2.再合并短的
        final_sections = self.merge_short_section(current_sections, min_content_length)

        return final_sections

    def split_long_section(self, section, max_content_length) -> List[dict]:
        self.log_step("step3","切长的")
        # 1.获取section的属性
        title = section.get("title")
        body = section.get("body")
        file_title = section.get("file_title")
        parent_title = section.get("parent_title")

        # 2.表格降维处理
        if '<table>' in body:
            self.logger.info("***** 表格降维处理 *****")
            body = MarkdownTableLinearizer.process(body)
            section['body'] = body
            self.logger.info(f"{body}")

        # 3.标题过长截断
        if len(title) > 50:
            title = title[:50]

        # 4.计算总长度
        title_prefix = f"{title}\n\n"
        total_length = len(title_prefix) + len(body)

        # 5.不超过阈值，无需切分
        if total_length <= max_content_length:
            return [section]

        # 6.计算body可用空间
        body_length = max_content_length - len(title_prefix)
        if body_length <= 0:
            return [section]

        # 7.递归切分
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=body_length,  # 每块最大长度
            chunk_overlap=0,  # 块之间无重叠
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],  # 按优先级尝试分隔符（段落→句子→标点→空格）
            keep_separator=False  # 不保留分隔符
        )
        texts = text_splitter.split_text(body)  # 得到列表
        if len(texts) == 1:
            return [section]

        # 8.生成子section
        sub_sections = []
        for index, text in enumerate(texts):  # 返回(index, text)元组
            sub_sections.append({
                "title": f"{title} - {index + 1}",  # 标题带序号
                "body": text,
                "file_title": file_title,
                "parent_title": parent_title
            })
        return sub_sections

    def merge_short_section(self, current_sections, min_content_length):
        self.log_step("step4","合并短的")
        """贪心累加算法：将同源的短section合并"""
        # 1.初始化
        current_section = current_sections[0]
        final_sections = []

        # 2.遍历集合
        for next_section in current_sections[1:]:
            same_parent = current_section['parent_title'] == next_section['parent_title']
            if same_parent and len(current_section.get("body").rstrip()) < min_content_length:
                current_section['body'] = current_section.get("body").rstrip() + "\n\n" + next_section.get(
                    "body").lstrip()
                current_section['title'] = current_section['parent_title']
            else:
                final_sections.append(current_section)
                current_section = next_section

        # 3.最后一个封箱
        final_sections.append(current_section)

        return final_sections

    def _assemble_chunks(self, final_chunks):
        self.log_step("step5", "组合标题和内容")
        """
        最终组合 chunks
        :param final_chunks:
        :return:
        """
        chunks = []

        for chunk in final_chunks:
            chunks.append({
                "title": chunk.get("title"),
                "file_title": chunk.get("file_title"),
                "parent_title": chunk.get("parent_title"),
                "content": f"{chunk.get('title')}\n\n{chunk.get('body')}"
            })
        return chunks

    def _backup_chunks(self, state, chunks):
        self.log_step("step6", "组合标题和内容")
        """
        将切分结果备份到json文件
        :param state:
        :param chunks:
        :return:
        """
        local_dir = state.get("file_dir", "")
        if not local_dir:
            return

        os.makedirs(local_dir, exist_ok=True) #exist_ok=True：如果目录已存在，不会抛出异常，直接跳过
        output_path = os.path.join(local_dir, "chunks.json")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.warning(f"备份失败：{e}")


if __name__ == '__main__':


    setup_logging()

    node = DocumentSplitNode()
    file_path = r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto\万用表RS-12的使用_new.md"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    state = {
        "file_title": "万用表的使用",
        "md_content": content,
        "file_dir": r"D:\workspace\python\PythonProject\shopkeeper_brain\knowledge\processor\import_process\temp_dir\万用表RS-12的使用\auto"
    }

    node.process(state)
