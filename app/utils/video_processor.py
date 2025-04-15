import cv2
import numpy as np
import os
import base64
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

class VideoProcessor:
    def __init__(self, model_path):
        self.model = YOLO(model_path)
        
        # 设置字体路径
        try:
            # Windows系统
            self.font_path = "C:/Windows/Fonts/simhei.ttf"  # 黑体
        except:
            try:
                # Linux系统
                self.font_path = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
            except:
                # 如果都找不到，使用默认字体
                self.font_path = None
    
    def get_video_preview(self, video_path):
        """获取视频的第一帧作为预览图"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        # 读取第一帧
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None
        
        # 调整预览图片大小
        height, width = frame.shape[:2]
        max_size = 320
        if height > width:
            new_height = max_size
            new_width = int(width * (max_size / height))
        else:
            new_width = max_size
            new_height = int(height * (max_size / width))
        
        frame = cv2.resize(frame, (new_width, new_height))
        
        # 将帧转换为base64
        _, buffer = cv2.imencode('.jpg', frame)
        return base64.b64encode(buffer).decode('utf-8')
    
    def process_video(self, video_path, output_folder):
        """处理视频，检测道路损坏并生成新视频"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None, "无法打开视频文件"

        # 获取视频属性
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))

        # 创建输出文件名
        output_filename = f'processed_{os.path.basename(video_path)}'
        output_path = os.path.join(output_folder, output_filename)

        # 使用H.264编码器
        fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264编码
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            return None, "无法创建输出视频文件"

        damage_percentages = []
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # 执行推理
            results = self.model.predict(source=frame, imgsz=640, conf=0.25)
            processed_frame = results[0].plot(boxes=False)
            
            # 计算损坏百分比
            percentage_damage = 0
            if results[0].masks is not None:
                total_area = 0
                masks = results[0].masks.data.cpu().numpy()
                image_area = frame.shape[0] * frame.shape[1]
                for mask in masks:
                    binary_mask = (mask > 0).astype(np.uint8) * 255
                    contour, _ = cv2.findContours(binary_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                    if contour:
                        total_area += cv2.contourArea(contour[0])
                
                percentage_damage = (total_area / image_area) * 100
                damage_percentages.append(percentage_damage)

            # 使用PIL绘制中文文本
            text = f'道路损坏: {percentage_damage:.2f}%'
            
            # 将OpenCV图像转换为PIL图像
            pil_image = Image.fromarray(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(pil_image)
            
            # 设置字体大小
            font_size = int(min(width, height) * 0.05)  # 根据图像大小调整字体大小
            if self.font_path:
                font = ImageFont.truetype(self.font_path, font_size)
            else:
                font = ImageFont.load_default()
            
            # 绘制文本
            draw.text((40, 40), text, font=font, fill=(255, 255, 255))
            
            # 将PIL图像转换回OpenCV格式
            processed_frame = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            out.write(processed_frame)

        cap.release()
        out.release()

        # 计算平均损坏百分比
        avg_damage = sum(damage_percentages) / len(damage_percentages) if damage_percentages else 0

        # 获取处理后视频的预览
        processed_preview = self.get_video_preview(output_path)

        return output_path, avg_damage, processed_preview 