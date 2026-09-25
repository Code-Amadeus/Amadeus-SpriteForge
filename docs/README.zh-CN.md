# SpriteForge 资产生产、管理与图编辑工具

从一张 idle 参考图生产角色动画：姿态静帧、图生视频片段、take 审阅、QA、行为图，
最后导出 Amadeus 可用的 KTX2 角色包。图生视频服务是可选适配器，Amadeus 主 runtime
保持独立。组织仓库为 `Code-Amadeus/Amadeus-SpriteForge`。

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
生产管线里开启了口型集的说话循环会导出静音闭嘴叠加层（见下方"口型叠加层"）；
旧的作者端 `spriteforge_mouth_config.json` 仍会阻止导出，除非明确选择 `--no-mouth`。
不会偷偷套用旧 Kurisu 专属的帧选择、口型修正或说话策略。

Amadeus 继续负责语义 intent、说话状态、嘴部振幅、呈现优先级、停留和回落。
单段预览不等于完整 TTS 表演模拟。角色素材、prompt 正文、API key、模型权重、
场景图编辑器和完整 renderer 不在仓库内；场景图后续按独立契约整理。

## 生产管线

```powershell
spriteforge init studio
spriteforge production init --workspace studio --id kurisu --display-name Kurisu --canvas 764x1028
spriteforge production take import --workspace studio --pose idle master.png
spriteforge production take accept --workspace studio --pose idle TAKE
spriteforge production pose add --workspace studio shy
spriteforge production take import --workspace studio --pose shy shy.png
spriteforge production clip add --workspace studio shy_in --from idle --to shy
spriteforge production prepare --workspace studio --clip shy_in --output handoff/shy_in
spriteforge production take import --workspace studio --clip shy_in shy_in.mp4
spriteforge review --workspace studio   # 打开 /production 审批、弃用和渲染
```

- **静帧是唯一的几何标准**：基准姿态按取景放到画布上，批准后测出头顶和头部中心。
  其他姿态的静帧如果是底图的刚性拷贝（纯表情编辑，≥50% 特征匹配一致）就配准回去；
  姿态变了就保留生成器的构图，要求人工叠加确认。头顶、中心超出容差不能批准，
  确实要动的姿态（侧身、思考）用 `production pose expect` 记录有意偏移。
- **Take 不可变、不删除**：每次生成或导入都是一个 take，保存 prompt 快照、首尾帧输入、
  服务商任务号。每个片段只采用一个 take，弃用的 take 带原因留档，可恢复。
- **Prompt 是带版本的数据**：character / 固定约束 / 动作 / 姿态主题分块，保存即新增版本，
  take 记录用到的版本。仍含 `{{PLACEHOLDER: ...}}` 的 prompt 不会提交到付费服务。
- **渲染**：解码（显式 BT.709）→ 首尾分别配准到两端静帧 → pingpong → 插帧处理器 →
  抠图处理器 → 边缘保护 → 首尾锁定到静帧 → QA → 整体发布到
  `production/clips/<id>/output`，帧间隔等时序写进 `render.json`，`graph-sync` 同步到节点。
- **QA**：静帧几何、断帧、闪烁、首尾配准漂移、首尾接缝、循环接缝、图边接缝；
  阈值沿用接缝色差文档（循环 1.0/1.5/2.2 L*，图边 1.2/1.8/2.5 L*）。
  导出时绑定了生产片段的节点若过期、未同步或 QA 失败，导出会被拒绝。
- **服务商**：Wan 2.7（`DASHSCOPE_API_KEY`）和 Seedance（`ARK_API_KEY`），key 只从环境变量读。
  也可以在网页或 ComfyUI 里手动生成，再导入视频。

抠图和插帧是外部命令（目录进、目录出），`tools/processors/` 提供 anime-segmentation 和
GMFSS 的参考封装。详见 [生产管线说明](production.md)。

## 口型叠加层

说话循环里的嘴型就是视频本身；运行时只在"没在说话或 RMS ≤ 0.08"时，
在嘴部椭圆遮罩里贴一张闭嘴图。RMS 只决定显不显示，不选嘴型。所以生产端只算：

- **遮罩轨迹和范围**：在预期位置附近找说话时变化最大的区域定嘴，再逐帧模板跟踪（每帧最多 6px，中值平滑）；
- **闭嘴图和图上的嘴位置**，并按这个循环的肤色调色；
- **每帧"离闭嘴多远"**，运行时只在停帧、降帧采样时用它挑最闭嘴的一帧。

`production clip set C --mouth neutral` 开启（只允许循环）。闭嘴图默认用**共用闭嘴帧**
（基准 idle 静帧，所有表情复用），不用第 0 帧，因为从过渡进入的循环第 0 帧不一定闭嘴。
侧面等脸型不同的姿态用 `production mouth pose side --use side` 单独指定；
`production mouth shared POSE` 更换共用帧；单个片段可用 `--mouth-source still|frame:N|pose:ID` 覆盖。

共用闭嘴帧来自别的表情，肤色会不同（脸红、调色）。渲染时会在遮罩覆盖的嘴周皮肤上比较
循环和闭嘴图的平均 Lab，把闭嘴图的嘴部区域平移到循环的色调，结果存为
`output/.mouth/closed.png`，导出直接编码这张；平移超过 8 L* 会在 QA 里提示。
生产页的"模拟静音"预览按运行时同样的方式画遮罩、贴闭嘴图。

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
