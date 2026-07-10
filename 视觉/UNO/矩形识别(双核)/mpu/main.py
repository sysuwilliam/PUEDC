"""
================================================================================
动态矩形中心检测系统 - Debian OpenCV 版本
================================================================================

基于 OpenCV 的动态矩形中心检测系统，在 Arduino UNO Q Debian 主机上运行。

【整体架构】
1. 图像采集模块：通过摄像头实时捕获视频帧
2. 矩形检测模块：检测图像中的矩形区域并提取顶点坐标
3. 矩形验证模块：验证检测到的四边形是否为标准矩形
4. 中心计算模块：计算矩形的几何中心（对角线交点）
5. HTTP服务模块：提供Web界面和API接口

【图像处理流程】
输入图像 → 高斯模糊 → Canny边缘检测 → 轮廓查找 → 多边形拟合 
→ 四边形筛选 → 矩形验证 → 中心计算 → 结果可视化

================================================================================
"""

import json
import threading
import time
import math
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

# HTTP服务配置
HOST = "0.0.0.0"
PORT = 8080

# 摄像头配置
CAMERA_INDEX = 0
WIDTH = 640
HEIGHT = 480
FPS = 30
JPEG_QUALITY = 80


# 矩形检测参数
canny_thresh1 = 50
canny_thresh2 = 150
approx_epsilon = 0.04
area_min_ratio = 0.001
gaussian_blur_size = 5
length_threshold = 120

# 面积阈值参数
S_THRESHOLD = 2000
THRESHOLD_MIN = 500
THRESHOLD_MAX = 10000
THRESHOLD_STEP = 500

# 全局状态
latest_frame = None
latest_status = "starting"
latest_result = {
    "status": latest_status,
    "rect_detected": False,
    "center": None,
    "error": None,
    "vertices": None,
    "area": 0,
}
lock = threading.Lock()


def are_segments_parallel(theta1, theta2, tolerance=30):
    """判断两条线段是否平行"""
    angle_difference = abs(theta1 - theta2)
    if angle_difference > 180:
        angle_difference = angle_difference - 180
    return math.isclose(angle_difference, 0, abs_tol=tolerance) or math.isclose(angle_difference, 180, abs_tol=tolerance)


def are_segments_vertical(theta1, theta2, tolerance=30):
    """判断两条线段是否垂直"""
    angle_difference = abs(theta1 - theta2)
    if angle_difference > 180:
        angle_difference = angle_difference - 180
    return math.isclose(angle_difference, 90, abs_tol=tolerance)


def find_intersection(x1, y1, x2, y2, x3, y3, x4, y4):
    """计算两条直线的交点（对角线交点）"""
    def calculate_determinant(A, B):
        return A[0] * B[1] - A[1] * B[0]

    AB = (x2 - x1, y2 - y1)
    AC = (x3 - x1, y3 - y1)
    CD = (x4 - x3, y4 - y3)

    det = calculate_determinant(AB, CD)

    if det == 0:
        return None

    t = calculate_determinant(AC, CD) / det

    intersection_x = x1 + t * AB[0]
    intersection_y = y1 + t * AB[1]

    return int(intersection_x), int(intersection_y)


def find_max_rect(rects):
    """从矩形列表中找到面积最大的矩形"""
    max_size = 0
    max_rect = None
    for rect in rects:
        area = rect[2] * rect[3]
        if area > max_size:
            max_rect = rect
            max_size = area
    return max_rect


def find_rectangles_opencv(image, canny_t1, canny_t2, epsilon, min_area_ratio, blur_size):
    """
    使用 OpenCV 检测图像中的矩形
    
    参数：
        image: 输入图像（BGR格式）
        canny_t1: Canny边缘检测低阈值
        canny_t2: Canny边缘检测高阈值
        epsilon: 多边形拟合精度
        min_area_ratio: 最小面积比例
        blur_size: 高斯模糊核大小
    
    返回：
        rects: 矩形列表，每个矩形格式为 [x, y, w, h, x1, y1, x2, y2, x3, y3, x4, y4]
               其中 (x,y,w,h) 为外接矩形，(x1,y1)...(x4,y4) 为四个顶点坐标
    """
    rects = []
    
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊降噪
    if blur_size > 0:
        blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
    else:
        blurred = gray
    
    # Canny边缘检测
    edges = cv2.Canny(blurred, canny_t1, canny_t2)
    
    # 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # 图像面积
    image_area = image.shape[0] * image.shape[1]
    min_area = image_area * min_area_ratio
    
    for contour in contours:
        # 计算轮廓面积
        area = cv2.contourArea(contour)
        
        if area < min_area:
            continue
        
        # 多边形拟合
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon * peri, True)
        
        # 筛选四边形
        if len(approx) == 4:
            # 检查是否为凸多边形
            if cv2.isContourConvex(approx):
                # 获取四个顶点
                points = approx.reshape(-1, 2)
                
                # 计算外接矩形
                x, y, w, h = cv2.boundingRect(approx)
                
                # 按照顺时针或逆时针顺序排列顶点
                center = np.mean(points, axis=0)
                angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
                sorted_indices = np.argsort(angles)
                sorted_points = points[sorted_indices]
                
                # 构造返回格式：[x, y, w, h, x1, y1, x2, y2, x3, y3, x4, y4]
                rect = [x, y, w, h]
                for point in sorted_points:
                    rect.extend([int(point[0]), int(point[1])])
                
                rects.append(rect)
    
    return rects


def process_frame(frame):
    """处理帧并返回处理后的帧和结果数据"""
    global S_THRESHOLD
    
    # 检测矩形
    rects = find_rectangles_opencv(
        frame, 
        canny_thresh1, 
        canny_thresh2,
        approx_epsilon,
        area_min_ratio,
        gaussian_blur_size
    )
    
    rect_detected = False
    center = None
    error = None
    vertices = None
    area = 0
    
    if rects:
        # 找到最大矩形
        max_rect = find_max_rect(rects)
        
        if max_rect:
            # 提取四个顶点
            c = [[0, 0], [0, 0], [0, 0], [0, 0]]
            for i in range(4):
                c[i][0] = max_rect[2*i+4]
                c[i][1] = max_rect[2*i+5]
            
            # 绘制检测到的四边形（红色）
            for s in range(4):
                next_s = (s + 1) % 4
                cv2.line(frame, (c[s][0], c[s][1]), (c[next_s][0], c[next_s][1]), (0, 0, 255), 3)
                cv2.circle(frame, (c[s][0], c[s][1]), 5, (255, 0, 0), -1)
            
            # 计算四条边的长度
            len1 = math.sqrt(pow(c[0][0]-c[1][0], 2) + pow(c[0][1]-c[1][1], 2))
            len2 = math.sqrt(pow(c[2][0]-c[3][0], 2) + pow(c[2][1]-c[3][1], 2))
            len3 = math.sqrt(pow(c[0][0]-c[3][0], 2) + pow(c[0][1]-c[3][1], 2))
            len4 = math.sqrt(pow(c[1][0]-c[2][0], 2) + pow(c[1][1]-c[2][1], 2))
            
            # 计算面积
            area = max_rect[2] * max_rect[3]
            
            # 计算对边差值
            err1 = abs(len1 - len2)
            err2 = abs(len3 - len4)
            
            # 验证矩形条件
            if (area > S_THRESHOLD and 
                err1 < length_threshold and 
                err2 < length_threshold and 
                len1 > 30 and len2 > 30 and len3 > 30 and len4 > 30):
                
                # 计算每条边的角度
                theta1 = math.atan2(c[0][1]-c[1][1], c[0][0]-c[1][0])
                theta2 = math.atan2(c[2][1]-c[3][1], c[2][0]-c[3][0])
                theta3 = math.atan2(c[0][1]-c[3][1], c[0][0]-c[3][0])
                theta4 = math.atan2(c[1][1]-c[2][1], c[1][0]-c[2][0])
                
                # 转换为角度
                theta1_degrees = math.degrees(theta1)
                theta2_degrees = math.degrees(theta2)
                theta3_degrees = math.degrees(theta3)
                theta4_degrees = math.degrees(theta4)
                
                # 验证平行和垂直关系
                is_line1_line2_parallel = are_segments_parallel(theta1_degrees, theta2_degrees)
                is_line3_line4_parallel = are_segments_parallel(theta3_degrees, theta4_degrees)
                is_line1_line3_vertical = are_segments_vertical(theta1_degrees, theta3_degrees)
                
                # 判断是否为标准矩形
                if (is_line1_line3_vertical and 
                    is_line1_line2_parallel and 
                    is_line3_line4_parallel):
                    
                    rect_detected = True
                    vertices = [[int(c[i][0]), int(c[i][1])] for i in range(4)]
                    
                    # 计算对角线交点（中心）
                    intersection = find_intersection(
                        c[0][0], c[0][1], c[2][0], c[2][1],
                        c[1][0], c[1][1], c[3][0], c[3][1]
                    )
                    
                    if intersection:
                        center = list(intersection)
                        
                        # 绘制中心点
                        cv2.circle(frame, intersection, 8, (0, 255, 0), -1)
                        
                        # 绘制标准矩形（绿色）
                        for s in range(4):
                            next_s = (s + 1) % 4
                            cv2.line(frame, (c[s][0], c[s][1]), 
                                    (c[next_s][0], c[next_s][1]), (0, 255, 0), 3)
                            cv2.circle(frame, (c[s][0], c[s][1]), 5, (255, 0, 0), -1)
                        
                        # 显示中心坐标
                        text = f"Center: ({intersection[0]}, {intersection[1]})"
                        cv2.putText(frame, text, (10, 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                        
                        # 计算与图像中心的偏差
                        center_x = WIDTH // 2
                        center_y = HEIGHT // 2
                        error_x = center_x - intersection[0]
                        error_y = center_y - intersection[1]
                        error = [error_x, error_y]
                        
                        # 显示偏差
                        error_text = f"Error: ({error_x:+04d}, {error_y:+04d})"
                        cv2.putText(frame, error_text, (10, 70),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    
    # 显示当前面积阈值
    threshold_text = f"S_THRESHOLD: {S_THRESHOLD}"
    cv2.putText(frame, threshold_text, (10, frame.shape[0] - 20),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    
    # 显示检测状态
    status_text = "RECT DETECTED" if rect_detected else "NO RECT"
    status_color = (0, 255, 0) if rect_detected else (0, 0, 255)
    cv2.putText(frame, status_text, (frame.shape[1] - 200, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
    
    result = {
        "status": "streaming",
        "rect_detected": rect_detected,
        "center": center,
        "error": error,
        "vertices": vertices,
        "area": int(area),
        "s_threshold": S_THRESHOLD,
        "timestamp": time.time(),
    }
    
    return frame, result


def camera_loop():
    global latest_frame, latest_status, latest_result
    
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    
    if not cap.isOpened():
        with lock:
            latest_status = "cannot open camera"
            latest_result = {
                "status": latest_status,
                "rect_detected": False,
                "center": None,
                "error": None,
                "vertices": None,
                "area": 0,
            }
        print("cannot open camera")
        return
    
    print("camera opened")
    
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            with lock:
                latest_status = "failed to read frame"
                latest_result = {
                    "status": latest_status,
                    "rect_detected": False,
                    "center": None,
                    "error": None,
                    "vertices": None,
                    "area": 0,
                }
            time.sleep(0.2)
            continue
        
        frame, result = process_frame(frame)
        
        with lock:
            latest_frame = frame
            latest_status = result["status"]
            latest_result = result
        
        time.sleep(1 / FPS)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_index()
        elif self.path == "/stream.mjpg":
            self.send_stream()
        elif self.path == "/snapshot.jpg":
            self.send_snapshot()
        elif self.path == "/health":
            self.send_health()
        elif self.path == "/result.json":
            self.send_result_json()
        elif self.path == "/config":
            self.send_config()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
    
    def do_POST(self):
        if self.path == "/threshold/increase":
            self.increase_threshold()
        elif self.path == "/threshold/decrease":
            self.decrease_threshold()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
    
    def get_jpeg(self):
        with lock:
            frame = None if latest_frame is None else latest_frame.copy()
        
        if frame is None:
            return None
        
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
        )
        if not ok:
            return None
        
        return encoded.tobytes()
    
    def send_index(self):
        html = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>矩形中心检测系统</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f4f7fb;
      font-family: Arial, sans-serif;
      color: #1f2933;
    }
    main {
      width: min(960px, calc(100vw - 32px));
      display: grid;
      gap: 14px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 28px;
    }
    .viewer {
      aspect-ratio: 4 / 3;
      background: #111827;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      overflow: hidden;
      display: grid;
      place-items: center;
    }
    img {
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .meta {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: #52606d;
      font-size: 14px;
    }
    .controls {
      display: flex;
      gap: 12px;
      margin-top: 8px;
    }
    button {
      padding: 8px 16px;
      border: 1px solid #d9e2ec;
      border-radius: 4px;
      background: white;
      cursor: pointer;
      font-size: 14px;
    }
    button:hover {
      background: #f4f7fb;
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>矩形中心检测系统</h1>
        <div class="meta">Arduino UNO Q - Debian OpenCV</div>
      </div>
      <a href="/snapshot.jpg" target="_blank">快照</a>
    </header>
    <section class="viewer">
      <img src="/stream.mjpg" alt="实时视频流">
    </section>
    <div class="meta">
      <a href="/health" target="_blank">健康检查</a>
      <a href="/result.json" target="_blank">检测结果</a>
      <a href="/config" target="_blank">配置信息</a>
    </div>
    <div class="controls">
      <button onclick="fetch('/threshold/increase', {method: 'POST'}).then(() => location.reload())">增加面积阈值 (+)</button>
      <button onclick="fetch('/threshold/decrease', {method: 'POST'}).then(() => location.reload())">减少面积阈值 (-)</button>
    </div>
  </main>
</body>
</html>
"""
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
    
    def send_snapshot(self):
        jpeg = self.get_jpeg()
        if jpeg is None:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "no frame")
            return
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(jpeg)
    
    def send_stream(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        
        while True:
            jpeg = self.get_jpeg()
            if jpeg is None:
                time.sleep(0.1)
                continue
            
            try:
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                break
            
            time.sleep(1 / FPS)
    
    def send_health(self):
        with lock:
            text = f"{latest_status}\n"
        
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
    
    def send_result_json(self):
        with lock:
            payload = json.dumps(latest_result).encode("utf-8")
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)
    
    def send_config(self):
        config = {
            "s_threshold": S_THRESHOLD,
            "threshold_min": THRESHOLD_MIN,
            "threshold_max": THRESHOLD_MAX,
            "threshold_step": THRESHOLD_STEP,
            "canny_thresh1": canny_thresh1,
            "canny_thresh2": canny_thresh2,
            "approx_epsilon": approx_epsilon,
            "gaussian_blur_size": gaussian_blur_size,
        }
        payload = json.dumps(config).encode("utf-8")
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)
    
    def increase_threshold(self):
        global S_THRESHOLD
        S_THRESHOLD = min(THRESHOLD_MAX, S_THRESHOLD + THRESHOLD_STEP)
        print(f"面积阈值增加到: {S_THRESHOLD}")
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Threshold increased to {S_THRESHOLD}".encode("utf-8"))
    
    def decrease_threshold(self):
        global S_THRESHOLD
        S_THRESHOLD = max(THRESHOLD_MIN, S_THRESHOLD - THRESHOLD_STEP)
        print(f"面积阈值减少到: {S_THRESHOLD}")
        
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(f"Threshold decreased to {S_THRESHOLD}".encode("utf-8"))


threading.Thread(target=camera_loop, daemon=True).start()

server = ThreadingHTTPServer((HOST, PORT), Handler)
print(f"矩形中心检测服务: http://0.0.0.0:{PORT}")
print(f"HTTP接口: http://localhost:{PORT}/result.json")
server.serve_forever()