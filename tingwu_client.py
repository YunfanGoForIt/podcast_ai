"""
通义听悟 API 客户端
用于音视频文件转写、章节速览、要点提炼等功能
"""
import json
import time
import uuid
import hashlib
import hmac
import base64
import requests
from typing import Optional, Dict, Any
from pathlib import Path


class TingwuClient:
    """通义听悟 API 客户端"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化客户端

        Args:
            config: 配置字典，包含 access_key_id, access_key_secret, appkey, region_id
        """
        self.access_key_id = config['access_key_id']
        self.access_key_secret = config['access_key_secret']
        self.appkey = config['appkey']
        self.region_id = config.get('region_id', 'cn-shanghai')

        # 旧版API端点
        self.endpoint = f"https://tingwu.cn-{self.region_id}.aliyuncs.com"

    def _make_signature(self, method: str, path: str, timestamp: str) -> str:
        """
        生成 API 签名

        Args:
            method: HTTP方法
            path: 请求路径
            timestamp: 时间戳

        Returns:
            签名字符串
        """
        string_to_sign = f"{method}\n&%2F&{timestamp}"
        signature = hmac.new(
            self.access_key_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _get_authorization(self, method: str, path: str, timestamp: str) -> str:
        """
        生成 Authorization 头

        Args:
            method: HTTP方法
            path: 请求路径
            timestamp: 时间戳

        Returns:
            Authorization 头值
        }
        """
        signature = self._make_signature(method, path, timestamp)
        return f"Dataplus {self.access_key_id}:{signature}"

    def _make_headers(self, method: str, path: str, extra_headers: Optional[Dict] = None) -> Dict[str, str]:
        """
        生成请求头

        Args:
            method: HTTP方法
            path: 请求路径
            extra_headers: 额外请求头

        Returns:
            请求头字典
        """
        timestamp = str(int(time.time()))
        headers = {
            'Authorization': self._get_authorization(method, path, timestamp),
            'Content-Type': 'application/json',
            'X-Forwarded-For': '127.0.0.1',
            'X-Timestamp': timestamp
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def submit_transcription_task(self, file_path: str) -> Dict[str, Any]:
        """
        提交音视频转写任务

        Args:
            file_path: 音频文件路径

        Returns:
            任务提交结果，包含 task_id
        """
        url = f"{self.endpoint}"

        # 读取文件内容并计算MD5
        with open(file_path, 'rb') as f:
            file_content = f.read()
            file_md5 = hashlib.md5(file_content).hexdigest()
            file_size = len(file_content)
            file_name = Path(file_path).name

        # 构造请求体
        task_id = str(uuid.uuid4())
        body = {
            "appkey": self.appkey,
            "file_link": "",  # 这里的file_link字段在直接上传时可能需要特殊处理
            "file_md5": file_md5,
            "file_name": file_name,
            "file_size": file_size,
            "enable_words": True,          # 开启词级别时间戳
            "enable_sentence": True,       # 开启句子级时间戳
            "enablepeaker_id": True,       # 开启说话人分离
            "enable_keyword": True,        # 开启关键词提取
            "enable_summary": True,        # 开启摘要总结
            "enable_chapter": True,        # 开启章节速览
            "enable_ppt": False,           # 不需要PPT提取
            "enable_cer": False,           # 不需要准确率评分
            "biz_type": "fileTrans",       # 业务类型：音视频文件转写
            "callback_url": "",            # 可选：回调URL，不设置则使用轮询
            "task_id": task_id
        }

        headers = self._make_headers('POST', '/')

        # 实际上传文件到OSS的逻辑需要根据实际场景处理
        # 这里使用文件上传方式
        response = requests.post(
            url,
            json=body,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    def submit_with_file_upload(self, file_path: str) -> Dict[str, Any]:
        """
        通过文件上传方式提交转写任务

        Args:
            file_path: 音频文件路径

        Returns:
            任务提交结果
        """
        url = f"{self.endpoint}"

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 读取文件内容并计算MD5
        with open(file_path, 'rb') as f:
            file_content = f.read()
            file_md5 = hashlib.md5(file_content).hexdigest()
            file_size = len(file_content)

        # 构造请求体
        body = {
            "appkey": self.appkey,
            "file_md5": file_md5,
            "file_size": file_size,
            "enable_words": True,
            "enable_sentence": True,
            "enablepeaker_id": True,
            "enable_keyword": True,
            "enable_summary": True,
            "enable_chapter": True,
            "biz_type": "fileTrans",
            "task_id": task_id
        }

        # 将文件内容进行Base64编码
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        body["file_content"] = file_base64

        timestamp = str(int(time.time()))
        headers = {
            'Authorization': self._get_authorization('POST', '/', timestamp),
            'Content-Type': 'application/json',
            'X-Forwarded-For': '127.0.0.1',
            'X-Timestamp': timestamp
        }

        response = requests.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        获取转写任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果
        """
        url = f"{self.endpoint}"

        body = {
            "task_id": task_id
        }

        timestamp = str(int(time.time()))
        headers = {
            'Authorization': self._get_authorization('POST', '/', timestamp),
            'Content-Type': 'application/json',
            'X-Forwarded-For': '127.0.0.1',
            'X-Timestamp': timestamp
        }

        response = requests.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    def wait_for_result(self, task_id: str, poll_interval: int = 10, max_polls: int = 120) -> Dict[str, Any]:
        """
        轮询等待任务完成

        Args:
            task_id: 任务ID
            poll_interval: 轮询间隔(秒)
            max_polls: 最大轮询次数

        Returns:
            最终任务结果

        Raises:
            TimeoutError: 任务超时
        """
        for i in range(max_polls):
            result = self.get_task_result(task_id)

            # 根据实际API返回状态判断
            status = result.get('data', {}).get('status', '')

            if status == 'SUCCESS':
                return result
            elif status == 'FAIL':
                raise Exception(f"转写任务失败: {result.get('data', {}).get('fail_reason', '未知错误')}")

            print(f"任务进行中... ({i + 1}/{max_polls})")
            time.sleep(poll_interval)

        raise TimeoutError("转写任务超时")

    def parse_transcription_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析转写结果

        Args:
            result: 原始API返回结果

        Returns:
            解析后的结构化数据
        """
        data = result.get('data', {})

        # 提取基本信息
        parsed = {
            'task_id': data.get('task_id'),
            'audio_name': data.get('file_name'),
            'transcription': [],  # 逐字稿
            'chapters': [],       # 章节速览
            'summary': '',        # 摘要
            'keywords': [],       # 关键词
            'speakers': set()     # 说话人列表
        }

        # 解析逐字稿
        words_result = data.get('words_result', [])
        sentences = data.get('sentences_result', [])

        if sentences:
            for sentence in sentences:
                parsed['transcription'].append({
                    'text': sentence.get('text', ''),
                    'speaker': sentence.get('speaker_label', '未知'),
                    'start_time': sentence.get('begin_time', 0),
                    'end_time': sentence.get('end_time', 0)
                })
                parsed['speakers'].add(sentence.get('speaker_label', '未知'))

        # 解析章节速览
        chapters_result = data.get('chapters_result', [])
        if chapters_result:
            parsed['chapters'] = chapters_result

        # 解析摘要
        summary_result = data.get('summary_result', [])
        if summary_result:
            parsed['summary'] = summary_result[0].get('summary', '')

        # 解析关键词
        keywords_result = data.get('keywords_result', [])
        if keywords_result:
            parsed['keywords'] = [kw.get('keyword', '') for kw in keywords_result]

        return parsed
