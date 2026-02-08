#!/bin/bash

echo "========================================"
echo "  QQ 自动点赞机器人 - Docker 快速部署"
echo "========================================"
echo ""
echo "📝 使用说明："
echo "   1. 小号：用来点赞的QQ账号（需要登录）"
echo "   2. 主号：被点赞的QQ账号（你的大号）"
echo ""
echo "🔧 配置步骤："
echo "   1. 编辑 docker-compose.yml"
echo "   2. 修改 ACCOUNT=你的小号QQ"
echo "   3. 修改 TARGET_FRIENDS=你的主号QQ"
echo ""
read -p "是否已完成配置？(y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请先修改 docker-compose.yml 中的配置"
    exit 1
fi

# 选择 Compose 命令（兼容 docker-compose / docker compose）
COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "安装指南: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker daemon 是否运行
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon 未启动或不可用"
    echo ""
    echo "请先启动 Docker Desktop（macOS: open -a Docker），等待 Docker 就绪后重试。"
    exit 1
fi

# 检查 Docker Compose 是否安装
if [[ -z "$COMPOSE_CMD" ]]; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    echo "安装指南: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker 环境检查通过"
echo ""

# 创建数据目录
mkdir -p napcat_data/account1/qq napcat_data/account1/config like_bot_data/account1
echo "✓ 创建数据目录"
echo ""

# NapCat-Docker 建议设置 UID/GID，避免持久化目录权限问题
export NAPCAT_UID="${NAPCAT_UID:-$(id -u)}"
export NAPCAT_GID="${NAPCAT_GID:-$(id -g)}"

# 启动服务
echo "正在启动服务..."
$COMPOSE_CMD up -d

echo ""
echo "========================================"
echo "✅ 服务启动完成！"
echo "========================================"
echo ""
echo "📱 下一步：登录小号QQ"
echo "   打开 WebUI（token 在 napcat 容器日志里）："
echo "   http://localhost:6099/webui?token=xxx"
echo ""
echo "   查看 token/登录链接："
echo "   $COMPOSE_CMD logs --tail=50 napcat-account1 | grep -E \"WebUi Token|User Panel Url\""
echo ""
echo "🖥️ 点赞管理页面："
echo "   http://localhost:8088"
echo ""
echo "📊 查看日志："
echo "   $COMPOSE_CMD logs -f"
echo ""
echo "🔍 检查状态："
echo "   $COMPOSE_CMD ps"
echo ""
echo "🛑 停止服务："
echo "   $COMPOSE_CMD down"
echo ""
echo "📖 详细说明："
echo "   查看 USAGE.md 文件"
echo ""
