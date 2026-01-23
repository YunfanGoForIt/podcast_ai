"""
Markdown 笔记生成器
结果转换为格式化的Markdown笔记
将播客解析"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class MarkdownNoteGenerator:
    """Markdown 笔记生成器"""

    def __init__(self, output_dir: str = "./notes"):
        """
        初始化生成器

        Args:
            output_dir: 笔记输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        audio_name: str,
        parsed_data: Dict[str, Any],
        llm_notes: Dict[str, Any],
        metadata: Optional[Dict] = None
    ) -> str:
        """
        生成完整的Markdown笔记

        Args:
            audio_name: 音频文件名
            parsed_data: 解析后的转写数据
            llm_notes: LLM生成的笔记
            metadata: 额外元数据

        Returns:
            Markdown内容
        """
        # 构建笔记文件名
        date_str = datetime.now().strftime("%Y%m%d")
        base_name = Path(audio_name).stem
        note_filename = f"{date_str}_{base_name}_笔记.md"

        # 准备章节内容
        chapters_content = self._generate_chapters_content(parsed_data, llm_notes)

        # 准备金句内容
        quotes_content = self._generate_quotes_content(parsed_data)

        # 构建完整Markdown
        markdown = f"""# 播客笔记：{base_name}

> 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 概览

- **音频文件**：{audio_name}
- **关键词**：{', '.join(parsed_data.get('keywords', []))}

### 播客摘要
{parsed_data.get('summary', '暂无摘要')}

---

## 章节速览

| 章节 | 标题 | 时间范围 |
|------|------|----------|
{self._generate_chapter_table(parsed_data.get('chapters', []))}

---

{self._format_llm_notes(llm_notes)}

---

## 完整逐字稿

### 说话人列表
{self._format_speakers(parsed_data)}

### 对话内容
{self._format_transcription(parsed_data.get('transcription', []))}

---

> 💡 **提示**：本笔记由AI自动生成，如有错误请人工校对。

"""

        # 保存笔记
        output_path = self.output_dir / note_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"笔记已保存至: {output_path}")
        return str(output_path)

    def _generate_chapters_content(
        self,
        parsed_data: Dict[str, Any],
        llm_notes: Dict[str, Any]
    ) -> str:
        """生成章节内容"""
        chapters = parsed_data.get('chapters', [])
        llm_chapters = llm_notes.get('chapters', [])

        content = []
        for i, chapter in enumerate(chapters):
            llm_chapter = llm_chapters[i] if i < len(llm_chapters) else {}

            chapter_content = f"""### {i+1}. {chapter.get('title', f'章节 {i+1}')}

**时间**：{chapter.get('timeline', '未知')}

**章节描述**：{chapter.get('desc', '暂无描述')}

"""
            # 添加LLM总结
            if llm_chapter.get('content'):
                chapter_content += f"**内容总结**：\n{llm_chapter['content'].strip()}\n\n"

            # 添加金句
            quotes = llm_chapter.get('quotes', [])
            if quotes:
                chapter_content += "**嘉宾金句**：\n"
                for quote in quotes:
                    chapter_content += f"> {quote}\n\n"

            # 添加关键要点
            key_points = llm_chapter.get('key_points', [])
            if key_points:
                chapter_content += "**关键要点**：\n"
                for point in key_points:
                    chapter_content += f"- {point}\n"
                chapter_content += "\n"

            content.append(chapter_content)

        return "\n".join(content)

    def _generate_quotes_content(self, parsed_data: Dict[str, Any]) -> str:
        """生成金句汇总"""
        transcription = parsed_data.get('transcription', [])

        # 按章节提取金句
        quotes_by_chapter = {}
        for item in transcription:
            text = item.get('text', '').strip()
            # 简单的启发式：金句通常较短（<100字）且有一定价值
            if 10 < len(text) < 150 and any(marker in text for marker in ['我认为', '我觉得', '重要的是', '其实', '也就是说', '大家', '所以']):
                speaker = item.get('speaker', '未知')
                quotes_by_chapter.setdefault(speaker, []).append(text)

        content = []
        for speaker, quotes in quotes_by_chapter.items():
            content.append(f"**{speaker}**：\n")
            for quote in quotes[:5]:  # 每位说话人最多5条金句
                content.append(f"> {quote}\n")
            content.append("\n")

        return "\n".join(content) if content else "暂无金句记录"

    def _generate_chapter_table(self, chapters: List[Dict]) -> str:
        """生成章节表格"""
        rows = []
        for i, chapter in enumerate(chapters):
            title = chapter.get('title', f'章节 {i+1}')
            timeline = chapter.get('timeline', '未知')
            rows.append(f"| {i+1} | {title} | {timeline} |")

        return "\n".join(rows) if rows else "| 暂无章节信息 |"

    def _format_llm_notes(self, llm_notes: Dict[str, Any]) -> str:
        """格式化LLM生成的笔记"""
        if not llm_notes.get('markdown'):
            return ""

        return f"""## AI 智能总结

{llm_notes['markdown']}
"""

    def _format_speakers(self, parsed_data: Dict[str, Any]) -> str:
        """格式化说话人列表"""
        speakers = parsed_data.get('speakers', set())
        if not speakers:
            return "暂无说话人信息"

        lines = []
        for speaker in sorted(speakers):
            lines.append(f"- **{speaker}**")
        return "\n".join(lines)

    def _format_transcription(self, transcription: List[Dict]) -> str:
        """格式化逐字稿"""
        if not transcription:
            return "暂无逐字稿内容"

        lines = []
        for item in transcription:
            speaker = item.get('speaker', '未知')
            text = item.get('text', '')
            start_time = item.get('start_time', 0)
            end_time = item.get('end_time', 0)

            # 格式化时间
            start_str = self._format_time(start_time)
            end_str = self._format_time(end_time)

            lines.append(f"**[{speaker}]** ({start_str} - {end_str})")
            lines.append(f"{text}\n")

        return "\n".join(lines)

    def _format_time(self, seconds: int) -> str:
        """格式化时间（秒 -> MM:SS 或 HH:MM:SS）"""
        if seconds < 0:
            return "00:00"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
