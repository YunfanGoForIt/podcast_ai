#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客自动化服务
定时从飞书获取新链接，调用 Qwen ASR 转写，生成笔记并保存
"""

import os
import sys
import json
import time
import hashlib
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests
from dotenv import load_dotenv
import fcntl

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入项目模块
from xiaoyuzhou_downloader import get_episode_info
from qwen_asr_client import QwenASRClient
from markdown_generator import MarkdownNoteGenerator
from llm_client import LLMManager
import yaml

# ==================== 配置 ====================

class Config:
    """配置管理"""

    def __init__(self):
        # 飞书配置
        self.app_token = os.getenv("app_token")
        self.table_id = os.getenv("table_id")
        self.feishu_app_id = os.getenv("FEISHU_APP_ID")
        self.feishu_app_secret = os.getenv("FEISHU_APP_SECRET")

        # Qwen ASR 配置
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        if not self.dashscope_api_key:
            raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")

        # ASR 模型名称
        self.asr_model = os.getenv("ASR_MODEL", "qwen3-asr-flash-filetrans")

        # 加载 LLM 配置
        self.llm_config = self._load_llm_config()

        # 目录配置
        self.audio_dir = PROJECT_ROOT / "xiaoyuzhou_audio"
        self.notes_dir = PROJECT_ROOT / "notes"
        self.state_file = PROJECT_ROOT / "podcast_state.json"
        self.log_dir = PROJECT_ROOT / "logs"
        self.workspace_dir = PROJECT_ROOT / "workspace"  # 转写结果存储目录

        # 任务配置
        self.check_interval = 60  # 检查间隔（秒）

        # 创建必要的目录
        self.audio_dir.mkdir(exist_ok=True)
        self.notes_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.workspace_dir.mkdir(exist_ok=True)

    def _load_llm_config(self) -> Optional[Dict[str, Any]]:
        """加载 LLM 配置"""
        config_file = PROJECT_ROOT / "config.yaml"
        if not config_file.exists():
            print(f"警告: LLM 配置文件不存在: {config_file}，将跳过 LLM 笔记生成")
            return None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                llm_config = config.get('llm')
                print(f"LLM 配置已加载: {llm_config.get('provider', 'unknown') if llm_config else 'None'}")
                return llm_config
        except Exception as e:
            print(f"警告: 加载 LLM 配置失败: {e}")
            return None

# ==================== 日志配置 ====================

def setup_logging(config: Config) -> logging.Logger:
    """配置日志"""
    log_file = config.log_dir / f"podcast_service_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)

# ==================== 状态管理 ====================

class EpisodeState:
    """单期播客状态"""
    PENDING = "pending"       # 未处理
    TRANSCRIBING = "transcribing"  # 转写中
    TRANSCRIBED = "transcribed"   # 已转写完成（待生成笔记）
    COMPLETED = "completed"  # 已完成
    TRANSCRIPTION_FAILED = "transcription_failed"  # 转写失败（可重试）


class StateManager:
    """状态管理，记录已处理的链接

    状态流转:
    pending -> transcribing -> transcribed -> completed
                ↑                              |
                +------- 失败重试 --------------+
    """

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"加载状态文件失败: {e}，将创建新状态")
                return {"episodes": {}, "last_check_time": None}
        return {"episodes": {}, "last_check_time": None}

    def _save_state(self):
        """保存状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存状态文件失败: {e}")

    def get_episode(self, episode_id: str) -> Optional[Dict]:
        """获取episode状态"""
        return self.state.get("episodes", {}).get(episode_id)

    def is_completed(self, episode_id: str) -> bool:
        """检查是否已完成"""
        episode = self.get_episode(episode_id)
        return episode and episode.get("state") == EpisodeState.COMPLETED

    def is_transcribed(self, episode_id: str) -> bool:
        """检查是否已转写完成"""
        episode = self.get_episode(episode_id)
        return episode and episode.get("state") in [EpisodeState.TRANSCRIBED, EpisodeState.COMPLETED]

    def update_episode(self, episode_id: str, data: Dict[str, Any]):
        """更新episode状态"""
        if "episodes" not in self.state:
            self.state["episodes"] = {}

        if episode_id not in self.state["episodes"]:
            self.state["episodes"][episode_id] = {}

        self.state["episodes"][episode_id].update({
            "updated_at": datetime.now().isoformat(),
            **data
        })
        self._save_state()

    def mark_transcribing(self, episode_id: str, record_id: str, url: str, title: str, audio_url: str):
        """标记开始转写"""
        self.update_episode(episode_id, {
            "state": EpisodeState.TRANSCRIBING,
            "record_id": record_id,
            "url": url,
            "title": title,
            "audio_url": audio_url,
        })

    def mark_transcribed(self, episode_id: str, task_id: str):
        """标记转写完成"""
        self.update_episode(episode_id, {
            "state": EpisodeState.TRANSCRIBED,
            "task_id": task_id,
        })

    def get_transcription_path(self, episode_id: str) -> Optional[str]:
        """获取转写结果文件路径"""
        episode = self.get_episode(episode_id)
        return episode.get("transcription_path") if episode else None

    def set_transcription_path(self, episode_id: str, path: str):
        """设置转写结果文件路径"""
        self.update_episode(episode_id, {"transcription_path": path})

    def mark_completed(self, episode_id: str, note_path: str):
        """标记完成"""
        self.update_episode(episode_id, {
            "state": EpisodeState.COMPLETED,
            "note_path": note_path,
            "completed_at": datetime.now().isoformat(),
        })

    def mark_failed(self, episode_id: str, error: str):
        """标记失败（保留状态，可重试）"""
        self.update_episode(episode_id, {
            "error": error,
            "failed_at": datetime.now().isoformat(),
        })

    def update_last_check_time(self):
        """更新最后检查时间"""
        self.state["last_check_time"] = datetime.now().isoformat()
        self._save_state()

# ==================== 飞书客户端 ====================

class FeishuClient:
    """飞书多维表格客户端"""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.access_token = None
        self.base_url = "https://open.feishu.cn/open-apis"

    def get_tenant_access_token(self) -> bool:
        """获取tenant_access_token"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.config.feishu_app_id,
            "app_secret": self.config.feishu_app_secret
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                self.logger.error(f"获取飞书token失败: {result.get('msg')}")
                return False

            self.access_token = result.get("tenant_access_token")
            self.logger.info("成功获取飞书access_token")
            return True
        except Exception as e:
            self.logger.error(f"获取飞书token异常: {e}")
            return False

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _refresh_token_if_needed(self) -> bool:
        """如果 token 过期，刷新 token"""
        if not self.access_token:
            return self.get_tenant_access_token()
        return True

    def get_all_records(self) -> Optional[List[Dict]]:
        """获取所有记录"""
        search_url = f"{self.base_url}/bitable/v1/apps/{self.config.app_token}/tables/{self.config.table_id}/records/search"

        payload = {
            "page_size": 100,
            "automatic_fields": False
        }

        all_records = []
        page_token = None

        while True:
            if page_token:
                payload["page_token"] = page_token

            try:
                response = requests.post(
                    search_url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=30
                )

                # 检查是否是 token 过期 (401 或特定错误码)
                if response.status_code == 401:
                    self.logger.warning("Access token 可能过期，尝试刷新...")
                    if self.get_tenant_access_token():
                        # 刷新成功，重试请求
                        response = requests.post(
                            search_url,
                            headers=self._get_headers(),
                            json=payload,
                            timeout=30
                        )
                    else:
                        self.logger.error("刷新 token 失败")
                        return None

                # 处理 400 错误，尝试刷新 token 后重试
                if response.status_code == 400:
                    self.logger.warning("收到 400 错误，尝试刷新 token 后重试...")
                    if self.get_tenant_access_token():
                        response = requests.post(
                            search_url,
                            headers=self._get_headers(),
                            json=payload,
                            timeout=30
                        )
                    else:
                        self.logger.error("刷新 token 失败")
                        return None

                response.raise_for_status()
                result = response.json()

                # 检查飞书 API 错误码
                code = result.get("code")
                if code != 0:
                    error_msg = result.get('msg', '')
                    self.logger.error(f"飞书API返回错误: code={code}, msg={error_msg}")

                    # token 过期错误码，尝试刷新
                    if code == 99991663:
                        self.logger.warning("Access token 过期，尝试刷新...")
                        if self.get_tenant_access_token():
                            continue  # 刷新成功，重试
                        else:
                            return None

                    return None

                items = result.get("data", {}).get("items", [])
                all_records.extend(items)

                has_more = result.get("data", {}).get("has_more", False)
                if not has_more:
                    break

                page_token = result.get("data", {}).get("page_token")

            except Exception as e:
                # 记录更详细的错误信息
                self.logger.error(f"获取飞书记录失败: {e}")
                if 'response' in dir() and hasattr(response, 'status_code'):
                    self.logger.error(f"状态码: {response.status_code}")
                    self.logger.error(f"响应头: {dict(response.headers)}")
                    try:
                        self.logger.error(f"响应体: {response.text[:500]}")
                    except:
                        pass
                return None

        return all_records

    def parse_podcast_link(self, record: Dict) -> Optional[Dict[str, str]]:
        """解析播客记录，提取链接"""
        fields = record.get("fields", {})

        # 尝试提取小宇宙链接
        for key in ["播客链接", "链接", "link", "url", "网址", "小宇宙链接"]:
            if key in fields and fields[key]:
                url = fields[key]

                # 处理飞书URL字段格式（字典）
                if isinstance(url, dict) and "link" in url:
                    url = url["link"]

                # 处理列表格式
                elif isinstance(url, list) and len(url) > 0:
                    url = url[0]
                    if isinstance(url, dict) and "link" in url:
                        url = url["link"]

                # 检查是否是小宇宙链接
                if isinstance(url, str) and "xiaoyuzhoufm.com" in url:
                    return {
                        "record_id": record.get("record_id"),
                        "url": url,
                        "title": fields.get("播客名称") or fields.get("名称") or fields.get("title", "")
                    }

        return None

# ==================== 播客处理服务 ====================

class PodcastService:
    """播客处理服务"""

    def __init__(self, config: Config):
        self.config = config

        # 单实例锁：确保只有一个服务实例运行
        self.lock_file = open(config.log_dir / "podcast_service.lock", 'w')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError("服务已在运行中！请先停止旧实例再启动新实例。")

        self.logger = setup_logging(config)
        self.logger.info("=" * 60)
        self.logger.info("获取单实例锁成功，确保只有一个服务实例在运行")
        self.logger.info("=" * 60)

        self.state_manager = StateManager(config.state_file)
        self.feishu_client = FeishuClient(config, self.logger)
        self.asr_client = QwenASRClient(config.dashscope_api_key, self.logger)
        self.markdown_generator = MarkdownNoteGenerator()

        # 初始化 LLM Manager（如果配置存在）
        self.llm_manager = None
        if config.llm_config:
            try:
                self.llm_manager = LLMManager(config.llm_config)
                self.logger.info(f"LLM Manager 已初始化: {config.llm_config.get('provider')}")
            except Exception as e:
                self.logger.warning(f"LLM Manager 初始化失败: {e}，将跳过 LLM 笔记生成")

        # 初始化飞书token
        if not self.feishu_client.get_tenant_access_token():
            raise RuntimeError("无法初始化飞书客户端")

    def process_episode(self, record_id: str, url: str, title: str) -> bool:
        """处理单个播客episode"""
        self.logger.info(f"开始处理: {title} - {url}")

        try:
            # 1. 获取episode信息
            self.logger.info("获取episode信息...")
            episode_info = get_episode_info(url)
            if not episode_info:
                self.logger.error(f"无法获取episode信息: {url}")
                return False

            audio_url = episode_info.get('audio_url')
            episode_title = episode_info.get('title', title)
            episode_id = episode_info.get('episode_id', '')

            if not audio_url:
                self.logger.error(f"未找到音频链接: {url}")
                return False

            if not episode_id:
                self.logger.error(f"未找到episode_id: {url}")
                return False

            self.logger.info(f"Episode ID: {episode_id}")
            self.logger.info(f"音频链接: {audio_url}")

            # 2. 检查是否已转写完成（断点续传）
            existing_episode = self.state_manager.get_episode(episode_id)

            # 如果已完成，直接跳过
            if self.state_manager.is_completed(episode_id):
                self.logger.info(f"该episode已完成，跳过: {episode_id}")
                return True

            # 如果已转写完成但笔记失败，尝试重新生成笔记
            if self.state_manager.is_transcribed(episode_id):
                self.logger.info(f"该episode已转写完成，尝试生成笔记: {episode_id}")
                return self._generate_notes(
                    episode_id=episode_id,
                    episode_title=episode_title,
                    url=url,
                    record_id=record_id,
                    task_id=self.state_manager.get_episode(episode_id).get("task_id", "")
                )

            # 如果转写失败且有 task_id，直接尝试获取结果（断点续传）
            existing = self.state_manager.get_episode(episode_id)
            if existing and existing.get("state") == EpisodeState.TRANSCRIPTION_FAILED:
                if existing.get("task_id"):
                    self.logger.info(f"该episode转写曾失败，尝试获取已有结果: {existing['task_id']}")
                    final_result = self.asr_client.wait_for_result(
                        task_id=existing["task_id"],
                        timeout=60,
                        poll_interval=5
                    )
                    if final_result.get('success'):
                        self.logger.info("转写结果已就绪")
                    else:
                        # 任务可能还在进行中或彻底失败，重新提交
                        self.logger.info("转写仍在进行或失败，重新提交任务...")
                        submit_result = self.asr_client.submit_transcription(
                            file_url=audio_url,
                            model=self.config.asr_model
                        )
                        if not submit_result.get('success'):
                            self.state_manager.update_episode(episode_id, {
                                "state": EpisodeState.TRANSCRIPTION_FAILED,
                                "error": str(submit_result),
                                "failed_at": datetime.now().isoformat()
                            })
                            return False
                        task_id = submit_result.get('task_id')
                        self.state_manager.update_episode(episode_id, {"task_id": task_id})
                        self.logger.info(f"转写任务已提交: {task_id}")
                        final_result = self.asr_client.wait_for_result(
                            task_id=task_id,
                            timeout=720,
                            poll_interval=10
                        )

            # 3. 提交转写任务（使用小宇宙音频URL）
            self.state_manager.mark_transcribing(episode_id, record_id, url, title, audio_url)

            self.logger.info("提交 Qwen ASR 转写任务...")
            self.logger.info(f"使用模型: {self.config.asr_model}")

            # 如果有已存在的 task_id，尝试获取结果
            if existing_episode and existing_episode.get("task_id"):
                task_id = existing_episode["task_id"]
                self.logger.info(f"使用已有的task_id获取结果: {task_id}")
                final_result = self.asr_client.wait_for_result(
                    task_id=task_id,
                    timeout=60,  # 较短超时，因为任务可能已完成
                    poll_interval=5
                )

                if not final_result.get('success'):
                    # 任务可能还在进行中，重新提交
                    self.logger.info("已有任务未完成，重新提交...")
                    submit_result = self.asr_client.submit_transcription(
                        file_url=audio_url,
                        model=self.config.asr_model
                    )
                    if not submit_result.get('success'):
                        self.logger.error(f"提交转写任务失败: {submit_result}")
                        self.state_manager.mark_failed(episode_id, str(submit_result))
                        return False
                    task_id = submit_result.get('task_id')
                    self.logger.info(f"转写任务已提交: {task_id}")

                    # 等待转写完成
                    self.logger.info("等待转写完成（这可能需要几分钟）...")
                    final_result = self.asr_client.wait_for_result(
                        task_id=task_id,
                        timeout=720,  # 12分钟超时
                        poll_interval=10
                    )
            else:
                # 提交新任务
                submit_result = self.asr_client.submit_transcription(
                    file_url=audio_url,
                    model=self.config.asr_model
                )

                if not submit_result.get('success'):
                    self.logger.error(f"提交转写任务失败: {submit_result}")
                    self.state_manager.mark_failed(episode_id, str(submit_result))
                    return False

                task_id = submit_result.get('task_id')
                self.logger.info(f"转写任务已提交: {task_id}")

                # 等待转写完成
                self.logger.info("等待转写完成（这可能需要几分钟）...")
                final_result = self.asr_client.wait_for_result(
                    task_id=task_id,
                    timeout=720,  # 12分钟超时
                    poll_interval=10
                )

            if not final_result.get('success'):
                self.logger.error(f"转写任务失败: {final_result}")
                # 标记为转写失败，保留 task_id 供重试
                self.state_manager.update_episode(episode_id, {
                    "state": EpisodeState.TRANSCRIPTION_FAILED,
                    "task_id": task_id,
                    "transcription_error": str(final_result),
                    "failed_at": datetime.now().isoformat()
                })
                return False

            # 4. 解析转写结果
            self.logger.info("解析转写结果...")
            parsed_result = self.asr_client.parse_transcription_result(
                result=final_result,
                metadata={
                    'task_id': task_id,
                    'title': episode_title,
                    'url': url
                }
            )

            # 5. 保存转写结果到 workspace
            transcription_path = self.config.workspace_dir / f"{episode_id}.json"
            try:
                with open(transcription_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_result, f, ensure_ascii=False, indent=2)
                self.logger.info(f"转写结果已保存: {transcription_path}")
            except Exception as e:
                self.logger.warning(f"保存转写结果失败: {e}")

            # 6. 标记为已转写
            self.state_manager.mark_transcribed(episode_id, task_id)
            self.state_manager.set_transcription_path(episode_id, str(transcription_path))
            self.logger.info(f"转写完成，task_id: {task_id}")

            # 7. 生成笔记
            return self._generate_notes(
                episode_id=episode_id,
                episode_title=episode_title,
                url=url,
                record_id=record_id,
                task_id=task_id
            )

        except Exception as e:
            self.logger.error(f"处理失败: {e}", exc_info=True)
            # 从 episode_id 获取失败信息
            error_episode_id = episode_info.get('episode_id', '') if 'episode_info' in dir() else ''
            if error_episode_id:
                self.state_manager.mark_failed(error_episode_id, str(e))
            return False

    def _generate_notes(self, episode_id: str, episode_title: str, url: str,
                        record_id: str, task_id: str) -> bool:
        """生成笔记（可独立调用，支持断点续传）"""
        try:
            # 从 workspace 加载转写结果
            transcription_path = self.state_manager.get_transcription_path(episode_id)
            if not transcription_path or not Path(transcription_path).exists():
                self.logger.error(f"转写结果文件不存在: {transcription_path}")
                return False

            with open(transcription_path, 'r', encoding='utf-8') as f:
                transcription_result = json.load(f)

            self.logger.info(f"从 {transcription_path} 加载转写结果")

            # 使用 LLM 生成笔记（如果可用）
            llm_notes = {}
            if self.llm_manager and transcription_result.get('transcription'):
                try:
                    self.logger.info("使用 LLM 生成笔记（分段处理）...")
                    llm_result = self.llm_manager.generate_podcast_notes(
                        transcription=transcription_result['transcription'],
                        chapters=transcription_result.get('chapters', []),
                        summary=transcription_result.get('summary', ''),
                        keywords=transcription_result.get('keywords', [])
                    )

                    if 'error' not in llm_result:
                        self.logger.info(f"LLM 笔记生成成功，共 {len(llm_result.get('segments', []))} 个分段")

                        # 6.1 根据分段内容生成最终的整体概括和关键洞察
                        self.logger.info("生成最终整体概括和关键洞察...")
                        final_summary = self.llm_manager.generate_final_summary(
                            segments_content=llm_result.get('markdown', '')
                        )

                        llm_notes = {
                            'segments': llm_result.get('segments', []),
                            'segments_markdown': llm_result.get('markdown', ''),
                            'final_summary': final_summary.get('overall_summary', ''),
                            'key_insights': final_summary.get('key_insights', [])
                        }
                        self.logger.info(f"最终概括和关键洞察生成完成，共 {len(final_summary.get('key_insights', []))} 条关键洞察")
                    else:
                        self.logger.warning(f"LLM 笔记生成失败: {llm_result.get('error')}")

                except Exception as e:
                    self.logger.warning(f"LLM 笔记生成异常: {e}，将使用基础笔记")
            else:
                self.logger.info("LLM 不可用，将使用基础笔记格式")

            # 7. 生成Markdown笔记（内部已保存）
            self.logger.info("生成Markdown笔记...")
            note_path = self.markdown_generator.generate(
                audio_name=episode_title,
                parsed_data=transcription_result,
                llm_notes=llm_notes
            )

            self.logger.info(f"笔记已保存: {note_path}")

            # 8. 标记为已完成
            self.state_manager.mark_completed(episode_id, str(note_path))

            self.logger.info(f"✅ 处理完成: {episode_title}")
            return True

        except Exception as e:
            self.logger.error(f"生成笔记失败: {e}", exc_info=True)
            # 标记失败，但保留转写状态，可重试
            self.state_manager.mark_failed(episode_id, str(e))
            self.logger.warning(f"笔记生成失败，但转写已完成，将自动重试: {episode_id}")
            return False

    def check_and_process_new(self) -> int:
        """检查并处理新的播客链接"""
        self.logger.info("="*60)
        self.logger.info("开始检查新链接...")
        self.logger.info("="*60)

        # 获取所有记录
        records = self.feishu_client.get_all_records()
        if not records:
            self.logger.warning("未获取到任何记录")
            return 0

        self.logger.info(f"共获取 {len(records)} 条记录")

        processed_count = 0

        for record in records:
            record_id = record.get("record_id")

            # 解析链接
            podcast_info = self.feishu_client.parse_podcast_link(record)
            if not podcast_info:
                self.logger.info(f"未找到有效的小宇宙链接，跳过记录: {record_id}, 字段: {record.get('fields', {}).keys()}")
                continue

            url = podcast_info["url"]
            title = podcast_info["title"]

            # 获取episode信息以获取 episode_id
            episode_info = get_episode_info(url)
            if not episode_info:
                self.logger.warning(f"无法获取episode信息，跳过: {url}")
                continue

            episode_id = episode_info.get('episode_id')
            if not episode_id:
                self.logger.warning(f"未找到episode_id，跳过: {url}")
                continue

            # 检查是否已完成
            if self.state_manager.is_completed(episode_id):
                self.logger.debug(f"该episode已完成，跳过: {episode_id}")
                continue

            # 处理
            if self.process_episode(record_id, url, title):
                processed_count += 1

        # 更新最后检查时间
        self.state_manager.update_last_check_time()

        self.logger.info(f"本次检查完成，新处理 {processed_count} 个播客")
        return processed_count

    def run(self):
        """运行服务"""
        self.logger.info("="*60)
        self.logger.info("播客自动化服务启动")
        self.logger.info("="*60)
        self.logger.info(f"检查间隔: {self.config.check_interval} 秒")

        while True:
            try:
                self.check_and_process_new()
            except Exception as e:
                self.logger.error(f"检查过程出错: {e}", exc_info=True)

            # 等待下一次检查
            self.logger.info(f"等待 {self.config.check_interval} 秒后进行下一次检查...")
            time.sleep(self.config.check_interval)

# ==================== 主函数 ====================

def main():
    """主函数"""
    try:
        config = Config()
        service = PodcastService(config)
        service.run()
    except KeyboardInterrupt:
        logging.info("收到停止信号，退出服务")
    except Exception as e:
        logging.error(f"服务异常退出: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
