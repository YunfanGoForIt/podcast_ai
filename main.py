#!/usr/bin/env python3
"""
播客解析工作流
使用通义听悟 API 转写播客音频，并通过 LLM 生成结构化笔记
"""
import sys
import argparse
from pathlib import Path

import yaml

from tingwu_client import TingwuClient
from llm_client import LLMManager
from markdown_generator import MarkdownNoteGenerator


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def parse_podcast(
    audio_path: str,
    config_path: str = "config.yaml",
    output_dir: str = None
) -> str:
    """
    解析播客音频，生成笔记

    Args:
        audio_path: 音频文件路径
        config_path: 配置文件路径
        output_dir: 输出目录（覆盖配置）

    Returns:
        生成的笔记文件路径
    """
    print(f"📁 加载配置文件: {config_path}")
    config = load_config(config_path)

    # 验证音频文件
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    print(f"🎙️ 开始解析播客: {audio_file.name}")
    print(f"   文件大小: {audio_file.stat().st_size / 1024 / 1024:.2f} MB")

    # 初始化客户端
    print("🔧 初始化通义听悟客户端...")
    tingwu_client = TingwuClient(config['aliyun'])

    # 初始化LLM
    print("🤖 初始化LLM客户端...")
    llm_manager = LLMManager(config['llm'])

    # 初始化笔记生成器
    output_directory = output_dir or config['output'].get('notes_dir', './notes')
    note_generator = MarkdownNoteGenerator(output_directory)

    # 提交转写任务
    print("📤 提交转写任务...")
    try:
        submit_result = tingwu_client.submit_with_file_upload(str(audio_file))
        task_id = submit_result.get('data', {}).get('task_id')

        if not task_id:
            raise Exception(f"获取任务ID失败: {submit_result}")

        print(f"✅ 任务已提交，任务ID: {task_id}")

        # 等待转写完成
        poll_interval = config['task'].get('poll_interval', 10)
        max_polls = config['task'].get('max_polls', 120)

        print("⏳ 等待转写完成（每10秒检查一次）...")
        result = tingwu_client.wait_for_result(task_id, poll_interval, max_polls)
        print("✅ 转写完成！")

    except Exception as e:
        print(f"❌ 转写失败: {e}")
        raise

    # 解析转写结果
    print("📝 解析转写结果...")
    parsed_data = tingwu_client.parse_transcription_result(result)

    print(f"   - 获取到 {len(parsed_data.get('transcription', []))} 条对话")
    print(f"   - 获取到 {len(parsed_data.get('chapters', []))} 个章节")
    print(f"   - 说话人: {', '.join(parsed_data.get('speakers', set()))}")
    print(f"   - 关键词: {', '.join(parsed_data.get('keywords', []))}")

    # 调用LLM生成笔记
    print("🎨 调用LLM生成智能笔记...")
    llm_notes = llm_manager.generate_podcast_notes(
        transcription=parsed_data['transcription'],
        chapters=parsed_data['chapters'],
        summary=parsed_data['summary'],
        keywords=parsed_data['keywords']
    )
    print("✅ 笔记生成完成！")

    # 生成Markdown笔记
    print("📄 生成Markdown笔记...")
    output_path = note_generator.generate(
        audio_name=audio_file.name,
        parsed_data=parsed_data,
        llm_notes=llm_notes
    )

    return output_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="播客解析工具 - 将播客音频转换为结构化笔记"
    )
    parser.add_argument(
        "audio",
        help="播客音频文件路径"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="输出目录（覆盖配置）"
    )

    args = parser.parse_args()

    try:
        output_path = parse_podcast(
            audio_path=args.audio,
            config_path=args.config,
            output_dir=args.output
        )
        print(f"\n✨ 完成！笔记已保存至: {output_path}")
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
