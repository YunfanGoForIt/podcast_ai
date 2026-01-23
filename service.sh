#!/bin/bash
# 播客自动化服务启动脚本

set -e

# 配置变量
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
SERVICE_NAME="podcast-service"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查虚拟环境
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log_info "创建虚拟环境..."
        python3 -m venv "$VENV_DIR"
    fi
}

# 安装依赖
install_deps() {
    log_info "检查并安装依赖..."
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
}

# 创建必要的目录
create_dirs() {
    log_info "创建必要的目录..."
    mkdir -p "$PROJECT_DIR/xiaoyuzhou_audio"
    mkdir -p "$PROJECT_DIR/notes"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/temp_audio"
}

# 检查配置文件
check_config() {
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_error ".env 文件不存在，请先创建配置文件"
        exit 1
    fi

    if [ ! -f "$PROJECT_DIR/config.yaml" ]; then
        log_error "config.yaml 文件不存在"
        exit 1
    fi
}

# 启动服务（前台运行）
start_foreground() {
    log_info "启动播客自动化服务（前台模式）..."
    cd "$PROJECT_DIR"
    exec "$PYTHON" podcast_service.py
}

# 启动服务（后台运行）
start_background() {
    log_info "启动播客自动化服务（后台模式）..."
    cd "$PROJECT_DIR"
    nohup "$PYTHON" podcast_service.py > logs/service.log 2>&1 &
    echo $! > podcast_service.pid
    log_info "服务已在后台启动，PID: $(cat podcast_service.pid)"
    log_info "查看日志: tail -f logs/service.log"
}

# 停止服务
stop_service() {
    if [ -f podcast_service.pid ]; then
        PID=$(cat podcast_service.pid)
        log_info "停止服务 (PID: $PID)..."
        kill "$PID" 2>/dev/null || true
        rm -f podcast_service.pid
        log_info "服务已停止"
    else
        log_warn "未找到运行中的服务"
    fi
}

# 重启服务
restart_service() {
    stop_service
    sleep 2
    start_background
}

# 查看状态
status_service() {
    if [ -f podcast_service.pid ]; then
        PID=$(cat podcast_service.pid)
        if ps -p "$PID" > /dev/null 2>&1; then
            log_info "服务正在运行 (PID: $PID)"
            log_info "最近日志:"
            tail -n 20 logs/service.log
        else
            log_error "PID文件存在但进程未运行"
            rm -f podcast_service.pid
        fi
    else
        log_info "服务未运行"
    fi
}

# 显示使用帮助
show_help() {
    cat << EOF
播客自动化服务管理脚本

用法: $0 [命令]

命令:
    install     安装依赖和初始化环境
    start       启动服务（后台模式）
    foreground  启动服务（前台模式，用于调试）
    stop        停止服务
    restart     重启服务
    status      查看服务状态
    logs        查看实时日志
    help        显示此帮助信息

示例:
    $0 install     # 首次使用，安装依赖
    $0 start       # 启动服务
    $0 status      # 查看状态
    $0 logs        # 查看日志
    $0 stop        # 停止服务

systemd 服务安装（推荐用于生产环境）:
    sudo cp podcast-service.service /etc/systemd/system/
    sudo sed -i 's|your_username|$(whoami)|g' /etc/systemd/system/podcast-service.service
    sudo sed -i 's|/path/to/your/project|$PROJECT_DIR|g' /etc/systemd/system/podcast-service.service
    sudo systemctl daemon-reload
    sudo systemctl enable podcast-service
    sudo systemctl start podcast-service
    sudo systemctl status podcast-service
EOF
}

# 查看日志
view_logs() {
    if [ -f logs/service.log ]; then
        tail -f logs/service.log
    else
        log_error "日志文件不存在"
    fi
}

# 主逻辑
case "${1:-}" in
    install)
        check_venv
        install_deps
        create_dirs
        check_config
        log_info "安装完成！运行 '$0 start' 启动服务"
        ;;
    start)
        check_config
        start_background
        ;;
    foreground|fg)
        check_config
        start_foreground
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        view_logs
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        show_help
        exit 1
        ;;
esac
