# 在线测评视觉防作弊

5174 端口的 H5 答题页请求浏览器摄像头权限，每 5 秒采集一张低分辨率 JPEG，发送到：

`POST /api/v1/assessment/result/{result_id}/vision`

后端只在内存中分析当前帧，不保存图片。异常会写入已有的 `asm_answer_event` 表，事件类型为 `vision`，便于管理端在测评详情中追溯。

## 技术与原理

- **YOLO（Ultralytics YOLO11n）**：对每帧做目标检测，识别 `person`、`cell phone`、`laptop`、`tablet` 等目标。检测结果包含类别、置信度和边界框；当前实现将检测到手机或其他计算设备标记为 `unauthorized_device`，检测到多个人标记为 `multiple_people`。
- **MediaPipe Face Mesh**：在同一帧上提取最多 3 张人脸的 468 个面部关键点，用人脸数量判断无人脸/多人脸。它是轻量级关键点模型，适合摄像头实时处理；后续可在此基础上加入头部姿态、视线和闭眼时长特征。
- **连续事件记录**：视觉异常、页面失焦、页面离开和摄像头权限失败都通过答题事件接口记录。视觉服务不会直接判定成绩，交卷仍由后端原有判分逻辑完成。

## 安装与配置

```powershell
pip install -r requirements.txt
```

首次分析帧时，Ultralytics 会按 `ANTI_CHEAT_MODEL_PATH` 加载 YOLO 权重；默认是项目启动目录下的 `yolo11n.pt`。生产环境建议预先下载权重并配置绝对路径：

```env
ANTI_CHEAT_ENABLED=true
ANTI_CHEAT_MODEL_PATH=D:/models/yolo11n.pt
ANTI_CHEAT_CONFIDENCE=0.35
```

如果依赖、权重或摄像头不可用，接口返回 `unavailable`，答题主流程仍可继续，并记录不可用事件。视觉提示属于风险信号，不应单独作为作弊结论；实际业务可按多次连续异常、人工复核或考试规则进行处置。微信小程序端不启用本次视觉监控。
