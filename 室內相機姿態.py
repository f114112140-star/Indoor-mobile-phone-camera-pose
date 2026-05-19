import cv2
import numpy as np
import math
import os
from google.colab.patches import cv2_imshow # Import cv2_imshow for Colab display


# =========================
# 1. 讀取圖片，支援中文路徑
# =========================
def read_image(path):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)

    if img is None:
        raise ValueError("圖片讀取失敗，請檢查路徑")

    # 灰階圖轉 BGR，方便後面畫彩色線
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # 如果有 alpha 通道，轉成 BGR
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    return img


# =========================
# 2. 影像前處理
# =========================
def preprocess(img):
    img_resized = cv2.resize(img, (640, 480))
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # 自適應 Canny 參數
    median = np.median(blur)
    lower = int(max(0, 0.66 * median))
    upper = int(min(255, 1.33 * median))

    edges = cv2.Canny(blur, lower, upper)

    return img_resized, gray, edges


# =========================
# 3. Hough Line 偵測
# =========================
def detect_hough_lines(edges):
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=50,
        maxLineGap=15
    )

    result = []

    if lines is None:
        return result

    for line in lines:
        x1, y1, x2, y2 = line[0]

        length = math.hypot(x2 - x1, y2 - y1)

        if length < 40:
            continue

        result.append((x1, y1, x2, y2, length))

    return result


# =========================
# 4. 線段轉成 ax + by + c = 0
# =========================
def line_to_abc(x1, y1, x2, y2):
    a = y1 - y2
    b = x2 - x1
    c = x1 * y2 - x2 * y1
    return a, b, c


# =========================
# 5. 計算兩條線交點
# =========================
def intersection(line1, line2):
    x1, y1, x2, y2, _ = line1
    x3, y3, x4, y4, _ = line2

    a1, b1, c1 = line_to_abc(x1, y1, x2, y2)
    a2, b2, c2 = line_to_abc(x3, y3, x4, y4)

    det = a1 * b2 - a2 * b1

    if abs(det) < 1e-6:
        return None

    x = (b1 * c2 - b2 * c1) / det
    y = (c1 * a2 - c2 * a1) / det

    return x, y


# =========================
# 6. 找視線消失點
# =========================
def find_vanishing_point(lines, width=640, height=480):
    points = []

    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            p = intersection(lines[i], lines[j])

            if p is None:
                continue

            x, y = p

            # 避免太離譜的交點
            if -width * 2 < x < width * 3 and -height * 2 < y < height * 3:
                points.append([x, y])

    if len(points) == 0:
        return None

    points = np.array(points)

    # 用中位數，比平均值穩定
    vp_x = int(np.median(points[:, 0]))
    vp_y = int(np.median(points[:, 1]))

    return vp_x, vp_y


# =========================
# 7. 估算 Roll
# =========================
def estimate_roll(lines):
    angles = []

    for x1, y1, x2, y2, length in lines:
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))

        # 轉到 -90 ~ 90
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180

        # 偏水平的線，用來估計畫面傾斜
        if abs(angle) < 45:
            angles.append(angle)

    if len(angles) == 0:
        return 0.0

    return float(np.median(angles))


# =========================
# 8. 由消失點估算 yaw / pitch
# =========================
def estimate_yaw_pitch(vp, width=640, height=480):
    fx = 0.8 * width
    fy = 0.8 * width
    cx = width / 2
    cy = height / 2

    vp_x, vp_y = vp

    yaw = math.degrees(math.atan2(vp_x - cx, fx))
    pitch = -math.degrees(math.atan2(vp_y - cy, fy))

    return yaw, pitch


# =========================
# 9. 畫相機座標軸
# =========================
def draw_camera_axis(img, vp, roll):
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    axis_len = 80

    roll_rad = math.radians(roll)

    # X 軸：紅色
    x_end = (
        int(cx + axis_len * math.cos(roll_rad)),
        int(cy + axis_len * math.sin(roll_rad))
    )

    # Y 軸：綠色
    y_end = (
        int(cx - axis_len * math.sin(roll_rad)),
        int(cy + axis_len * math.cos(roll_rad))
    )

    # Z 軸：藍色，指向消失點方向
    if vp is not None:
        vx, vy = vp
        dx = vx - cx
        dy = vy - cy
        norm = math.hypot(dx, dy)

        if norm > 1:
            z_end = (
                int(cx + axis_len * dx / norm),
                int(cy + axis_len * dy / norm)
            )
        else:
            z_end = (cx, cy - axis_len)
    else:
        z_end = (cx, cy - axis_len)

    cv2.arrowedLine(img, (cx, cy), x_end, (0, 0, 255), 3, tipLength=0.25)
    cv2.arrowedLine(img, (cx, cy), y_end, (0, 255, 0), 3, tipLength=0.25)
    cv2.arrowedLine(img, (cx, cy), z_end, (255, 0, 0), 3, tipLength=0.25)

    cv2.putText(img, "X", x_end, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(img, "Y", y_end, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(img, "Z", z_end, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)


# =========================
# 10. 畫結果
# =========================
def draw_result(img, lines, vp, yaw, pitch, roll):
    output = img.copy()

    # 畫 Hough Line
    for x1, y1, x2, y2, length in lines:
        cv2.line(output, (x1, y1), (x2, y2), (0, 255, 255), 2)

    # 畫消失點
    if vp is not None:
        vp_x, vp_y = vp
        cv2.circle(output, (vp_x, vp_y), 8, (0, 0, 255), -1)
        cv2.putText(output, "Vanishing Point", (vp_x + 10, vp_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # 畫中心十字線
    h, w = output.shape[:2]
    cx, cy = w // 2, h // 2
    cv2.line(output, (cx, 0), (cx, h), (0, 255, 0), 1) # Vertical line
    cv2.line(output, (0, cy), (w, cy), (0, 255, 0), 1) # Horizontal line
    cv2.circle(output, (cx, cy), 5, (0, 255, 0), -1) # Center dot

    # 畫相機座標軸
    draw_camera_axis(output, vp, roll)

    # 畫 yaw pitch roll 文字
    cv2.rectangle(output, (10, 10), (260, 120), (0, 0, 0), -1)

    cv2.putText(output, f"Yaw   : {yaw:.2f} deg", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.putText(output, f"Pitch : {pitch:.2f} deg", (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.putText(output, f"Roll  : {roll:.2f} deg", (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    return output


# =========================
# 11. 主程式
# =========================
def main():
    img_path = "/content/001.jpg"

    img = read_image(img_path)

    original, gray, edges = preprocess(img)

    lines = detect_hough_lines(edges)

    vp = find_vanishing_point(lines)

    if vp is not None:
        yaw, pitch = estimate_yaw_pitch(vp)
    else:
        yaw, pitch = 0.0, 0.0

    roll = estimate_roll(lines)

    result = draw_result(original, lines, vp, yaw, pitch, roll)

    print("========== Camera Pose ==========")
    print(f"Yaw   : {yaw:.2f} degree")
    print(f"Pitch : {pitch:.2f} degree")
    print(f"Roll  : {roll:.2f} degree")

    # For displaying images in Colab, cv2.imshow does not work directly.
    # You'd typically use google.colab.patches.cv2_imshow for a quick view or save to file.
    cv2_imshow(original) # Display original image
    cv2_imshow(edges) # Edges might be too busy for direct display, keeping commented
    cv2_imshow(result)   # Display result image

    # 儲存結果
    save_path = "camera_pose_result.jpg"
    cv2.imwrite(save_path, result)
    print(f"結果已儲存：{save_path}")

    # cv2.waitKey(0)
    # cv2.destroyAllWindows()


if __name__ == "__main__":
    main()