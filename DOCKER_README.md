# Docker 部署指南

使用 Docker 部署 QQ 自动点赞机器人，支持多小号管理。

## 快速开始

### 1. 修改配置

编辑 `docker-compose.yml`，修改以下配置：

```yaml
environment:
  - ACCOUNT=123456789      # 你的小号QQ
  - TARGET_FRIENDS=987654321  # 你的主号QQ（要被点赞的账号）
```

### 2. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f like-bot1
docker-compose logs -f napcat-account1
```

### 3. 登录 QQ

首次启动需要扫码登录：

1. 先从日志里复制 WebUI 登录链接（含 token）：
   ```bash
   docker compose logs --tail=50 napcat-account1 | grep -E "WebUi Token|User Panel Url"
   ```
2. 打开 WebUI：`http://localhost:6099/webui?token=xxx`
3. 扫码登录你的小号QQ
4. 登录成功后会自动保存登录状态（已挂载持久化目录）

### 4. 验证运行

```bash
# 检查服务状态
docker-compose ps

# 测试 API 连接
curl -sS -X POST http://localhost:3000/get_status \
  -H "Content-Type: application/json" \
  -d '{}'
```

管理页面（手动点赞一次 / 开关定时任务）：

`http://localhost:8088`

## 多小号配置

### 方案一：使用 docker-compose.yml（推荐）

取消注释 `docker-compose.yml` 中的小号2、小号3配置：

```yaml
# 取消这些行的注释
napcat-account2:
  # ...
like-bot2:
  # ...
```

然后重启：
```bash
docker-compose up -d
```

### 方案二：使用多个 compose 文件

为每个小号创建独立的配置文件：

**docker-compose.account2.yml**:
```yaml
version: '3.8'

services:
  napcat-account2:
    image: mlikiowa/napcat-docker:latest
    container_name: napcat_account2
    ports:
      - "6100:6099"
      - "3001:3000"
    environment:
      - NAPCAT_UID=${NAPCAT_UID:-1000}
      - NAPCAT_GID=${NAPCAT_GID:-1000}
      - ACCOUNT=234567890
      - HTTP_ENABLE=true
      - HTTP_PORT=3000
    volumes:
      - ./napcat_data/account2/qq:/app/.config/QQ
      - ./napcat_data/account2/config:/app/napcat/config
    restart: unless-stopped

  like-bot2:
    build: .
    container_name: like_bot_2
    environment:
      - API_URL=http://napcat-account2:3000
      - TARGET_FRIENDS=987654321
      - LIKE_TIMES=10
      - SCHEDULE_TIME=09:05
    depends_on:
      - napcat-account2
    restart: unless-stopped
```

启动：
```bash
docker-compose -f docker-compose.yml up -d
docker-compose -f docker-compose.account2.yml up -d
```

## 常用命令

### 服务管理

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart

# 重启特定服务
docker-compose restart like-bot1

# 停止但不删除容器
docker-compose stop
```

### 日志查看

```bash
# 查看所有日志
docker-compose logs

# 实时查看日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100

# 查看特定服务日志
docker-compose logs -f napcat-account1
docker-compose logs -f like-bot1
```

### 更新和重建

```bash
# 重新构建镜像
docker-compose build

# 强制重新构建
docker-compose build --no-cache

# 拉取最新镜像并重启
docker-compose pull
docker-compose up -d
```

### 数据管理

```bash
# 备份配置数据
tar -czf napcat_backup.tar.gz napcat_data/

# 恢复配置数据
tar -xzf napcat_backup.tar.gz

# 清理所有数据（谨慎使用）
docker-compose down -v
rm -rf napcat_data/
```

## 端口说明

| 服务 | WebUI 端口 | API 端口 | 说明 |
|------|-----------|---------|------|
| 小号1 | 6099 | 3000 | 第一个账号 |
| 小号2 | 6100 | 3001 | 第二个账号 |
| 小号3 | 6101 | 3002 | 第三个账号 |

访问 WebUI：`http://localhost:端口号`
（建议使用 `/webui` 路径，例如：`http://localhost:6099/webui`）

## 环境变量说明

### NapCatQQ 容器

| 变量 | 说明 | 默认值 |
|------|------|--------|
| ACCOUNT | QQ账号 | 必填 |
| NAPCAT_UID | 宿主机 UID（权限对齐） | 1000 |
| NAPCAT_GID | 宿主机 GID（权限对齐） | 1000 |
| MODE | OneBot11 配置模板名 | qqlike |
| WEBUI_TOKEN | WebUI Token（可选，未设置则自动生成） | 空 |
| WEBUI_PREFIX | WebUI 前缀（可选） | 空 |

### 点赞机器人容器

| 变量 | 说明 | 示例 |
|------|------|------|
| API_URL | NapCat API地址 | http://napcat-account1:3000 |
| ACCESS_TOKEN | 访问令牌 | 留空或填写token |
| TARGET_FRIENDS | 目标QQ号（逗号分隔） | 987654321,123456789 |
| LIKE_TIMES | 点赞次数 | 10 |
| SCHEDULE_TIME | 执行时间 | 09:00 |
| DELAY | 请求间隔（秒） | 2 |
| ADMIN_ENABLE | 启用管理页面 | true |
| ADMIN_PORT | 管理页面端口（容器内） | 8080 |
| STATE_FILE | 开关状态持久化文件 | /app/data/state.json |

## 故障排查

### 1. 容器无法启动

```bash
# 查看详细错误
docker-compose logs napcat-account1

# 检查端口占用
netstat -tuln | grep 3000
lsof -i :3000
```

### 2. 无法连接 API

```bash
# 查看 NapCat 端口是否已监听
docker compose logs --tail=200 napcat-account1 | grep -E "HTTP Server Adapter|Start On|Login"

# 从 like-bot 容器内测试（镜像里没有 curl/ping，用 python requests 即可）
docker exec -it like_bot_1 python - <<'PY'
import os, requests
url = os.environ["API_URL"].rstrip("/") + "/get_status"
r = requests.post(url, json={}, timeout=10)
print(r.status_code, r.text)
PY
```

### 3. QQ 登录失败

- 访问 WebUI 重新扫码登录
- 检查 QQ 账号是否正常
- 查看 NapCat 日志排查问题

### 4. 点赞失败

```bash
# 查看机器人日志
docker-compose logs -f like-bot1

# 检查 API 是否正常
curl -sS -X POST http://localhost:3000/get_login_info \
  -H "Content-Type: application/json" \
  -d '{}'

# 手动测试点赞
curl -X POST http://localhost:3000/send_like \
  -H "Content-Type: application/json" \
  -d '{"user_id": "987654321", "times": 10}'
```

## 性能优化

### 资源限制

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  napcat-account1:
    # ...
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### 日志轮转

```yaml
services:
  napcat-account1:
    # ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 安全建议

1. **不要暴露端口到公网**
   ```yaml
   ports:
     - "127.0.0.1:3000:3000"  # 只监听本地
   ```

2. **使用访问令牌**
   ```yaml
   environment:
     - ACCESS_TOKEN=your_secure_token_here
   ```

3. **定期备份数据**
   ```bash
   # 添加到 crontab
   0 2 * * * tar -czf /backup/napcat_$(date +\%Y\%m\%d).tar.gz /path/to/napcat_data/
   ```

4. **使用 Docker secrets**（生产环境）
   ```yaml
   secrets:
     access_token:
       file: ./secrets/access_token.txt
   ```

## 监控和告警

### 健康检查

```yaml
services:
  napcat-account1:
    # ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/get_login_info"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Watchtower 自动更新

```yaml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 86400  # 每天检查更新
```

## 参考资料

- [NapCatQQ Docker 镜像](https://hub.docker.com/r/mlikiowa/napcat-docker)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [NapCatQQ 官方文档](https://napneko.github.io)
