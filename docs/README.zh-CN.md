# SpriteForge 资产管理与图编辑工具

这一版分离本地管理工具、生成服务与 Amadeus 主 runtime。
组织仓库为 `Code-Amadeus/Amadeus-SpriteForge`。

![KTX2 角色预览与原始行为图](images/reviewer-ktx2-graph.png)

截图展示当前 reviewer 与单独提供的角色包；仓库内可直接运行的示例使用几何图形素材。

## 启动

```powershell
git clone https://github.com/Code-Amadeus/Amadeus-SpriteForge.git
cd Amadeus-SpriteForge
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[qa]"
.\.venv\Scripts\spriteforge.exe init workspace --demo
.\.venv\Scripts\spriteforge.exe review --workspace workspace
```

默认地址 `http://127.0.0.1:7788`，支持 `--port`、`--no-browser`。
基本编辑、预览和校验仅需 Python 标准库；QA 的可选依赖为 OpenCV 和 NumPy。
示例是自行生成的几何图形，不含现有角色素材。

## 功能与边界

- 导入 PNG 目录，发现具体帧文件夹及处理版本。
- 播放队列、逐帧检查、接缝 QA、已有口型素材的局部预览。
- 编辑行为图、唯一根节点、手动边和自动遍历权重。
- 明确选择节点帧目录、phase、间隔与循环方式。
- 保存前校验，原子替换图文件；失败保留原图。
- 使用同一份已选帧导出 Amadeus v1 KTX2 运行包。

Graph 的 `Preview selected clip` 与导出共用帧选择、时间和循环配置。
普通队列播放器的 FPS 是人工检视速度，不改变节点的导出间隔。

导出需独立安装 KTX-Software，传入 `--toktx`，命令见根 README。
这版不导出口型覆盖层；已有口型配置会阻止导出，除非明确选择 `--no-mouth`。
不会偷偷套用旧 Kurisu 专属的帧选择、口型修正或说话策略。

Amadeus 继续负责语义 intent、说话状态、嘴部振幅、呈现优先级、停留和回落。
单段预览不等于完整 TTS 表演模拟。生成服务、角色素材、场景图编辑器和完整
renderer 不在本次迁移内；场景图后续按独立契约整理。

代码和几何示例采用 AGPL-3.0-only，与迁入的 Amadeus 合同代码保持一致。
用户素材的许可不因此改变。来源见 `NOTICE.md`。


## 直接查看 KTX2

```powershell
spriteforge review --workspace examples/runtime-minimal
spriteforge review --workspace path/to/character-pack
```

检测到 runtime_manifest.json 时，按只读运行包打开，直接解码、显示和播放索引中的
KTX2，无需 PNG 原图或 toktx。PixiJS 和 Basis JS/WASM 解码器随仓库和 wheel 提供，
不依赖 CDN。需要支持 WebGL 的浏览器；已验证 Amadeus 使用的 UASTC KTX2，不宣称
覆盖所有 KTX2 编码。可播放、逐帧检查和查看行为图；图编辑及 QA 留在作者工作区。
