"""
MCU控制应用 - HTTP通信版本
通过HTTP获取检测结果并调用MCU
"""

import time
import requests

from arduino.app_utils import App, Bridge

# MPU侧HTTP服务地址
# 注意：App Lab容器内localhost指向容器自己，需要使用宿主系统IP
# 可以使用以下方式获取宿主IP：
# 1. 直接指定IP（推荐）
# 2. 使用环境变量
# 3. 自动检测（需要额外逻辑）
import os
MPU_HOST = os.environ.get('MPU_HOST', '10.83.100.145')  # 默认使用设备IP
MPU_URL = f"http://{MPU_HOST}:8080/result.json"

# 检查间隔（秒）
CHECK_INTERVAL = 0.01  # 10ms

# 缓存上次的时间戳，避免重复处理
last_timestamp = 0

# 统计信息
request_count = 0
success_count = 0
error_count = 0
last_status_report = 0

print("=" * 60)
print("矩形检测MCU控制应用启动（HTTP模式）")
print("=" * 60)
print(f"MPU服务地址: {MPU_URL}")
print(f"检查间隔: {CHECK_INTERVAL * 1000:.0f}ms")
print("=" * 60)

# 测试HTTP连接
print("\n📡 测试HTTP连接...")
try:
    test_response = requests.get(MPU_URL, timeout=2.0)
    if test_response.status_code == 200:
        print(f"✅ HTTP连接成功！状态码: {test_response.status_code}")
        print(f"✅ MPU服务正常运行")
        test_data = test_response.json()
        print(f"✅ 数据格式正确，包含字段: {list(test_data.keys())}")
    else:
        print(f"⚠️  HTTP响应异常，状态码: {test_response.status_code}")
except requests.exceptions.ConnectionError:
    print("❌ 连接失败！MPU服务可能未启动")
    print("❌ 请先启动MPU侧: python3 main.py")
except requests.exceptions.Timeout:
    print("⚠️  连接超时！MPU服务响应缓慢")
except Exception as e:
    print(f"❌ 测试失败: {e}")

print("\n" + "=" * 60)
print("开始运行...")
print("=" * 60 + "\n")


def get_detection_result():
    """通过HTTP获取检测结果
    
    Returns:
        dict: 检测结果字典，如果请求失败则返回None
    """
    global request_count, success_count, error_count
    
    request_count += 1
    
    try:
        response = requests.get(MPU_URL, timeout=0.1)
        
        if response.status_code == 200:
            success_count += 1
            return response.json()
        else:
            error_count += 1
            if error_count <= 3:  # 只打印前3次错误
                print(f"❌ HTTP错误: 状态码 {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        error_count += 1
        if error_count <= 3:
            print("⚠️  HTTP请求超时")
        return None
    except requests.exceptions.ConnectionError:
        error_count += 1
        if error_count <= 3:
            print("❌ 连接失败: MPU服务可能未启动")
        return None
    except Exception as e:
        error_count += 1
        if error_count <= 3:
            print(f"❌ HTTP请求失败: {e}")
        return None


def send_to_mcu_if_changed():
    """检查检测结果并通知MCU（仅当数据更新时）"""
    global last_timestamp
    
    # 通过HTTP获取检测结果
    result = get_detection_result()
    
    if result is None:
        return
    
    # 检查时间戳，避免重复处理
    timestamp = result.get('timestamp', 0)
    if timestamp <= last_timestamp:
        return
    
    last_timestamp = timestamp
    
    # 提取检测信息
    rect_detected = result.get('rect_detected', False)
    center = result.get('center', None)
    error = result.get('error', None)
    
    # 根据检测结果调用不同的MCU函数
    if rect_detected and center is not None:
        # 检测到矩形，发送中心坐标和偏差
        cx, cy = center[0], center[1]
        ex, ey = error[0], error[1] if error else (0, 0)
        
        # 调用MCU的on_rect_detected函数
        ok = Bridge.call("on_rect_detected", cx, cy, ex, ey)
        
        if ok:
            print(f"✅ 检测到矩形: 中心=({cx}, {cy}), 偏差=({ex:+d}, {ey:+d})")
        else:
            print(f"❌ 调用MCU失败")
    else:
        # 未检测到矩形
        ok = Bridge.call("on_rect_lost")
        
        if ok:
            print("⚠️  未检测到矩形")


def report_status():
    """周期性报告状态"""
    global request_count, success_count, error_count, last_status_report
    
    current_time = time.time()
    if current_time - last_status_report >= 5.0:  # 每5秒报告一次
        last_status_report = current_time
        
        if request_count > 0:
            success_rate = (success_count / request_count) * 100
            print(f"\n📊 状态报告:")
            print(f"   总请求: {request_count}")
            print(f"   成功: {success_count} ({success_rate:.1f}%)")
            print(f"   失败: {error_count}")
            print(f"   上次时间戳: {last_timestamp:.2f}\n")


def loop():
    """主循环：持续通过HTTP获取检测结果并通知MCU"""
    send_to_mcu_if_changed()
    report_status()
    time.sleep(CHECK_INTERVAL)


# 启动App
App.run(user_loop=loop)
