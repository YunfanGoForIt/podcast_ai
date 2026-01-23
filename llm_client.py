"""
LLM 客户端
支持多种模型提供商：OpenAI, Azure, Anthropic 等
"""
import json
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM 提供商基类"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        发送对话请求

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            模型生成的文本
        """
        pass


class OpenAIClient(LLMProvider):
    """OpenAI API 客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config['api_key']
        self.base_url = config.get('base_url', 'https://api.openai.com/v1')
        self.model = config.get('model', 'gpt-4o')
        self.client = None

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            print("openai 库未安装，将使用 requests 方式调用")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送对话请求"""
        # 设置默认 max_tokens（如果未提供）
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = 4096

        if self.client:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        else:
            # 使用 requests 方式调用
            import requests

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "messages": messages,
                **kwargs
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']


class AzureClient(LLMProvider):
    """Azure OpenAI API 客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config['api_key']
        self.base_url = config.get('base_url', '')
        self.deployment = config.get('deployment', 'gpt-4o')
        self.api_version = config.get('api_version', '2024-02-15-preview')
        self.client = None

        try:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.base_url,
                api_version=self.api_version
            )
        except ImportError:
            print("openai 库未安装，将使用 requests 方式调用")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送对话请求"""
        # 设置默认 max_tokens（如果未提供）
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = 4096

        if self.client:
            response = self.client.chat.completions.create(
                deployment_id=self.deployment,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        else:
            import requests

            headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json"
            }

            params = {"api-version": self.api_version}

            data = {
                "messages": messages,
                **kwargs
            }

            response = requests.post(
                f"{self.base_url}/openai/deployments/{self.deployment}/chat/completions",
                params=params,
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']


class AnthropicClient(LLMProvider):
    """Anthropic Claude API 客户端（使用 Anthropic 标准格式）"""

    def __init__(self, config: Dict[str, Any]):
        self.api_key = config['api_key']
        self.base_url = config.get('base_url', 'https://api.anthropic.com')
        self.model = config.get('model', 'claude-sonnet-4-5-20251101')
        self.client = None

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            print("anthropic 库未安装，将使用 requests 方式调用")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送对话请求（使用 Anthropic 标准格式）"""
        # 设置默认 max_tokens（如果未提供）
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = 4096

        # 将 OpenAI 格式的消息转换为 Anthropic 格式
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_prompt = msg['content']
            else:
                anthropic_messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })

        if self.client:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=anthropic_messages,
                **kwargs
            )
            return response.content[0].text
        else:
            import requests

            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }

            data = {
                "model": self.model,
                "messages": anthropic_messages,
                **kwargs
            }

            if system_prompt:
                data["system"] = system_prompt

            response = requests.post(
                f"{self.base_url}/v1/messages",
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()['content'][0]['text']


class LLMManager:
    """LLM 管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.provider = config.get('provider', 'openai')
        self.client = self._create_client(config)

    def _create_client(self, config: Dict[str, Any]) -> LLMProvider:
        """创建客户端"""
        if self.provider == 'openai':
            return OpenAIClient(config)
        elif self.provider == 'azure':
            return AzureClient(config)
        elif self.provider == 'anthropic':
            return AnthropicClient(config)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.provider}")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送对话请求"""
        return self.client.chat(messages, **kwargs)

    def generate_podcast_notes(
        self,
        transcription: List[Dict],
        chapters: List[Dict],
        summary: str,
        keywords: List[str],
        prompt_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成播客笔记（两步流程）

        第一步：分段和整体概括
        第二步：逐段生成详细笔记

        Args:
            transcription: 逐字稿（必须包含 start_time, end_time, text 字段）
            chapters: 章节信息（可选，如果ASR提供了章节）
            summary: 初步摘要（可选）
            keywords: 关键词（可选）
            prompt_template: 自定义提示词模板（第二步使用）

        Returns:
            生成的完整笔记
        """
        # 第一步：分段和整体概括
        segmentation = self.segment_podcast(transcription)

        if not segmentation.get('success'):
            return {
                'error': segmentation.get('error', '分段失败'),
                'markdown': ''
            }

        # 第二步：为每个分段生成详细笔记
        section_notes = []
        overall_summary = segmentation['overall_summary']

        for i, segment in enumerate(segmentation['segments']):
            print(f"[LLM] 正在生成第 {i+1}/{len(segmentation['segments'])} 段的笔记...")
            note = self.generate_segment_notes(
                segment=segment,
                transcription=transcription,
                overall_summary=overall_summary
            )
            section_notes.append({
                'segment': segment,
                'note': note
            })

        # 合并所有笔记为完整Markdown
        full_markdown = self._merge_notes(overall_summary, section_notes)

        return {
            'overall_summary': overall_summary,
            'segments': segmentation['segments'],
            'section_notes': section_notes,
            'markdown': full_markdown
        }

    def segment_podcast(self, transcription: List[Dict]) -> Dict[str, Any]:
        """
        第一步：将播客分段并生成整体概括

        Args:
            transcription: 逐字稿列表，每个元素包含 {start_time, end_time, text}

        Returns:
            {
                'success': bool,
                'overall_summary': str,  # 约600字的整体概括
                'segments': [  # 分段列表
                    {
                        'title': str,  # 段落标题
                        'start_time': float,  # 开始时间（秒）
                        'end_time': float,  # 结束时间（秒）
                        'description': str  # 段落简短描述
                    }
                ]
            }
        """
        # 准备带时间戳的文本（格式化为可读格式）
        timestamped_text = self._format_transcription_with_timestamps(transcription)

        # 计算音频总时长，估算分段数量（每小时约5段）
        total_duration = transcription[-1].get('end_time', 0) if transcription else 0
        estimated_segments = max(5, int(total_duration / 720))  # 720秒 = 12分钟一段

        messages = [
            {
                "role": "system",
                "content": """你是一位专业的播客内容分析师，擅长理解播客的话题结构和内容流向。
你的任务是根据播客内容的自然话题边界，将整个播客合理地分为若干段，并给出整体概括。"""
            },
            {
                "role": "user",
                "content": f"""请分析以下播客逐字稿，完成两个任务：

**任务1：生成整体概括**
请用约600字概括整个播客的核心内容、主要观点和关键信息。

**任务2：分段**
根据内容的话题变化和自然边界，将播客分为 {estimated_segments} 段左右（每小时约5段）。
每段应该是一个相对完整的话题或讨论单元。

## 播客逐字稿（带时间戳）

{timestamped_text}

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
  "overall_summary": "整体概括内容（约600字）",
  "segments": [
    {{
      "title": "第一段的标题",
      "start_time": 0.0,
      "end_time": 720.5,
      "description": "这段讨论的核心内容简述"
    }},
    {{
      "title": "第二段的标题",
      "start_time": 720.5,
      "end_time": 1440.0,
      "description": "这段讨论的核心内容简述"
    }}
  ]
}}
```

注意事项：
1. start_time 和 end_time 要精确到秒，必须对应实际播客中的时间点
2. 分段要根据话题的自然边界，不要在句子中间切断
3. 每段应该是一个相对完整的话题讨论
4. 时间戳格式为数字（秒数），不要用字符串
"""
            }
        ]

        try:
            response = self.chat(messages, temperature=0.5)
            # 尝试从响应中提取JSON
            json_str = self._extract_json(response)

            if not json_str:
                return {
                    'success': False,
                    'error': '无法从响应中提取有效的JSON'
                }

            result = json.loads(json_str)

            return {
                'success': True,
                'overall_summary': result.get('overall_summary', ''),
                'segments': result.get('segments', []),
                'raw_response': response
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'分段失败: {str(e)}'
            }

    def generate_segment_notes(
        self,
        segment: Dict[str, Any],
        transcription: List[Dict],
        overall_summary: str
    ) -> str:
        """
        第二步：为单个分段生成详细笔记

        Args:
            segment: 分段信息 {title, start_time, end_time, description}
            transcription: 完整的逐字稿
            overall_summary: 整体概括

        Returns:
            该分段的Markdown笔记
        """
        # 提取该分段对应的对话内容
        segment_transcription = self._extract_segment_transcription(
            transcription,
            segment['start_time'],
            segment['end_time']
        )

        # 格式化为可读文本
        segment_text = "\n".join([
            f"[{t.get('start_time', 0):.1f}s] {t.get('text', '')}"
            for t in segment_transcription
        ])

        messages = [
            {
                "role": "system",
                "content": """你是一位专业的播客内容编辑，擅长将播客内容整理成结构清晰、重点突出的笔记。
你的任务是将播客片段转换为易于阅读的Markdown笔记。"""
            },
            {
                "role": "user",
                "content": f"""请为以下播客片段生成详细的笔记。

## 整体概括（供参考）
{overall_summary}

## 当前片段信息
**标题：** {segment['title']}
**时间范围：** {segment['start_time']:.1f}s - {segment['end_time']:.1f}s
**简要描述：** {segment.get('description', '')}

## 当前片段的对话内容
{segment_text}

## 输出格式

请按照以下结构输出Markdown笔记：

### {segment['title']}

**内容总结：** 用简洁的语言总结本段的核心内容和观点

**关键要点：**
- 要点1
- 要点2
- 要点3

**金句提取：**
> "最有价值的句子1"
> "最有价值的句子2"

**思考与启发：** （本段内容的思考和启发）
"""
            }
        ]

        return self.chat(messages, temperature=0.7)

    def _format_transcription_with_timestamps(self, transcription: List[Dict]) -> str:
        """将逐字稿格式化为带时间戳的可读文本"""
        lines = []
        for item in transcription:
            start_time = item.get('start_time', 0)
            text = item.get('text', '')
            # 转换为 HH:MM:SS 格式
            hours = int(start_time // 3600)
            minutes = int((start_time % 3600) // 60)
            seconds = int(start_time % 60)
            timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            lines.append(f"[{timestamp}] {text}")

        # 如果内容太长，进行采样（每10句保留1句，保证前中后都有）
        if len(lines) > 500:
            step = len(lines) // 500
            if step > 1:
                lines = lines[::step]

        return "\n".join(lines)

    def _extract_json(self, text: str) -> Optional[str]:
        """从文本中提取JSON内容"""
        # 尝试直接解析
        try:
            json.loads(text.strip())
            return text.strip()
        except:
            pass

        # 尝试提取 ```json ... ``` 代码块
        import re
        json_pattern = r'```json\s*(.*?)\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 尝试提取 {...} 花括号内容
        brace_pattern = r'\{.*\}'
        match = re.search(brace_pattern, text, re.DOTALL)
        if match:
            return match.group(0).strip()

        return None

    def _extract_segment_transcription(
        self,
        transcription: List[Dict],
        start_time: float,
        end_time: float
    ) -> List[Dict]:
        """提取指定时间范围的对话内容"""
        segment = []

        for item in transcription:
            item_start = item.get('start_time', 0)
            item_end = item.get('end_time', 0)

            # 如果句子与时间段有重叠，就包含进来
            if item_end >= start_time and item_start <= end_time:
                segment.append(item)

        return segment

    def _merge_notes(self, overall_summary: str, section_notes: List[Dict]) -> str:
        """合并所有分段笔记（不包含整体概括，由后续步骤生成）"""
        lines = ["## 分段详情\n"]

        for i, item in enumerate(section_notes, 1):
            segment = item['segment']
            note = item['note']

            duration_min = (segment['end_time'] - segment['start_time']) / 60
            lines.append(f"\n---\n")
            lines.append(f"**第 {i} 段：{segment['title']}**\n")
            lines.append(f"**时间范围：** {segment['start_time']/60:.1f}分钟 - {segment['end_time']/60:.1f}分钟（时长 {duration_min:.1f}分钟）\n\n")
            lines.append(note)

        return "\n".join(lines)

    def generate_final_summary(self, segments_content: str) -> Dict[str, str]:
        """
        根据完整的分段内容生成最终的整体概括和关键洞察

        Args:
            segments_content: 完整的分段详情内容

        Returns:
            {
                'overall_summary': str,  # 约600字的整体概括
                'key_insights': List[str]  # 6个左右的关键洞察
            }
        """
        messages = [
            {
                "role": "system",
                "content": """你是一位专业的播客内容分析师，擅长提炼播客的核心价值和洞察。
你的任务是根据详细的分段笔记，生成精炼的整体概括和关键洞察。"""
            },
            {
                "role": "user",
                "content": f"""请根据以下播客分段详情，完成两个任务：

**任务1：生成整体概括**
请用约600字概括整个播客的核心内容、主要观点和价值，要涵盖所有重要话题。

**任务2：提炼关键洞察**
精选6个左右最有价值的洞察、观点或启发，每个洞察用一句话精炼表达。

## 播客分段详情

{segments_content}

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
  "overall_summary": "整体概括内容（约600字）",
  "key_insights": [
    "关键洞察1",
    "关键洞察2",
    "关键洞察3",
    "关键洞察4",
    "关键洞察5",
    "关键洞察6"
  ]
}}
```

注意事项：
1. 整体概括要全面覆盖所有分段的核心内容
2. 关键洞察要选择最有价值、最发人深省的观点
3. 每个洞察要独立成句，简洁有力
"""
            }
        ]

        try:
            response = self.chat(messages, temperature=0.7)
            json_str = self._extract_json(response)

            if not json_str:
                return {
                    'overall_summary': '生成失败',
                    'key_insights': []
                }

            result = json.loads(json_str)
            return {
                'overall_summary': result.get('overall_summary', ''),
                'key_insights': result.get('key_insights', [])
            }

        except Exception as e:
            return {
                'overall_summary': f'生成失败: {str(e)}',
                'key_insights': []
            }

