# 室內手機相機姿態
本專案是將拍攝到的照片做相機姿態偵測，利用照片中的直線結構，例如牆角、地板線、門框等，先用 Canny 和 Hough Transform 偵測線段，再根據線段交會得到消失點。
由於室內環境多半符合 Manhattan World，也就是三個主要方向互相垂直，因此可以利用消失點與相機內參反推相機旋轉矩陣，最後將旋轉矩陣轉換成 yaw、pitch、roll。
## 專案流程
```mermaid
graph LR
    A[輸入照片] --> B[灰階化]
    B --> C[Canny]
    C --> D[Hough Line]
    D --> E[消失點偵測]

    E --> G[旋轉矩陣 R]
    F[相機內參 fx fy cx cy] --> G

    G --> H[yaw / roll / pitch]
```
## breakdown
```mermaid
graph TD
  A[相機姿態] -->B[灰階化]
  A --> C[canny]
  A --> D[Hough Line]
```
