#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析小宇宙FM链接并下载音频
"""

import os
import json
import requests
import re
from urllib.parse import urlparse

# 输出目录
OUTPUT_DIR = "xiaoyuzhou_audio"

# 小宇宙API
XIAOYUZHOU_API = "https://www.xiaoyuzhoufm.com/episode"


def get_episode_info(episode_url):
    """
    获取小宇宙episode信息

    小宇宙有两种链接格式:
    1. https://www.xiaoyuzhoufm.com/episode/xxxxx
    2. https://www.xiaoyuzhoufm.com/podcast/xxxxx/episode/xxxxx
    """
    # 提取episode ID
    match = re.search(r'/episode/([a-zA-Z0-9]+)', episode_url)
    if not match:
        print(f"[ERROR] 无法从链接中提取episode ID: {episode_url}")
        return None

    episode_id = match.group(1)
    print(f"[OK] Episode ID: {episode_id}")

    # 调用小宇宙Web API
    api_url = f"{XIAOYUZHOU_API}/{episode_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()

        # 小宇宙返回的是HTML，需要从HTML中提取JSON数据
        html = response.text

        # 尝试从HTML中提取JSON数据
        # 查找 window.__NUXT__ 或类似的JSON数据
        json_match = re.search(r'window\.__NUXT__\s*=\s*(.+?);?\s*</script>', html)
        if json_match:
            try:
                json_str = json_match.group(1)
                # 小宇宙的JSON数据可能需要处理
                data = json.loads(json_str)
                return parse_nuxt_data(data, episode_id)
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON解析失败: {e}")

        # 尝试查找其他JSON模式
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*(.+?);?\s*</script>',
            r'<script\s+id\s*=\s*"__NEXT_DATA__"\s+type\s*=\s*"application/json"\s*>\s*(.+?)\s*</script>',
        ]

        for pattern in patterns:
            json_match = re.search(pattern, html)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                    return parse_nuxt_data(data, episode_id)
                except json.JSONDecodeError:
                    continue

        print("[WARN] 无法从页面中提取JSON数据")
        print("[INFO] 尝试直接查找音频链接...")

        # 直接搜索音频链接
        audio_patterns = [
            r'"url"\s*:\s*"([^"]+\.mp3[^"]*)"',
            r'"audio"\s*:\s*"([^"]+)"',
            r'https://[^"]+\.mp3[^"]*',
            r'https://audio\.qssapp\.com/[^"]+',
            r'https://st\.xiaoyuzhoufm\.com/[^"]+',
        ]

        for pattern in audio_patterns:
            matches = re.findall(pattern, html)
            if matches:
                audio_url = matches[0] if isinstance(matches[0], str) else matches[0][0]
                print(f"[OK] 找到音频链接: {audio_url}")
                return {
                    "episode_id": episode_id,
                    "audio_url": audio_url,
                    "title": f"Episode_{episode_id}"
                }

        print("[ERROR] 无法找到音频链接")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 请求失败: {e}")
        return None


def parse_nuxt_data(data, episode_id):
    """解析NUXT数据"""
    # 尝试不同的数据路径
    possible_paths = [
        lambda d: d.get("data", [{}])[0].get("data", {}) if isinstance(d.get("data"), list) else d.get("data", {}),
        lambda d: d.get("state", {}).get("episode", {}),
        lambda d: d.get("props", {}).get("pageProps", {}).get("episode", {}),
        lambda d: d if isinstance(d, dict) and "audio" in d else {},
    ]

    for path_func in possible_paths:
        try:
            episode_data = path_func(data)
            if episode_data:
                # 提取音频URL
                audio_url = None
                for key in ["audio", "audio_url", "url", "enclosure", "media_url"]:
                    if key in episode_data:
                        audio_url = episode_data[key]
                        if isinstance(audio_url, dict):
                            audio_url = audio_url.get("url", audio_url.get("src"))
                        break

                if not audio_url and "data" in episode_data:
                    audio_url = episode_data["data"].get("audio")

                if audio_url:
                    # 提取标题
                    title = episode_data.get("title") or episode_data.get("name") or f"Episode_{episode_id}"

                    return {
                        "episode_id": episode_id,
                        "audio_url": audio_url,
                        "title": title,
                        "raw_data": episode_data
                    }
        except (KeyError, IndexError, TypeError):
            continue

    return None


def download_audio(audio_url, output_path):
    """下载音频文件"""
    try:
        print(f"\n开始下载: {audio_url}")
        print(f"保存到: {output_path}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaoyuzhoufm.com/",
        }

        response = requests.get(audio_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        print(f"文件总大小: {total_size / (1024*1024):.2f} MB")

        downloaded_size = 0
        chunk_size = 8192

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)

                    # 显示进度
                    if total_size > 0:
                        percent = (downloaded_size / total_size) * 100
                        print(f"\r进度: {percent:.1f}% ({downloaded_size/(1024*1024):.2f} MB)", end="")

        print(f"\n[OK] 下载完成!")
        return True

    except Exception as e:
        print(f"\n[ERROR] 下载失败: {e}")
        return False


def main():
    """主函数"""
    print("="*60)
    print("小宇宙FM音频下载工具")
    print("="*60)

    # 从飞书多维表格获取的链接
    episode_url = "https://www.xiaoyuzhoufm.com/episode/69608f978f388c61e1fa0ad0"

    print(f"\n解析链接: {episode_url}")

    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 获取episode信息
    episode_info = get_episode_info(episode_url)

    if not episode_info:
        print("[ERROR] 无法获取episode信息")
        return

    print(f"\nEpisode信息:")
    print(f"  ID: {episode_info.get('episode_id')}")
    print(f"  标题: {episode_info.get('title')}")
    print(f"  音频: {episode_info.get('audio_url')}")

    # 下载音频
    audio_url = episode_info.get('audio_url')
    if audio_url:
        # 生成文件名
        title = episode_info.get('title', f"episode_{episode_info.get('episode_id')}")
        # 清理文件名
        title = re.sub(r'[<>:"/\\|?*]', '_', title)
        title = title[:100]  # 限制长度

        # 确定扩展名
        ext = ".mp3"
        if ".m4a" in audio_url.lower():
            ext = ".m4a"
        elif ".wav" in audio_url.lower():
            ext = ".wav"

        output_path = os.path.join(OUTPUT_DIR, f"{title}{ext}")

        download_audio(audio_url, output_path)
    else:
        print("[ERROR] 未找到音频链接")


if __name__ == "__main__":
    main()
