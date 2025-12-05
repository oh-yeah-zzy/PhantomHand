# PhantomHand 👋

<div align="center">

![PhantomHand](https://img.shields.io/badge/PhantomHand-v0.1.0-00ffff?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178c6?style=for-the-badge&logo=typescript&logoColor=white)
![Tauri](https://img.shields.io/badge/Tauri-1.5+-ffc131?style=for-the-badge&logo=tauri&logoColor=white)

**🎮 用手势控制你的电脑，就像科幻电影一样！**

[功能特性](#-功能特性) •
[快速开始](#-快速开始) •
[手势指南](#-手势指南) •
[打包部署](#-打包部署) •
[架构设计](#-架构设计) •
[贡献指南](#-贡献指南)

</div>

---

## ✨ 功能特性

- 🖐️ **实时手势识别** - 基于 MediaPipe 的高精度手部追踪
- 🖱️ **鼠标控制** - 用手指移动光标，捏合点击
- 🎵 **媒体控制** - 握拳暂停/播放，滑动调节音量
- 🖥️ **窗口管理** - 滑动切换窗口
- 🎨 **炫酷可视化** - 赛博朋克风格的 3D 骨骼渲染
- ⚡ **低延迟** - 优化的推理管道，实时响应

## 📸 预览

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│    ╭──○ 指尖发光追踪                                        │
│    │                                                        │
│    ├──○ 霓虹色骨骼连线                                      │
│    │                                                        │
│    ○ 手掌识别 + 手势状态                                    │
│                                                             │
│         🎮 PhantomHand - 幻影之手                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- 摄像头设备
- Windows 10/11（目前仅支持）

### 安装步骤

**1. 克隆项目**

```bash
git clone https://github.com/yourusername/PhantomHand.git
cd PhantomHand
```

**2. 安装 Python 依赖**

```bash
cd python_service
pip install -r requirements.txt
```

**3. 安装前端依赖**

```bash
cd ../tauri_app
npm install
```

### 运行项目

**方式一：调试模式（推荐初次使用）**

```bash
cd python_service
python main.py --debug
```

这会打开一个预览窗口，可以直接看到手势识别效果。

**方式二：完整模式（服务器 + 前端）**

终端 1 - 启动后端服务：
```bash
cd python_service
python main.py
```

终端 2 - 启动前端（开发模式）：
```bash
cd tauri_app
npm run dev
```

然后在浏览器打开 `http://localhost:1420`

## 👋 手势指南

| 手势 | 动作 | 说明 |
|:---:|:---:|------|
| 🖐️ | **张开手掌** | 激活控制模式 |
| 👆 | **指向** | 移动鼠标光标 |
| 🤏 | **捏合** | 鼠标点击/拖拽 |
| ✊ | **握拳** | 播放/暂停媒体 |
| ✌️ | **剪刀手** | 截屏 |
| 👌 | **OK** | 静音切换 |
| 👋→ | **向左/右滑** | 切换窗口 |
| 👋↑ | **向上/下滑** | 调节音量 |

## 📦 打包部署

### 一键打包

在 Windows 环境下，运行打包脚本：

**PowerShell:**
```powershell
.\scripts\build-windows.ps1
```

**CMD:**
```cmd
scripts\build-windows.bat
```

### 打包产物

```
tauri_app/src-tauri/target/release/bundle/
├── msi/
│   └── PhantomHand_0.1.0_x64_en-US.msi    # MSI 安装包
└── nsis/
    └── PhantomHand_0.1.0_x64-setup.exe    # NSIS 安装包
```

### 打包要求

- Python 3.9+
- Node.js 18+
- Rust (通过 rustup 安装)
- Visual Studio Build Tools 2019+

详细打包指南请参考 [docs/BUILD.md](docs/BUILD.md)

## 🏗️ 架构设计

```
PhantomHand/
├── python_service/          # Python 后端服务
│   ├── core/                # 核心模块
│   │   ├── capture.py       # 摄像头采集
│   │   ├── detector.py      # 手部检测 (MediaPipe)
│   │   ├── gesture.py       # 手势分类
│   │   ├── state_machine.py # 状态机
│   │   └── action.py        # 系统动作执行
│   ├── config/              # 配置管理
│   ├── server.py            # WebSocket 服务
│   └── main.py              # 主入口
│
├── tauri_app/               # Tauri + React 前端
│   ├── src/
│   │   ├── canvas/          # 3D 可视化组件
│   │   ├── components/      # UI 组件
│   │   ├── stores/          # 状态管理 (Zustand)
│   │   └── types/           # TypeScript 类型
│   └── package.json
│
└── docs/                    # 文档
```

### 数据流

```
摄像头 → 帧采集 → MediaPipe检测 → 手势分类 → 状态机 → 动作执行
                       ↓
                  WebSocket
                       ↓
                前端可视化 (Three.js)
```

## ⚙️ 配置说明

配置文件位于 `python_service/config/settings.py`

```python
# 手势识别阈值
finger_extended_angle: float = 2.5   # 手指伸展角度阈值
pinch_distance_ratio: float = 0.25   # 捏合距离阈值

# 状态机参数
p_high: float = 0.7      # 手势进入阈值
t_enter: int = 120       # 手势确认时间(ms)
t_cooldown: int = 200    # 冷却时间(ms)

# 鼠标控制
mouse_sensitivity: float = 1.5  # 灵敏度
mouse_smoothing: float = 0.7    # 平滑系数
```

## 🛠️ 命令行参数

```bash
python main.py [OPTIONS]

选项：
  --debug, -d       启动调试模式（预览窗口）
  --test, -t        运行测试
  --host HOST       服务器地址 (默认: 127.0.0.1)
  --port, -p PORT   服务器端口 (默认: 8765)
  --camera, -c ID   摄像头设备ID (默认: 0)
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发环境设置

1. Fork 并克隆项目
2. 创建新分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交 Pull Request

### 代码风格

- Python: 遵循 PEP 8
- TypeScript: 使用 ESLint + Prettier

## 📝 待办事项

- [ ] macOS / Linux 平台支持
- [ ] 自定义手势训练
- [ ] 应用插件系统（PPT、IDE）
- [ ] GPU 加速推理
- [ ] 移动端控制

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

- [MediaPipe](https://mediapipe.dev/) - Google 的手部追踪方案
- [Three.js](https://threejs.org/) - 3D 可视化
- [Tauri](https://tauri.app/) - 跨平台桌面应用框架
- [React Three Fiber](https://github.com/pmndrs/react-three-fiber) - React 渲染器

---

<div align="center">

**如果觉得这个项目有趣，请给个 ⭐ Star！**

Made with ❤️ by PhantomHand Team

</div>
