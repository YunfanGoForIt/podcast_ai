# 播客解析工作流

使用通义听悟 API 将播客音频转换为结构化的 Markdown 笔记，支持自动化处理流程。

## 功能特性

### 核心功能
- 🎙️ **音频转写**：使用通义听悟 API 将播客音频转为逐字稿
- 📑 **章节速览**：自动识别播客章节结构
- 🏷️ **关键词提取**：自动提取内容关键词
- 🤖 **智能总结**：调用 LLM 生成结构化笔记
- ✨ **金句提取**：从逐字稿中提取嘉宾金句
- 📝 **Markdown输出**：生成易于阅读的 Markdown 笔记

### 自动化服务
- 🔄 **定时监控**：每分钟自动检查飞书多维表格的新链接
- ⬇️ **自动下载**：从小宇宙FM自动下载播客音频
- 🚀 **自动转写**：调用通义听悟API进行语音分析
- 📁 **智能归档**：按日期自动归档笔记到子文件夹
- 💾 **状态追踪**：记录已处理的播客，避免重复处理

---

## 快速开始

### 方式一：手动处理单个音频

```bash
pip install -r requirements.txt
python main.py podcast.mp3
```

### 方式二：自动化服务（推荐）

```bash
# 安装依赖
./service.sh install

# 配置.env文件（填写飞书和通义听悟配置）
nano .env

# 启动服务
./service.sh start
```

服务会自动监控飞书表格，发现新链接后自动下载、转写、生成笔记。

---

## 手动处理配置

### 1. 开通通义听悟服务

1. 登录[阿里云控制台](https://console.aliyun.com/)
2. 搜索"通义听悟"或访问[通义听悟控制台](https://nls-portal.console.aliyun.com/tingwu/overview)
3. 点击"立即开通"，选择"试用"（免费90天，每天2小时额度）

### 2. 创建项目

1. 在通义听悟控制台左侧点击"我的项目"
2. 点击"创建项目"
3. 填写配置：
   - **项目名称**：任意名称，如"播客转写"
   - **回调方式**：选择"不设置回调主动轮询"（推荐）
   - **对象存储**：可跳过
4. 点击"创建"，完成后在项目列表复制 **Appkey**

### 3. 创建 AccessKey

1. 访问 [RAM 访问控制台](https://ram.console.aliyun.com/manage/ak)
2. 点击"创建 AccessKey"
3. 复制 **AccessKey ID** 和 **AccessKey Secret**

### 4. 编辑配置文件

编辑 `config.yaml`：

```yaml
# 阿里云通义听悟配置
aliyun:
  access_key_id: "你的AccessKey ID"
  access_key_secret: "你的AccessKey Secret"
  appkey: "你的Appkey"  # 从通义听悟控制台获取
  region_id: "cn-shanghai"

# LLM 配置（支持 OpenAI / Azure / Anthropic）
llm:
  provider: "openai"
  api_key: "你的OpenAI API Key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"
```

---

## 自动化服务配置

### 1. 飞书配置

创建 `.env` 文件：

```env
# 飞书多维表格配置
app_token=your_app_token
table_id=your_table_id
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
```

#### 获取飞书配置信息：

1. **App Token**：打开多维表格，URL格式为 `https://xxx.feishu.cn/base/xxxxxx?table=tblxxxxx`
   - App Token: `xxxxxx`（base后的部分）

2. **Table ID**：URL中 `table=` 后的值（如 `tblxxxxx`）

3. **App ID & Secret**：
   - 访问 [飞书开放平台](https://open.feishu.cn/app)
   - 创建企业自建应用
   - 在"权限管理"中添加权限：
     - `bitable:app`（查看、评论、创建和导出多维表格）
     - `bitable:app:readonly`（只读权限）
   - 在"凭证与基础信息"中获取 App ID 和 App Secret

### 2. 飞书表格字段要求

多维表格需要包含以下字段之一：
- **链接**（URL类型）：小宇宙播客链接
- **播客名称**（文本类型）：可选

---

## 自动化服务使用

### 本地运行（用于测试）

```bash
# 前台运行（查看日志）
./service.sh foreground

# 后台运行
./service.sh start

# 查看状态
./service.sh status

# 查看日志
./service.sh logs

# 停止服务
./service.sh stop
```

### Linux服务器部署（生产环境）

#### 使用 systemd 服务（推荐）

```bash
# 1. 复制服务文件
sudo cp podcast-service.service /etc/systemd/system/

# 2. 修改服务文件中的路径和用户名
sudo nano /etc/systemd/system/podcast-service.service
# 将 your_username 替换为实际用户名
# 将 /path/to/your/project 替换为实际项目路径

# 3. 重载并启动
sudo systemctl daemon-reload
sudo systemctl enable podcast-service
sudo systemctl start podcast-service

# 4. 查看状态
sudo systemctl status podcast-service
sudo journalctl -u podcast-service -f
```

详细的部署指南请查看 [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 目录结构

```
播客解析/
├── main.py                  # 手动处理主程序
├── podcast_service.py       # 自动化服务主程序
├── service.sh               # 服务管理脚本
├── podcast-service.service  # systemd服务配置
├── DEPLOYMENT.md            # Linux部署详细文档
├── tingwu_client.py         # 通义听悟 API 客户端
├── llm_client.py            # LLM 客户端
├── markdown_generator.py    # Markdown 笔记生成器
├── xiaoyuzhou_downloader.py # 小宇宙FM下载器
├── test_feishu.py           # 飞书API测试
├── config.yaml              # 配置文件
├── .env                     # 环境变量（需自行创建）
├── requirements.txt         # 依赖列表
├── xiaoyuzhou_audio/        # 音频下载目录
├── notes/                   # 笔记保存目录
│   └── 2025-01/            # 按年月归档
├── logs/                    # 日志目录
│   └── podcast_service_*.log
└── podcast_state.json       # 状态记录（自动生成）
```

---

## 自动化服务工作流程

```
1. 定时检查飞书表格（每分钟）
   ↓
2. 发现新链接
   ↓
3. 获取小宇宙episode信息
   ↓
4. 下载音频文件
   ↓
5. 上传通义听悟转写
   ↓
6. 等待转写完成（轮询）
   ↓
7. 生成Markdown笔记
   ↓
8. 保存到 notes/YYYY-MM/ 目录
   ↓
9. 更新状态记录（避免重复）
```

### 状态管理

`podcast_state.json` 记录所有已处理的播客：

```json
{
  "processed_records": {
    "record_id": {
      "url": "https://...",
      "processed_at": "2025-01-23T10:30:00",
      "title": "播客标题",
      "note_path": "notes/2025-01/标题.md"
    }
  },
  "last_check_time": "2025-01-23T12:00:00"
}
```

如需重新处理某个播客，删除对应记录即可。

---

## 手动处理单个音频

### 音频上传方式

**你不需要手动上传到任何地方！** 程序会自动处理。

运行程序时，只需指定本地音频文件路径：

```bash
python main.py 你的播客文件.mp3
python main.py "E:\播客\ episode001.m4a"
python main.py "C:\Users\xxx\Downloads\播客音频.wav"
```

支持的音频格式：
- MP3、M4A、WAV、FLAC、OGG、AAC
- 单文件最大 1GB（可在 config.yaml 中修改限制）

### 使用方法

```bash
# 基本用法
python main.py podcast.mp3

# 指定配置文件
python main.py -c myconfig.yaml podcast.mp3

# 指定输出目录
python main.py -o ./my_notes podcast.mp3
```

### 运行流程

```
1. 提交音频 → 2. 等待转写 → 3. 获取结果 → 4. LLM总结 → 5. 生成笔记
```

---

## 输出示例

生成的 Markdown 笔记包含以下内容：

```markdown
# 播客笔记：xxx

## 概览
- 关键词：AI、技术、未来
- 播客摘要：...

## 章节速览
| 章节 | 标题 | 时间范围 |
|------|------|----------|
| 1 | 开场介绍 | 00:00-05:30 |
| 2 | 核心话题 | 05:30-25:00 |

## AI 智能总结
### 第一章：章节标题
**内容总结**：...

**嘉宾金句**：
> "金句内容"

**关键要点**：
- 要点1

## 完整逐字稿
[speaker] 00:00 - 00:30
对话内容...
```

---

## 配置说明

### 检查间隔

编辑 `podcast_service.py` 中的 `check_interval`：

```python
self.check_interval = 60  # 秒，默认1分钟
```

### 通义听悟轮询

在 `config.yaml` 中配置：

```yaml
task:
  poll_interval: 10  # 轮询间隔（秒）
  max_polls: 120     # 最大轮询次数
```

---

## 常见问题

**Q: 提示 "没有权限" 或 "OSS" 错误？**
A: 在 RAM 控制台给子账户添加 `AliyunTingwuFullAccess` 权限

**Q: 轮询超时？**
A: 检查 config.yaml 中的 `max_polls` 设置，或音频文件过大

**Q: 支持批量处理吗？**
A: 自动化服务会自动批量处理飞书表格中的所有新链接

**Q: 如何切换 LLM 提供商？**
A: 修改 config.yaml 中的 `llm.provider`，支持 `openai`、`azure`、`anthropic`

**Q: 飞书表格如何配置？**
A: 需要包含"链接"字段（URL类型），填入小宇宙播客链接

**Q: 如何查看服务日志？**
A:
- 本地: `./service.sh logs` 或 `tail -f logs/podcast_service_*.log`
- systemd: `sudo journalctl -u podcast-service -f`

---

## 依赖安装

```bash
pip install -r requirements.txt
```

主要依赖：
- `requests` - HTTP请求
- `pyyaml` - YAML配置解析
- `python-dotenv` - 环境变量管理
- `openai` / `anthropic` - LLM API（可选）
