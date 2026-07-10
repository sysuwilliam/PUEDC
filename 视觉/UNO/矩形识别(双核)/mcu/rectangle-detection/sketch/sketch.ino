// 矩形检测MCU控制代码 - Serial Wire版本
// 参考Blink LED例程

#include "Arduino_RouterBridge.h"

// 统计变量
int detect_count = 0;
int lost_count = 0;

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH);  // 初始熄灭
    
    Bridge.begin();
    Bridge.provide("on_rect_detected", on_rect_detected);
    Bridge.provide("on_rect_lost", on_rect_lost);
    
    // 启动信息
    Monitor.println("==================================");
    Monitor.println("  矩形检测MCU控制应用已启动");
    Monitor.println("  等待MPU侧检测结果...");
    Monitor.println("==================================");
}

void loop() {
}

void on_rect_detected(int cx, int cy, int ex, int ey) {
    detect_count++;
    digitalWrite(LED_BUILTIN, LOW);  // 点亮LED
    
    Monitor.println("========== 矩形检测成功 ==========");
    Monitor.print("检测次数: ");
    Monitor.println(detect_count);
    Monitor.print("中心坐标: (");
    Monitor.print(cx);
    Monitor.print(", ");
    Monitor.print(cy);
    Monitor.println(")");
    Monitor.print("偏差: (");
    Monitor.print(ex);
    Monitor.print(", ");
    Monitor.print(ey);
    Monitor.println(")");
    Monitor.println("==================================");
}

void on_rect_lost() {
    lost_count++;
    digitalWrite(LED_BUILTIN, HIGH);  // 熄灭LED
    
    Monitor.print("⚠️  未检测到矩形 - 丢失次数: ");
    Monitor.println(lost_count);
}
