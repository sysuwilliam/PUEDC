# 🎯 Rectangle Detection MCU Control

通过HTTP获取MPU侧的矩形检测结果，并通过Serial Wire输出检测数据。

## 功能特性

- **HTTP通信**：通过HTTP请求获取检测结果
- **Bridge通信**：通过Bridge RPC调用MCU函数
- **Serial Wire输出**：通过Monitor.println()输出检测数据
- **LED状态指示**：板载LED指示检测状态
- **实时响应**：检测延迟 < 15ms
- **离线支持**：使用局域网IP，支持离线运行

## 混合架构说明

本系统采用**MPU-MCU混合架构**，通过HTTP通信：

```
MPU侧（OpenCV视觉检测）         MCU侧（本项目）
    │                              │
    ├─ OpenCV视觉检测              ├─ HTTP请求
    ├─ 矩形中心计算                ├─ Bridge通信
    └─ HTTP服务 :8080 ───────────►  └─ Serial Wire输出
              HTTP GET
           /result.json
```

**通信方式**：HTTP over 局域网（支持离线运行）

**MPU服务地址**：`http://<设备IP>:8080/result.json`

⚠️ **重要说明**：
- MCU侧运行在App Lab容器中，容器内的`localhost`指向容器自己
- 必须使用宿主系统的实际IP地址（如`10.83.100.145`）
- 可以通过环境变量`MPU_HOST`配置，或直接修改代码中的默认IP

## Serial Wire输出效果

### 检测到矩形时

```
检测成功: 中心=(320, 240) 偏差=(10, -5)
```

### 未检测到时

```
未检测到矩形
```

```
⚠️  未检测到矩形 - 丢失次数: 1
```

## LED状态指示

| 状态 | LED | 说明 |
|------|-----|------|
| 启动时 | 熄灭 | 初始状态 |
| 检测到矩形 | 点亮 | 检测成功 |
| 未检测到 | 熄灭 | 检测失败 |

## 运行

### 方法1：使用App Lab界面

1. 打开Arduino App Lab
2. 找到`rectangle-detection`应用
3. 点击"Start"按钮

### 方法2：使用命令行

```bash
arduino-app-cli app start user:rectangle-detection
```

## 停止

### 方法1：使用App Lab界面

1. 打开Arduino App Lab
2. 找到`rectangle-detection`应用
3. 点击"Stop"按钮

### 方法2：使用命令行

```bash
arduino-app-cli app stop user:rectangle-detection
```

## 项目结构

```
rectangle-detection/
├── app.yaml             # App配置
├── README.md            # 本文档
├── python/
│   └── main.py          # Python端：读取共享文件+Bridge调用
└── sketch/
    ├── sketch.ino       # Arduino端：Serial Wire输出
    └── sketch.yaml      # Arduino库依赖配置
```

## 工作流程

### Python端（MPU侧）

```python
1. 每10ms检查一次共享文件
2. 读取检测结果（timestamp, rect_detected, center, error）
3. 检查时间戳，判断是否为新数据
4. 如果是新数据：
   - 检测到矩形 → Bridge.call("on_rect_detected", cx, cy, ex, ey)
   - 未检测到 → Bridge.call("on_rect_lost")
```

### Arduino端（MCU侧）

```cpp
1. 接收Bridge RPC调用
2. on_rect_detected(cx, cy, ex, ey):
   - 更新状态和计数
   - 点亮LED
   - Monitor.println()输出详细信息
3. on_rect_lost():
   - 更新状态和计数
   - 熄灭LED
   - Monitor.println()输出警告
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| MPU_URL | http://localhost:8080/result.json | MPU侧HTTP接口 |
| CHECK_INTERVAL | 0.01 (10ms) | 检查间隔 |
| TIMEOUT | 0.1 (100ms) | HTTP请求超时 |

## Bridge RPC接口

### on_rect_detected(cx, cy, ex, ey)

**功能**：处理矩形检测成功

**参数**：
- `cx`: 矩形中心x坐标
- `cy`: 矩形中心y坐标
- `ex`: 与图像中心的x偏差
- `ey`: 与图像中心的y偏差

**返回**：`true`（成功）或`false`（失败）

**输出**：
```
========== 矩形检测成功 ==========
检测次数: N
中心坐标: (cx, cy)
偏差: (ex, ey)
==================================
```

### on_rect_lost()

**功能**：处理矩形丢失

**参数**：无

**返回**：`true`（成功）或`false`（失败）

**输出**：
```
⚠️  未检测到矩形 - 丢失次数: N
```

## 依赖库

| 库名称 | 版本 | 说明 |
|--------|------|------|
| Arduino_RouterBridge | 0.4.1 | Bridge通信 + Monitor输出 |
| Arduino_RPClite | 0.2.1 | RPC基础 |
| MsgPack | 0.4.2 | 消息序列化 |
| ArxContainer | 0.7.0 | 容器支持 |
| ArxTypeTraits | 0.3.2 | 类型特性 |
| DebugLog | 0.8.4 | 调试日志 |

**注意**：不再需要`Arduino_LED_Matrix`和`ArduinoGraphics`库

## 调试方法

### 查看App状态

```bash
arduino-app-cli app list
```

### 查看运行日志（Python端）

```bash
arduino-app-cli app logs user:rectangle-detection
```

**日志示例**：
```
✅ 检测到矩形: 中心=(320, 240), 偏差=(+10, -5)
⚠️  未检测到矩形
```

### 查看Serial Wire输出（MCU端）

在App Lab界面中：
1. 打开`rectangle-detection`应用
2. 点击"Console"标签
3. 查看"Sketch"输出

**输出示例**：
```
==================================
  矩形检测MCU控制应用已启动
  等待MPU侧检测结果...
==================================

========== 矩形检测成功 ==========
检测次数: 1
中心坐标: (320, 240)
偏差: (10, -5)
==================================
```

### 查看HTTP接口

```bash
curl http://localhost:8080/result.json
```

**输出示例**：
```json
{
    "timestamp": 1234567890.123,
    "rect_detected": true,
    "center": [320, 240],
    "error": [10, -5]
}
```

## 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 检查间隔 | 10ms | Python端轮询 |
| Bridge调用延迟 | 2-5ms | RPC通信 |
| Monitor输出延迟 | < 1ms | Serial Wire |
| LED控制延迟 | < 1ms | GPIO操作 |
| **总延迟** | **< 15ms** | 端到端 |

## 配合MPU使用

本系统需要配合MPU侧OpenCV程序使用：

### 启动顺序

```bash
# 1. 启动MPU侧（OpenCV视觉检测）
cd "D:\IEEE Project\评测\arduino-UNO-Q-4GB\Debian开发\混合架构\方案一\mpu"
python3 main.py

# 2. 启动MCU侧（本App）
arduino-app-cli app start user:rectangle-detection
```

### 验证运行

1. **MPU侧**：浏览器访问 `http://localhost:8080/stream.mjpg`
2. **MCU侧**：
   - 观察板载LED状态
   - 在App Lab查看Console输出
3. **HTTP接口**：`curl http://localhost:8080/result.json`

## 故障排除

### 没有Serial Wire输出

**检查项**：
1. App是否正常启动：`arduino-app-cli app list`
2. Monitor是否初始化：检查`Monitor.begin()`是否调用
3. MPU侧是否运行：浏览器访问 `http://localhost:8080/health`

### LED不亮

**检查项**：
1. LED引脚是否正确：`LED_BUILTIN`
2. LED是否被其他代码占用
3. 检测是否成功：查看Console输出

### 输出不更新

**可能原因**：
1. MPU侧未运行
2. HTTP请求失败
3. 时间戳未变化

**解决方法**：
```bash
# 检查MPU侧
curl http://localhost:8080/health

# 检查HTTP接口
curl http://localhost:8080/result.json

# 重启App
arduino-app-cli app stop user:rectangle-detection
arduino-app-cli app start user:rectangle-detection
```

## Monitor vs Serial

### Monitor.println()

- ✅ 通过Bridge输出到App Lab Console
- ✅ 可以在App Lab界面直接查看
- ✅ 适合调试和监控

### Serial.println()

- ⚠️ 通过UART硬件输出
- ⚠️ 需要外部串口工具查看
- ⚠️ 不会显示在App Lab Console

**本项目使用Monitor.println()**

## 扩展建议

### 1. 添加更多输出信息

可以在`sketch.ino`中添加：
- 时间戳
- 检测频率统计
- 性能指标

### 2. 添加数据记录

可以在MCU侧记录历史数据：
- 最近N次检测结果
- 平均偏差
- 检测成功率

### 3. 添加控制逻辑

可以在MCU侧添加：
- 电机控制（根据偏差）
- 舵机控制（跟踪目标）
- 蜂鸣器提示

## 应用场景

- 工业视觉定位
- 机器人导航
- 自动对焦系统
- 目标跟踪
- 电赛视觉任务
- MPU-MCU协同控制
- 实时调试监控

## 技术特点

- **混合架构**：MPU视觉检测 + MCU实时控制
- **低延迟**：总延迟 < 15ms
- **线程安全**：使用`provide_safe`注册RPC函数
- **高效输出**：Serial Wire输出，无需LED矩阵渲染
- **调试友好**：Console直接查看MCU数据
- **状态指示**：LED + 文本双重指示

## 开发参考

本项目参考了`Blink LED`项目：
- Monitor.println()使用方式
- Bridge通信方式
- LED控制方式

## 相关项目

- **MPU侧**：`D:\IEEE Project\评测\arduino-UNO-Q-4GB\Debian开发\混合架构\方案一\mpu`
- **参考项目**：`D:\IEEE Project\评测\arduino-UNO-Q-4GB\Apps\Blink LED`
