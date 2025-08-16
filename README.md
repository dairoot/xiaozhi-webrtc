# XiaoZhi WebRTC

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

一个基于 WebRTC 实时音视频通信项目，集成了 XiaoZhi SDK 

## ✨ 功能特性

- [x] 集成 XiaoZhi 基础能力
- [x] 实时音视频通信
- [ ] 数字人 替换成视频或者h5（计划中）

## 🎯  在线体验

[https://xiaozhi.dairoot.cn](https://xiaozhi.dairoot.cn)

> 💡 **提示**: 由于部署在海外服务器，访问速度可能较慢


https://github.com/user-attachments/assets/525cc396-15e8-48ea-bd70-492845d055db

## 🚀 快速开始

```bash
# 克隆项目
git clone <repository-url>
cd xiaozhi-webrtc
```

#### 方法一：使用 uv（推荐）

```bash
# 安装 uv
pip install uv

# 安装项目依赖
uv sync

# 运行项目
uv run main.py
```

#### 方法二：使用 Docker

```bash
# 使用 Docker Compose 运行
docker compose up
```

#### 方法三：传统 pip 安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 运行项目
python main.py
```

## ⚙️ 部署要求

### 端口要求

WebRTC 需要以下端口用于实时音视频通信：

| 端口 | 协议 | 用途 |
|------|------|------|
| 3478 | UDP | STUN 服务 |
| 3478 / 5349 | TCP | TURN 服务 |
| 49152–65535 | UDP | WebRTC 媒体流端口（默认） |

**注意：** 确保防火墙允许这些端口的通信，特别是在生产环境中部署时。

### HTTPS 要求

**线上环境必须使用 HTTPS**：WebRTC 需要访问摄像头和麦克风，现代浏览器出于安全考虑只允许在 HTTPS 环境下使用这些功能。

## 📖 使用说明

1. **启动服务**: 运行项目后，服务将在 `http://localhost:8083` 或者 `https://yourdomain.com`  启动
2. **访问页面**: 在浏览器中打开上述地址
3. **授权权限**: 允许浏览器访问摄像头和麦克风
4. **开始通信**: 点击开始按钮建立 WebRTC 连接

**注意**: 生产环境必须使用 HTTPS，否则 WebRTC 功能将无法正常工作。
