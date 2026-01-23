# 播客自动化笔记生成服务

基于阿里云 Qwen ASR 和大语言模型的播客自动化转写和笔记生成服务，支持从飞书多维表格自动获取小宇宙播客链接，生成结构化 Markdown 笔记。

## ✨ 核心特性

### 🤖 AI 驱动的三步笔记生成
- **第1步：智能分段** - 根据话题内容自动分段（每小时约5段）
- **第2步：逐段精析** - 为每个分段生成详细笔记、关键要点和金句
- **第3步：整体概括** - 生成 600 字整体概括 + 6 条关键洞察

### 🎯 核心功能
- 🎙️ **语音转写** - 使用 Qwen ASR (DashScope) 高精度转写
- 📝 **智能笔记** - LLM 生成结构化笔记（整体概括 + 关键洞察 + 分段详情）
- 🔄 **自动化流程** - 定时监控飞书表格，自动处理新链接
- 💾 **双端同步** - 同时保存到本地和 Syncthing 目录
- 🔒 **单实例锁** - 防止多进程冲突
- 📊 **状态追踪** - 记录处理状态，失败记录自动跳过

### 📦 输出格式
生成的 Markdown 笔记包含：
- 整体概括（约600字）
- 关键洞察（6条精选）
- 分段详情（含时间戳、标题、内容总结、金句、关键要点）
- 完整逐字稿（带时间戳）

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Linux 服务器（推荐）或本地环境

### 2. 安装依赖

```bash
# 克隆项目
cd /path/to/podcast_ai  # 或你的项目路径

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

创建 `.env` 文件：

```bash
# 飞书多维表格配置
app_token=your_app_token
table_id=your_table_id
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret

# DashScope API Key (阿里云百炼)
# 获取地址: https://dashscope.console.aliyun.com/apiKey
DASHSCOPE_API_KEY=sk-your-dashscope-api-key

# Qwen ASR 模型名称
ASR_MODEL=qwen3-asr-flash-filetrans-2025-11-17
``` （这个是有免费额度的）

### 4. 配置 LLM

编辑 `config.yaml`：

```yaml
# LLM 配置 (支持多种模型)
llm:
  provider: "openai"  # 可选: openai, azure, anthropic
  api_key: "your-api-key"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 或其他 LLM API
  model: "qwen3-max"  # 或 gpt-4o, claude-sonnet-4-5-20251101 等
```

### 5. 启动服务

```bash
# 方式一：直接运行（前台）
python podcast_service.py

# 方式二：使用 screen（推荐，可以在服务器持久运行）
screen -S podcast
python podcast_service.py
# Ctrl+A+D 退出 screen

# 方式三：后台运行
nohup python podcast_service.py > /dev/null 2>&1 &
```

---

## 📋 配置说明

### DashScope API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/apiKey)
2. 创建 API Key
3. 复制到 `.env` 文件的 `DASHSCOPE_API_KEY`

### ASR 模型选择

在 `.env` 中配置 `ASR_MODEL`：

| 模型名称 | 说明 | 速度 | 准确率 |
|---------|------|------|--------|
| `qwen3-asr-flash-filetrans` | 快速模式（推荐） | 快 | 高 |
| `qwen3-asr-std-filetrans` | 标准模式 | 中 | 更高 |

### LLM 配置

支持多种 LLM 提供商：

**阿里云百炼（推荐，与 ASR 同一平台）**
```yaml
llm:
  provider: "openai"
  api_key: "sk-your-dashscope-key"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen3-max"
```

**OpenAI**
```yaml
llm:
  provider: "openai"
  api_key: "sk-your-openai-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"
```

**Anthropic Claude**
```yaml
llm:
  provider: "anthropic"
  api_key: "sk-your-anthropic-key"
  base_url: "https://api.anthropic.com"
  model: "claude-sonnet-4-5-20251101"
```

### 飞书多维表格配置

#### 获取配置信息

1. **App Token & Table ID**
   - 打开多维表格 URL：`https://xxx.feishu.cn/base/xxxxxx?table=tblxxxxx`
   - App Token: `xxxxxx`（base 后的部分）
   - Table ID: `tblxxxxx`（table= 后的值）

2. **App ID & Secret**
   - 访问 [飞书开放平台](https://open.feishu.cn/app)
   - 创建企业自建应用
   - 添加权限：
     - `bitable:app` - 查看、评论、创建和导出
   - 在"凭证与基础信息"中获取 App ID 和 App Secret

#### 表格字段要求

多维表格需包含以下字段之一：
- **播客链接**（URL 类型）- 小宇宙播客链接
- **链接**（URL 类型）
- **播客名称**（文本 类型）- 可选

### Syncthing 同步（可选）

笔记会自动同步到：`/var/lib/syncthing/podcast_notes/`

配置 Syncthing：
1. 安装 Syncthing
2. 添加文件夹 `/var/lib/syncthing/podcast_notes`
3. 确保目录权限正确（`www-data:www-data`）

---

## 📂 目录结构

```
podcast_ai/
├── podcast_service.py         # 主服务程序
├── qwen_asr_client.py         # Qwen ASR 客户端
├── llm_client.py              # LLM 客户端（三步流程）
├── markdown_generator.py      # Markdown 笔记生成器
├── xiaoyuzhou_downloader.py   # 小宇宙FM链接解析
├── config.yaml                # LLM 配置文件
├── .env                       # 环境变量（需自行创建）
├── requirements.txt           # Python 依赖
├── service.sh                 # 服务管理脚本
├── podcast-service.service    # systemd 配置
├── notes/                     # 本地笔记输出
│   └── {播客标题}.md
├── logs/                      # 日志目录
│   ├── podcast_service_*.log
│   └── podcast_service.lock   # 单实例锁文件
└── podcast_state.json         # 处理状态记录
```

---

## 🔄 工作流程

```
飞书多维表格
  ↓ (每60秒轮询)
解析小宇宙链接
  ↓
获取音频URL (无需下载)
  ↓
提交 Qwen ASR 转写任务
  ↓ (等待最多12分钟)
获取转写结果
  ↓
┌─────────────────────────┐
│ LLM 三步笔记生成         │
│ 第1步: 分段+整体概括     │
│ 第2步: 逐段生成详细笔记   │
│ 第3步: 最终概括+关键洞察  │
└─────────────────────────┘
  ↓
生成 Markdown 笔记
  ↓
保存到两个位置:
  - notes/{播客标题}.md
  - /var/lib/syncthing/podcast_notes/{播客标题}.md
  ↓
标记处理状态
```

### 状态管理

`podcast_state.json` 记录所有已处理的播客：

```json
{
  "processed_records": {
    "record_id": {
      "url": "https://www.xiaoyuzhoufm.com/episode/xxx",
      "title": "播客标题",
      "note_path": "/path/to/note.md",
      "task_id": "xxx",
      "processed_at": "2026-01-23T20:00:00"
    }
  },
  "processed_urls": {
    "url_hash": "record_id"
  },
  "last_check_time": "2026-01-23T20:00:00"
}
```

**失败记录**：
```json
{
  "failed": true,
  "error": "错误信息",
  "failed_at": "2026-01-23T20:00:00"
}
```

---

## 🛠️ 服务管理

### 使用 screen（推荐）

```bash
# 启动服务
screen -S podcast
python podcast_service.py
# 按 Ctrl+A+D 退出 screen

# 重新连接
screen -r podcast

# 停止服务
screen -S podcast -X quit
```

### 使用 systemd

```bash
# 复制服务文件
sudo cp podcast-service.service /etc/systemd/system/

# 修改路径和用户
sudo nano /etc/systemd/system/podcast-service.service

# 重载并启动
sudo systemctl daemon-reload
sudo systemctl enable podcast-service
sudo systemctl start podcast-service

# 查看状态
sudo systemctl status podcast-service

# 查看日志
sudo journalctl -u podcast-service -f

# 停止服务
sudo systemctl stop podcast-service
```

### 查看日志

```bash
# 查看最新日志
tail -f logs/podcast_service_20260123.log

# 查看所有日志
ls -lt logs/

# 搜索错误
grep ERROR logs/podcast_service_*.log
```

---

## 🧪 测试

### 测试 ASR 转写

```bash
# 单独测试 ASR 功能（需要实际的转写结果JSON文件）
python -c "
from qwen_asr_client import QwenASRClient
import logging

logging.basicConfig(level=logging.INFO)
client = QwenASRClient('your-api-key')

# 测试提交任务
result = client.submit_transcription(
    file_url='https://media.xyzcdn.net/xxx.m4a',
    model='qwen3-asr-flash-filetrans'
)
print(result)
"
```

### 测试 LLM 笔记生成

```bash
python test_llm.py
```

测试包含6个步骤：
1. 简单对话 - 测试 LLM 连接
2. 生成简短摘要
3. 提取关键要点
4. 第一步：分段
5. 第二步：单段笔记
6. 完整流程

---

## ⚙️ 高级配置

### 修改轮询间隔

编辑 `podcast_service.py` 第63行：

```python
self.check_interval = 60  # 秒，默认60秒
```

### 修改 ASR 超时时间

编辑 `podcast_service.py` 第371行：

```python
timeout=720,  # 秒，默认720秒（12分钟）
```

### 修改分段数量

分段数量由音频时长自动计算：
- 每 12 分钟左右一段（720秒）
- 约 1 小时的播客会产生 5 个分段

可在 `llm_client.py` 第314行修改：

```python
estimated_segments = max(5, int(total_duration / 720))
```

---

## ❓ 常见问题

### Q: 转写任务失败？
A: 检查以下几点：
1. API Key 是否正确
2. 音频 URL 是否可公开访问
3. 超时时间是否足够（默认12分钟）
4. 查看 `logs/podcast_service_*.log` 了解详细错误

### Q: LLM 笔记生成失败？
A:
1. 检查 `config.yaml` 中的 LLM 配置
2. 确认 API Key 有效
3. 检查网络连接
4. 失败时会降级到基础笔记格式

### Q: 处理失败的记录会重试吗？
A: 不会。失败记录会被标记 `failed: true`，下次轮询自动跳过。如需重新处理，删除 `podcast_state.json` 中的对应记录即可。

### Q: 如何重新处理某个播客？
A:
1. 打开 `podcast_state.json`
2. 找到对应的 `record_id`
3. 删除该记录
4. 重启服务

### Q: Syncthing 同步失败？
A:
1. 检查目录权限：`ls -la /var/lib/syncthing/podcast_notes`
2. 确保所有者是 `www-data`: `sudo chown -R www-data:www-data /var/lib/syncthing/podcast_notes`
3. 重启 Syncthing: `sudo systemctl restart syncthing@www-data.service`

### Q: 如何切换 ASR 模型？
A: 修改 `.env` 中的 `ASR_MODEL` 变量，然后重启服务。

### Q: 多个服务实例同时运行？
A: 不会。程序使用文件锁 `logs/podcast_service.lock` 确保只有一个实例运行。重复启动会报错："服务已在运行中！"

### Q: 笔记保存在哪里？
A: 两个位置：
1. 本地：`notes/{播客标题}.md`（相对于项目根目录）
2. Syncthing：`/var/lib/syncthing/podcast_notes/{播客标题}.md`

---

## 📊 成本估算

### DashScope Qwen ASR
- **Flash 模式**：约 ¥0.25/小时
- **Std 模式**：约 ¥0.5/小时

### LLM API (以 Qwen3-Max 为例)
- **分段**（1次调用）：约 ¥0.1
- **逐段笔记**（5次调用）：约 ¥0.5
- **最终概括**（1次调用）：约 ¥0.05
- **总计**：约 ¥0.65/小时播客

---

## 📝 更新日志

### v2.0 (2026-01-23)
- ✅ 从通义听悟迁移到 Qwen ASR
- ✅ 实现三步 LLM 笔记生成流程
- ✅ 新增 Syncthing 双端同步
- ✅ 新增单实例锁机制
- ✅ 新增失败记录标记
- ✅ 移除音频下载，直接使用 URL
- ✅ 优化状态管理和错误处理

### v1.0
- 初始版本，使用通义听悟 API

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
