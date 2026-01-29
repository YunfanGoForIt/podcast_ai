"""
Qwen ASM (Qwen3 ASR) 客户端
使用阿里云 DashScope API 进行语音识别
"""
import os
import logging
from typing import Dict, Any, Optional
from dashscope.audio.qwen_asr import QwenTranscription
from dashscope.api_entities.dashscope_response import TranscriptionResponse


class QwenASRClient:
    """Qwen ASR 语音识别客户端"""

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        """
        初始化客户端

        Args:
            api_key: DashScope API Key
            logger: 日志记录器
        """
        import dashscope

        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)

        # 配置 API Key
        dashscope.api_key = api_key

        # 配置 API 端点（北京地域）
        # 如使用新加坡地域，替换为：https://dashscope-intl.aliyuncs.com/api/v1
        dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'

        self.logger.info("[Qwen ASR] 初始化客户端")
        self.logger.info(f"[Qwen ASR] API 端点: {dashscope.base_http_api_url}")

    def submit_transcription(
        self,
        file_url: str,
        model: str = 'qwen3-asr-flash-filetrans',
        enable_itn: bool = False
    ) -> Dict[str, Any]:
        """
        提交语音转写任务

        Args:
            file_url: 音频文件的公开可访问 URL
            model: 模型名称，默认 qwen3-asr-flash-filetrans
            enable_itn: 是否启用逆文本标准化（数字、日期等格式转换）

        Returns:
            任务提交结果，包含 task_id
        """
        self.logger.info(f"[Qwen ASR] 提交转写任务")
        self.logger.info(f"[Qwen ASR] 文件 URL: {file_url}")
        self.logger.info(f"[Qwen ASR] 模型: {model}")

        try:
            task_response = QwenTranscription.async_call(
                model=model,
                file_url=file_url,
                enable_itn=enable_itn
            )

            self.logger.info(f"[Qwen ASR] 响应状态码: {task_response.status_code}")
            self.logger.info(f"[Qwen ASR] 响应: {task_response}")

            if task_response.status_code == 200:
                task_id = task_response.output.task_id
                self.logger.info(f"[Qwen ASR] ✅ 任务提交成功 - task_id: {task_id}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'response': task_response
                }
            else:
                self.logger.error(f"[Qwen ASR] ❌ 任务提交失败")
                self.logger.error(f"[Qwen ASR] 错误码: {task_response.status_code}")
                self.logger.error(f"[Qwen ASR] 错误信息: {task_response}")
                return {
                    'success': False,
                    'error': f"HTTP {task_response.status_code}",
                    'response': task_response
                }

        except Exception as e:
            self.logger.error(f"[Qwen ASR] ❌ 提交任务异常: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def fetch_result(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            任务状态和结果
        """
        self.logger.debug(f"[Qwen ASR] 查询任务状态 - task_id: {task_id}")

        try:
            query_response = QwenTranscription.fetch(task=task_id)

            self.logger.debug(f"[Qwen ASR] 查询响应: {query_response}")

            return {
                'success': query_response.status_code == 200,
                'status_code': query_response.status_code,
                'response': query_response
            }

        except Exception as e:
            self.logger.error(f"[Qwen ASR] 查询任务状态失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def wait_for_result(
        self,
        task_id: str,
        timeout: int = 3600,
        poll_interval: int = 10
    ) -> Dict[str, Any]:
        """
        等待任务完成

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒），默认 1 小时
            poll_interval: 轮询间隔（秒）

        Returns:
            转写结果
        """
        self.logger.info(f"[Qwen ASR] 开始等待任务完成 - task_id: {task_id}")
        self.logger.info(f"[Qwen ASR] 超时时间: {timeout}秒, 轮询间隔: {poll_interval}秒")

        try:
            task_result = QwenTranscription.wait(
                task=task_id,
                timeout=timeout
            )

            self.logger.info(f"[Qwen ASR] 最终响应: {task_result}")

            if task_result.status_code == 200:
                output = task_result.output

                # 检查任务状态
                if output.task_status == "SUCCEEDED":
                    self.logger.info(f"[Qwen ASR] ✅ 转写任务完成")

                    # Qwen ASR 返回的是 transcription_url，需要下载
                    if hasattr(output, 'result') and output.result:
                        # output.result 可能是 dict 或对象
                        result = output.result
                        if isinstance(result, dict):
                            transcription_url = result.get('transcription_url')
                        else:
                            transcription_url = result.transcription_url

                        if not transcription_url:
                            self.logger.error(f"[Qwen ASR] 未找到 transcription_url，result: {result}")
                            return {
                                'success': False,
                                'error': '未找到 transcription_url'
                            }

                        self.logger.info(f"[Qwen ASR] 转写结果URL: {transcription_url}")

                        # 下载转写结果
                        import requests
                        try:
                            resp = requests.get(transcription_url, timeout=30)
                            resp.raise_for_status()
                            transcription_data = resp.json()

                            # Qwen ASR 返回的数据结构：
                            # {
                            #   "file_url": "...",
                            #   "audio_info": {"format": "aac", "sample_rate": 44100},
                            #   "transcripts": [
                            #     {
                            #       "channel_id": 0,
                            #       "text": "完整文本...",
                            #       "sentences": [
                            #         {"sentence_id": 0, "begin_time": 7148, "end_time": 31508, "text": "..."},
                            #         ...
                            #       ]
                            #     }
                            #   ]
                            # }

                            # 提取完整文本
                            transcripts = transcription_data.get('transcripts', [])
                            if transcripts and len(transcripts) > 0:
                                text = transcripts[0].get('text', '')
                                sentences = transcripts[0].get('sentences', [])

                                self.logger.info(f"[Qwen ASR] 转写完成")
                                self.logger.info(f"[Qwen ASR] 文本长度: {len(text)} 字符")
                                self.logger.info(f"[Qwen ASR] 句子数量: {len(sentences)}")
                                self.logger.info(f"[Qwen ASR] 文本预览: {text[:200]}...")

                                return {
                                    'success': True,
                                    'text': text,
                                    'sentences': sentences,
                                    'transcription_url': transcription_url,
                                    'raw_data': transcription_data,
                                    'response': task_result
                                }
                            else:
                                self.logger.error(f"[Qwen ASR] 未找到 transcripts 数据")
                                return {
                                    'success': False,
                                    'error': '未找到 transcripts 数据'
                                }
                        except Exception as e:
                            self.logger.error(f"[Qwen ASR] 下载转写结果失败: {e}")
                            return {
                                'success': False,
                                'error': f"下载转写结果失败: {str(e)}"
                            }
                    else:
                        self.logger.error(f"[Qwen ASR] 未找到转写结果")
                        return {
                            'success': False,
                            'error': '未找到转写结果'
                        }
                else:
                    self.logger.error(f"[Qwen ASR] ❌ 任务状态: {output.task_status}")
                    return {
                        'success': False,
                        'error': f"任务状态: {output.task_status}"
                    }
            else:
                self.logger.error(f"[Qwen ASR] ❌ HTTP错误")
                self.logger.error(f"[Qwen ASR] 状态码: {task_result.status_code}")
                return {
                    'success': False,
                    'error': f"HTTP {task_result.status_code}",
                    'response': task_result
                }

        except Exception as e:
            self.logger.error(f"[Qwen ASR] ⏰ 等待任务超时或异常: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def parse_transcription_result(self, result: Dict[str, Any], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        解析转写结果为统一格式

        Args:
            result: wait_for_result 返回的结果
            metadata: 额外的元数据（如标题、URL等）

        Returns:
            解析后的结构化数据
        """
        self.logger.info("[Qwen ASR] 解析转写结果")

        if not result.get('success'):
            return {
                'error': result.get('error', 'Unknown error'),
                'transcription': [],
                'text': ''
            }

        text = result.get('text', '')
        sentences = result.get('sentences', [])

        # 尝试从响应中获取音频时长
        response = result.get('response')
        audio_duration = 0
        if response and hasattr(response, 'usage'):
            audio_duration = response.usage.seconds or 0

        # 如果有 sentences 数据，构建分段转录
        transcription_list = []
        speakers = []  # 改为 list

        if sentences:
            for sent in sentences:
                transcription_list.append({
                    'text': sent.get('text', ''),
                    'speaker': '未知',  # Qwen ASR 不提供说话人识别
                    'start_time': sent.get('begin_time', 0) / 1000,  # 毫秒转秒
                    'end_time': sent.get('end_time', 0) / 1000
                })
                if '未知' not in speakers:
                    speakers.append('未知')

            self.logger.info(f"[Qwen ASR] 解析了 {len(transcription_list)} 个句子片段")
        else:
            # 如果没有分段信息，使用完整文本
            transcription_list.append({
                'text': text,
                'speaker': '未知',
                'start_time': 0,
                'end_time': audio_duration
            })

        parsed = {
            'task_id': metadata.get('task_id') if metadata else None,
            'audio_name': metadata.get('title', '') if metadata else '',
            'text': text,
            'audio_duration': audio_duration,
            'transcription': transcription_list,
            'chapters': [],  # Qwen ASR 不提供章节，需要 LLM 后处理
            'summary': '',   # 需要调用 LLM 生成摘要
            'keywords': [],  # 需要调用 LLM 提取关键词
            'speakers': speakers
        }

        self.logger.info(f"[Qwen ASR] ✅ 解析完成")
        self.logger.info(f"[Qwen ASR] 文本长度: {len(text)} 字符")
        self.logger.info(f"[Qwen ASR] 音频时长: {audio_duration} 秒")
        self.logger.info(f"[Qwen ASR] 转录片段: {len(transcription_list)} 个")

        return parsed
