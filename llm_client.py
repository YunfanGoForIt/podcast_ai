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
    """Anthropic Claude API 客户端"""

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
        """发送对话请求"""
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
        生成播客笔记

        Args:
            transcription: 逐字稿
            chapters: 章节信息
            summary: 摘要
            keywords: 关键词
            prompt_template: 自定义提示词模板

        Returns:
            生成的笔记
        """
        if prompt_template is None:
            prompt_template = self._get_default_template()

        # 准备逐字稿文本（限制长度以避免超出token限制）
        full_text = "\n".join([f"[{t.get('speaker', '未知')}] {t.get('text', '')}" for t in transcription[:500]])

        # 准备章节信息
        chapter_info = "\n".join([
            f"章节{i+1}: {c.get('title', '')} - {c.get('desc', '')} (时间: {c.get('timeline', '')})"
            for i, c in enumerate(chapters)
        ])

        messages = [
            {
                "role": "system",
                "content": """你是一位专业的播客内容编辑，擅长将播客内容整理成结构清晰、重点突出的笔记。
你的任务是将播客逐字稿转换为易于阅读的Markdown笔记，包含章节划分、金句提取和内容总结。"""
            },
            {
                "role": "user",
                "content": prompt_template.format(
                    summary=summary,
                    keywords=", ".join(keywords),
                    chapters=chapter_info,
                    transcription=full_text[:10000]  # 限制长度
                )
            }
        ]

        result = self.chat(messages, temperature=0.7)
        return self._parse_notes_result(result)

    def _get_default_template(self) -> str:
        """获取默认提示词模板"""
        return """请将以下播客内容整理成笔记：

## 播客摘要
{summary}

## 关键词
{keywords}

## 章节信息
{chapters}

## 播客逐字稿（部分）
{transcription}

请按照以下格式整理成Markdown笔记：

# 播客笔记

## 概述
（用2-3段话总结本期播客的主要内容）

## 章节笔记

### 第一章：章节标题
**内容总结：** 用简洁的语言总结本章的核心内容

**嘉宾金句：**
> "金句1"

> "金句2"

**关键要点：**
- 要点1
- 要点2

### 第二章：章节标题
...

## 核心金句
- 所有章节中最有价值的金句汇总

## 总结与思考
（对本期播客的整体思考和启发）
"""

    def _parse_notes_result(self, result: str) -> Dict[str, Any]:
        """解析笔记生成结果"""
        # 尝试提取章节信息
        chapters = []
        current_chapter = None
        current_section = None

        lines = result.split('\n')
        for line in lines:
            # 检测章节标题（通常是 ## 或 ### 开头的）
            if line.startswith('## '):
                if current_chapter:
                    chapters.append(current_chapter)
                current_chapter = {
                    'title': line.replace('## ', '').strip(),
                    'content': '',
                    'quotes': [],
                    'key_points': []
                }
                current_section = 'content'
            elif line.startswith('### '):
                current_section = 'content'
            elif line.strip().startswith('> '):
                if current_chapter:
                    current_chapter['quotes'].append(line.replace('> ', '').strip())
            elif line.strip().startswith('- '):
                if current_chapter:
                    current_chapter['key_points'].append(line.replace('- ', '').strip())
            else:
                if current_chapter and current_section == 'content':
                    current_chapter['content'] += line + '\n'

        if current_chapter:
            chapters.append(current_chapter)

        return {
            'markdown': result,
            'chapters': chapters
        }
