#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播客自动化服务
定时从飞书获取新链接，下载音频，调用通义听悟解析，保存笔记
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

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入项目模块
from xiaoyuzhou_downloader import get_episode_info, download_audio
from tingwu_client import TingwuClient
from markdown_generator import MarkdownGenerator
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

        # 加载YAML配置
        config_path = PROJECT_ROOT / "config.yaml"
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)

        # 通义听悟配置
        self.tingwu_config = {
            'access_key_id': yaml_config['aliyun']['access_key_id'],
            'access_key_secret': yaml_config['aliyun']['access_key_secret'],
            'appkey': yaml_config['aliyun']['appkey'],
            'region_id': yaml_config['aliyun']['region_id'],
        }

        # 目录配置
        self.audio_dir = PROJECT_ROOT / "xiaoyuzhou_audio"
        self.notes_dir = PROJECT_ROOT / "notes"
        self.state_file = PROJECT_ROOT / "podcast_state.json"
        self.log_dir = PROJECT_ROOT / "logs"

        # 任务配置
        self.check_interval = 60  # 检查间隔（秒）
        self.poll_interval = yaml_config['task']['poll_interval']
        self.max_polls = yaml_config['task']['max_polls']

        # 创建必要的目录
        self.audio_dir.mkdir(exist_ok=True)
        self.notes_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)

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

class StateManager:
    """状态管理，记录已处理的链接"""

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
                return {}
        return {
            "processed_records": {},  # record_id -> 处理信息
            "processed_urls": {},     # url_hash -> 处理信息
            "last_check_time": None
        }

    def _save_state(self):
        """保存状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存状态文件失败: {e}")

    def is_record_processed(self, record_id: str) -> bool:
        """检查记录是否已处理"""
        return record_id in self.state.get("processed_records", {})

    def is_url_processed(self, url: str) -> bool:
        """检查URL是否已处理"""
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return url_hash in self.state.get("processed_urls", {})

    def mark_record_processed(self, record_id: str, url: str, info: Dict[str, Any]):
        """标记记录为已处理"""
        if "processed_records" not in self.state:
            self.state["processed_records"] = {}
        if "processed_urls" not in self.state:
            self.state["processed_urls"] = {}

        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

        self.state["processed_records"][record_id] = {
            "url": url,
            "processed_at": datetime.now().isoformat(),
            **info
        }

        self.state["processed_urls"][url_hash] = {
            "record_id": record_id,
            "processed_at": datetime.now().isoformat(),
            **info
        }

        self._save_state()

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
                response.raise_for_status()
                result = response.json()

                if result.get("code") != 0:
                    self.logger.error(f"飞书API返回错误: {result.get('msg')}")
                    return None

                items = result.get("data", {}).get("items", [])
                all_records.extend(items)

                has_more = result.get("data", {}).get("has_more", False)
                if not has_more:
                    break

                page_token = result.get("data", {}).get("page_token")

            except Exception as e:
                self.logger.error(f"获取飞书记录失败: {e}")
                return None

        return all_records

    def parse_podcast_link(self, record: Dict) -> Optional[Dict[str, str]]:
        """解析播客记录，提取链接"""
        fields = record.get("fields", {})

        # 尝试提取小宇宙链接
        for key in ["链接", "link", "url", "网址", "小宇宙链接"]:
            if key in fields and fields[key]:
                url = fields[key]
                # 确保是字符串
                if isinstance(url, list) and len(url) > 0:
                    url = url[0]
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
        self.logger = setup_logging(config)
        self.state_manager = StateManager(config.state_file)
        self.feishu_client = FeishuClient(config, self.logger)
        self.tingwu_client = TingwuClient(config.tingwu_config)
        self.markdown_generator = MarkdownGenerator()

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

            # 2. 下载音频
            self.logger.info(f"下载音频: {episode_title}")

            # 清理文件名
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', episode_title)
            safe_title = safe_title[:100]

            # 确定扩展名
            ext = ".mp3"
            if ".m4a" in audio_url.lower():
                ext = ".m4a"
            elif ".wav" in audio_url.lower():
                ext = ".wav"

            audio_path = self.config.audio_dir / f"{safe_title}{ext}"

            if not download_audio(audio_url, str(audio_path)):
                self.logger.error(f"音频下载失败: {audio_url}")
                return False

            self.logger.info(f"音频已保存: {audio_path}")

            # 3. 上传到通义听悟进行转写
            self.logger.info("提交通义听悟转写任务...")
            task_result = self.tingwu_client.submit_with_file_upload(str(audio_path))

            if task_result.get('code') != 0:
                self.logger.error(f"提交转写任务失败: {task_result}")
                return False

            task_id = task_result.get('data', {}).get('task_id')
            self.logger.info(f"转写任务已提交: {task_id}")

            # 4. 等待转写完成
            self.logger.info("等待转写完成...")
            final_result = self.tingwu_client.wait_for_result(
                task_id,
                poll_interval=self.config.poll_interval,
                max_polls=self.config.max_polls
            )

            # 5. 解析转写结果
            self.logger.info("解析转写结果...")
            parsed_result = self.tingwu_client.parse_transcription_result(final_result)

            # 6. 生成Markdown笔记
            self.logger.info("生成Markdown笔记...")
            markdown_content = self.markdown_generator.generate(parsed_result)

            # 7. 保存笔记
            # 创建子文件夹（按日期或播客名称）
            date_folder = datetime.now().strftime("%Y-%m")
            episode_folder = self.config.notes_dir / date_folder
            episode_folder.mkdir(exist_ok=True)

            note_path = episode_folder / f"{safe_title}.md"

            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            self.logger.info(f"笔记已保存: {note_path}")

            # 标记为已处理
            self.state_manager.mark_record_processed(
                record_id,
                url,
                {
                    "title": episode_title,
                    "episode_id": episode_id,
                    "audio_path": str(audio_path),
                    "note_path": str(note_path),
                    "task_id": task_id
                }
            )

            self.logger.info(f"✅ 处理完成: {episode_title}")
            return True

        except Exception as e:
            self.logger.error(f"处理失败: {e}", exc_info=True)
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

            # 检查是否已处理
            if self.state_manager.is_record_processed(record_id):
                continue

            # 解析链接
            podcast_info = self.feishu_client.parse_podcast_link(record)
            if not podcast_info:
                continue

            url = podcast_info["url"]
            title = podcast_info["title"]

            # 检查URL是否已处理
            if self.state_manager.is_url_processed(url):
                self.logger.info(f"URL已处理过，跳过: {url}")
                self.state_manager.mark_record_processed(record_id, url, {"skipped": True})
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
