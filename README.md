# QQ名片自动点赞机器人

基于 OneBot V11 标准和 NapCatQQ 实现的QQ名片自动点赞机器人。支持多小号并发点赞，定时任务自动执行，提供Web管理界面。

## 功能特点

- ✅ 每天自动给指定好友点赞（最多10次/人/天）
- ✅ 支持多个小号同时点赞（最多5个）
- ✅ 定时任务，无需手动操作
- ✅ 请求间隔控制，避免频率过快
- ✅ Web管理界面，实时查看状态和手动控制
- ✅ 统一管理面板，聚合多个bot状态
- 🐳 支持 Docker 一键部署

## 快速开始

### 前置要求

- Docker & Docker Compose
- 多个QQ小号（用于点赞）
- 一个主号QQ（被点赞的账号）

### 配置步骤

1. **克隆项目**
```bash
git clone <repo-url>
cd QQLike
```

2. **配置环境变量**
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的QQ号：
```env
# 小号QQ号（必填）
ACCOUNT_1=你的小号1
ACCOUNT_2=你的小号2
ACCOUNT_3=你的小号3
ACCOUNT_4=你的小号4
ACCOUNT_5=你的小号5

# 主号QQ（必填）
TARGET_FRIENDS=你的主号QQ

# 其他配置（可选）
LIKE_TIMES=10
SCHEDULE_TIME=09:00
DELAY=2
```

3. **启动服务**
```bash
docker compose up -d
```

4. **扫码登录**

查看NapCat日志获取登录链接：
```bash
docker compose logs napcat-account1 | grep -E "WebUi Token|User Panel Url"
```

访问 `http://localhost:6099/webui?token=xxx` 扫码登录

5. **打开管理页面**

- 单个bot管理：http://localhost:8088
- 统一管理面板：http://localhost:8099

详细说明请查看 [Docker 部署指南](DOCKER_README.md)

## 项目结构

```
QQLike/
├── docker-compose.yml      # Docker 编排配置
├── Dockerfile              # Docker 镜像构建
├── .env.example            # 环境变量模板
├── .gitignore              # Git 忽略配置
├── qq_auto_like_bot.py     # 点赞机器人核心脚本
├── like_manager.py         # 统一管理面板
├── napcat_watchdog.py      # NapCat 监控脚本
├── napcat_templates/       # NapCat 配置模板
├── napcat_data/            # NapCat 数据目录（持久化）
├── like_bot_data/          # 点赞bot数据目录（持久化）
├── README.md               # 本文件
├── DOCKER_README.md        # Docker 详细指南
└── USAGE.md                # 使用说明
```

## 配置说明

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `ACCOUNT_1-5` | 小号QQ号 | `123456789` |
| `TARGET_FRIENDS` | 主号QQ（被点赞账号） | `987654321` |
| `LIKE_TIMES` | 每个好友点赞次数 | `10` |
| `SCHEDULE_TIME` | 定时执行时间 | `09:00` |
| `SCHEDULE_TIME_2-5` | 各小号定时时间（可选） | `09:05` |
| `DELAY` | 请求间隔（秒） | `2` |
| `ACCESS_TOKEN` | API访问令牌（可选） | `` |
| `NAPCAT_UID/GID` | 容器文件权限 | `1000` |

### 定时任务

默认每天 09:00 执行点赞任务。可通过 `SCHEDULE_TIME` 修改。

多小号时建议错开时间，避免同时请求：
- 小号1：09:00
- 小号2：09:05
- 小号3：09:10
- 小号4：09:15
- 小号5：09:20

## 常见问题

### Q: 如何添加更多小号？

A: 在 `docker-compose.yml` 中复制 `napcat-account5` 和 `like-bot5` 的配置，修改：
- 容器名称（如 `napcat_account6`）
- 端口号（如 `6104:6099`、`3005:3000`）
- 账号变量（如 `ACCOUNT_6`）
- 在 `.env` 中添加对应的 `ACCOUNT_6` 值

### Q: 点赞失败怎么办？

A: 检查以下几点：
1. 确认小号已登录（查看WebUI）
2. 确认主号和小号是好友关系
3. 检查是否已达到每日点赞上限（10次/人/天）
4. 查看容器日志：`docker compose logs like-bot1`

### Q: 如何查看日志？

A: 
```bash
# 查看所有日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f like-bot1
docker compose logs -f napcat-account1
```

### Q: 如何停止服务？

A:
```bash
# 停止所有服务
docker compose down

# 停止并删除数据
docker compose down -v
```

### Q: 如何更新代码？

A:
```bash
git pull
docker compose up -d --build
```

## 安全建议

⚠️ **重要提示**：

1. **不要提交敏感信息**：`.env` 文件已在 `.gitignore` 中，不会被提交
2. **使用小号操作**：避免主号风险
3. **合理设置间隔**：建议 2-5 秒，避免被检测
4. **监控账号状态**：定期检查小号是否异常
5. **遵守规则**：不要频繁操作，可能导致账号限制

## 技术栈

- **NapCatQQ**: QQ Bot 协议端实现
- **OneBot V11**: 统一的 Bot 协议标准
- **Python**: 脚本语言
- **Docker**: 容器化部署
- **Flask**: Web 管理界面

## 参考资源

- [OneBot V11 标准](https://github.com/botuniverse/onebot-11)
- [NapCatQQ 项目](https://github.com/NapNeko/NapCatQQ)
- [NapCatQQ 文档](https://napneko.github.io)
- [Docker 官方文档](https://docs.docker.com)

## 许可证

本项目仅供学习交流使用，请勿用于非法用途。使用本项目产生的一切后果由用户自行承担。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v1.0.0 (2026-02-08)
- 初始版本发布
- 支持5个小号并发点赞
- 完整的Web管理界面
- Docker 一键部署
