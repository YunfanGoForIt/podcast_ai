# 播客自动化服务 - Linux 部署指南

## 功能说明

这是一个自动化播客处理服务，可以：
- 定时从飞书多维表格获取新的播客链接
- 自动下载小宇宙FM音频
- 调用通义听悟API进行语音转写和分析
- 自动生成Markdown格式笔记
- 按日期归档保存到本地文件夹

## 目录结构

```
播客解析/
├── podcast_service.py       # 主服务程序
├── service.sh               # 服务管理脚本
├── podcast-service.service  # systemd服务配置
├── config.yaml              # 配置文件
├── .env                     # 环境变量（需自行创建）
├── requirements.txt         # Python依赖
├── xiaoyuzhou_audio/        # 音频下载目录
├── notes/                   # 笔记保存目录
│   └── 2025-01/            # 按年月归档
├── logs/                    # 日志目录
├── podcast_state.json      # 状态记录文件
└── xiaoyuzhou_downloader.py
├── tingwu_client.py
├── markdown_generator.py
└── llm_client.py
```

## 部署步骤

### 1. 上传代码到服务器

```bash
# 使用scp上传
scp -r 播客解析/ user@your-server:/home/user/podcast_parser/

# 或使用rsync
rsync -av 播客解析/ user@your-server:/home/user/podcast_parser/
```

### 2. SSH登录服务器

```bash
ssh user@your-server
cd /home/user/podcast_parser
```

### 3. 安装Python和依赖

```bash
# 安装Python 3（如果没有）
sudo apt update
sudo apt install python3 python3-venv python3-pip -y

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 配置环境变量

编辑 `.env` 文件：

```bash
nano .env
```

填写以下内容：

```env
# 飞书配置
app_token=your_app_token
table_id=your_table_id
FEISHU_APP_ID=your_feishu_app_id
FEISHU_APP_SECRET=your_feishu_app_secret
```

### 5. 检查配置文件

确保 `config.yaml` 配置正确，特别是通义听悟的API密钥。

### 6. 创建必要目录

```bash
mkdir -p xiaoyuzhou_audio notes logs temp_audio
```

### 7. 测试运行

```bash
# 使用管理脚本
chmod +x service.sh
./service.sh install
./service.sh foreground
```

检查是否有错误，按 Ctrl+C 停止。

### 8. 启动服务

#### 方式1：使用管理脚本（推荐测试环境）

```bash
# 后台启动
./service.sh start

# 查看状态
./service.sh status

# 查看日志
./service.sh logs

# 停止服务
./service.sh stop
```

#### 方式2：使用systemd（推荐生产环境）

```bash
# 1. 复制服务文件
sudo cp podcast-service.service /etc/systemd/system/

# 2. 修改服务文件中的路径和用户名
sudo nano /etc/systemd/system/podcast-service.service
# 将 your_username 替换为实际用户名
# 将 /path/to/your/project 替换为实际项目路径

# 3. 重载systemd
sudo systemctl daemon-reload

# 4. 启用开机自启
sudo systemctl enable podcast-service

# 5. 启动服务
sudo systemctl start podcast-service

# 6. 查看状态
sudo systemctl status podcast-service

# 查看日志
sudo journalctl -u podcast-service -f
```

## 管理命令

### 使用管理脚本

```bash
./service.sh install    # 首次安装
./service.sh start      # 启动服务（后台）
./service.sh foreground # 前台运行（调试用）
./service.sh stop       # 停止服务
./service.sh restart    # 重启服务
./service.sh status     # 查看状态
./service.sh logs       # 查看实时日志
```

### 使用systemd

```bash
sudo systemctl start podcast-service      # 启动
sudo systemctl stop podcast-service       # 停止
sudo systemctl restart podcast-service    # 重启
sudo systemctl status podcast-service     # 状态
sudo journalctl -u podcast-service -f     # 日志
```

## 日志查看

日志文件位置：`logs/podcast_service_YYYYMMDD.log`

```bash
# 查看今天的日志
tail -f logs/podcast_service_$(date +%Y%m%d).log

# 查看最近100行
tail -n 100 logs/podcast_service_$(date +%Y%m%d).log

# 搜索错误
grep ERROR logs/podcast_service_*.log
```

## 工作原理

1. **定时检查**：每60秒检查一次飞书多维表格
2. **状态追踪**：通过 `podcast_state.json` 记录已处理的链接，避免重复
3. **处理流程**：
   - 获取episode信息
   - 下载音频文件
   - 上传到通义听悟转写
   - 等待转写完成
   - 生成Markdown笔记
   - 保存到 `notes/YYYY-MM/` 目录

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

## 故障排查

### 1. 服务无法启动

```bash
# 检查日志
./service.sh logs

# 或前台运行查看错误
./service.sh foreground
```

### 2. 飞书API错误

- 检查 `.env` 中的配置是否正确
- 确认飞书应用有权限访问多维表格

### 3. 通义听悟失败

- 检查 `config.yaml` 中的API密钥
- 确认账户余额充足
- 查看日志中的详细错误信息

### 4. 音频下载失败

- 检查网络连接
- 确认小宇宙链接有效
- 检查磁盘空间

## 状态文件

`podcast_state.json` 记录了所有已处理的播客：

```json
{
  "processed_records": {
    "record_id_1": {
      "url": "https://...",
      "processed_at": "2025-01-23T10:30:00",
      "title": "播客标题",
      "note_path": "notes/2025-01/标题.md"
    }
  },
  "processed_urls": {},
  "last_check_time": "2025-01-23T12:00:00"
}
```

如果需要重新处理某个播客，可以删除对应的记录。

## 性能优化

### 1. 并发处理

如果需要同时处理多个播客，可以修改代码使用多线程。

### 2. 磁盘清理

定期清理旧的音频文件：

```bash
# 清理30天前的音频
find xiaoyuzhou_audio/ -type f -mtime +30 -delete

# 清理旧日志
find logs/ -name "*.log" -mtime +90 -delete
```

### 3. 监控

使用系统监控工具：

```bash
# CPU和内存使用
htop

# 磁盘使用
df -h

# 服务状态
sudo systemctl status podcast-service
```

## 安全建议

1. **权限控制**：限制配置文件权限
   ```bash
   chmod 600 .env config.yaml
   ```

2. **日志轮转**：配置logrotate防止日志文件过大
   ```bash
   sudo nano /etc/logrotate.d/podcast-service
   ```

   内容：
   ```
   /home/user/podcast_parser/logs/*.log {
       daily
       rotate 30
       compress
       delaycompress
       missingok
       notifempty
   }
   ```

3. **防火墙**：如果不需要外部访问，关闭相关端口

## 更新服务

```bash
# 停止服务
./service.sh stop

# 拉取新代码
git pull  # 或重新上传文件

# 更新依赖
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
./service.sh start
```
