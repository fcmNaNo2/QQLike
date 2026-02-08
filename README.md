# QQ名片自动点赞机器人

基于 OneBot V11 标准和 NapCatQQ 实现的QQ名片自动点赞机器人。

## 功能特点

- ✅ 每天自动给指定好友点赞（最多10次/人/天）
- ✅ 支持多个小号同时点赞
- ✅ 定时任务，无需手动操作
- ✅ 请求间隔控制，避免频率过快
- 🐳 支持 Docker 一键部署

## 快速开始（Docker 推荐）

### 方式一：使用 Docker（推荐）

```bash
# 1. 修改配置
vim docker-compose.yml
# 修改 ACCOUNT（小号QQ）和 TARGET_FRIENDS（主号QQ）

# 2. 一键启动
./start.sh

# 3. 打开 WebUI 扫码登录（token 从 napcat 日志里复制）
#    docker compose logs --tail=50 napcat-account1 | grep -E "WebUi Token|User Panel Url"
#    然后访问 http://localhost:6099/webui?token=xxx

# 4. 打开点赞管理页面（手动点一次点赞 / 开关定时任务）
#    http://localhost:8088

# 5. 查看日志
docker compose logs -f
```

详细说明请查看 [Docker 部署指南](DOCKER_README.md)

### 方式二：直接运行 Python 脚本

## 前置要求

### 1. 安装 NapCatQQ

NapCatQQ 是基于 NTQQ 的现代化 Bot 协议端实现。

**下载地址**: [https://github.com/NapNeko/NapCatQQ/releases](https://github.com/NapNeko/NapCatQQ/releases)

**文档**: [https://napneko.github.io](https://napneko.github.io)

### 2. 配置 NapCatQQ

启动 NapCatQQ 并配置 HTTP 服务：

```json
{
  "http": {
    "enable": true,
    "host": "0.0.0.0",
    "port": 3000,
    "secret": "",
    "enableHeart": true,
    "enablePost": false
  }
}
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 配置脚本

编辑 `qq_auto_like_bot.py` 中的配置区域：

```python
# OneBot HTTP API 地址
API_URL = 'http://localhost:3000'

# 访问令牌（如果配置了的话）
ACCESS_TOKEN = None

# 要点赞的好友QQ号列表
TARGET_FRIENDS = [
    '123456789',  # 你的主号QQ
]

# 每个好友点赞次数（1-10）
LIKE_TIMES = 10

# 定时任务时间
SCHEDULE_TIME = '09:00'  # 每天早上9点
```

### 2. 运行机器人

```bash
python qq_auto_like_bot.py
```

### 3. 后台运行（Linux/macOS）

使用 screen 或 nohup：

```bash
# 使用 screen
screen -S qq_like_bot
python qq_auto_like_bot.py
# 按 Ctrl+A+D 退出 screen

# 使用 nohup
nohup python qq_auto_like_bot.py > like_bot.log 2>&1 &
```

## OneBot V11 API 说明

### send_like 接口

发送好友点赞。

**端点**: `/send_like`

**参数**:
- `user_id` (string/int): 对方 QQ 号
- `times` (int): 点赞次数，每个好友每天最多 10 次

**响应**:
```json
{
  "status": "ok",
  "retcode": 0,
  "data": null
}
```

### get_friend_list 接口

获取好友列表。

**端点**: `/get_friend_list`

**响应**:
```json
{
  "status": "ok",
  "retcode": 0,
  "data": [
    {
      "user_id": 123456789,
      "nickname": "昵称",
      "remark": "备注"
    }
  ]
}
```

## 多小号配置

如果你有多个小号，可以为每个小号运行一个机器人实例：

1. 每个小号启动一个 NapCatQQ 实例（使用不同端口）
2. 复制脚本并修改 API_URL 和端口
3. 分别运行各个脚本

**示例**:
```python
# 小号1 - 端口 3000
API_URL = 'http://localhost:3000'

# 小号2 - 端口 3001
API_URL = 'http://localhost:3001'

# 小号3 - 端口 3002
API_URL = 'http://localhost:3002'
```

## 注意事项

⚠️ **重要提示**:

1. 每个好友每天最多点赞 10 次（腾讯限制）
2. 建议设置合理的请求间隔（2-5秒），避免被检测
3. 不要频繁操作，可能导致账号异常
4. 仅供学习交流使用，请遵守相关法律法规
5. 使用小号操作，避免主号风险

## 故障排查

### 1. 连接失败

检查 NapCatQQ 是否正常运行：
```bash
curl -sS -X POST http://localhost:3000/get_login_info \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 2. 点赞失败

- 确认好友关系是否存在
- 检查是否已达到每日点赞上限
- 查看 NapCatQQ 日志

### 3. 获取好友列表为空

确保 QQ 已登录并且 NapCatQQ 连接正常。

## 参考资料

- [OneBot V11 标准](https://github.com/botuniverse/onebot-11)
- [NapCatQQ 项目](https://github.com/NapNeko/NapCatQQ)
- [NapCatQQ 文档](https://napneko.github.io)

## 许可证

本项目仅供学习交流使用，请勿用于非法用途。
