import cv2
import numpy as np
import os
import base64
import logging
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO
from collections import deque

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, model_path):
        try:
            logger.debug(f"初始化视频处理器，模型路径: {model_path}")
            if not os.path.exists(model_path):
                logger.error(f"模型文件不存在: {model_path}")
                raise FileNotFoundError(f"模型文件不存在: {model_path}")
            
            self.model = YOLO(model_path)
            logger.info("YOLO模型加载成功")
            
            # 设置字体路径
            try:
                # Windows系统
                self.font_path = "C:/Windows/Fonts/simhei.ttf"  # 黑体
                logger.debug(f"使用Windows字体: {self.font_path}")
            except:
                try:
                    # Linux系统
                    self.font_path = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
                    logger.debug(f"使用Linux字体: {self.font_path}")
                except:
                    # 如果都找不到，使用默认字体
                    self.font_path = None
                    logger.warning("未找到中文字体，将使用默认字体")
        except Exception as e:
            logger.error(f"视频处理器初始化失败: {str(e)}")
            raise
    
    def get_video_preview(self, video_path):
        """获取视频的第一帧作为预览图"""
        try:
            logger.debug(f"获取视频预览: {video_path}")
            if not os.path.exists(video_path):
                logger.error(f"视频文件不存在: {video_path}")
                return None
            
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"无法打开视频文件: {video_path}")
                return None
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error("无法读取视频帧")
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
        except Exception as e:
            logger.error(f"获取视频预览失败: {str(e)}")
            return None

    def process_video(self, video_path, output_folder):
        """处理视频文件"""
        try:
            logger.debug(f"开始处理视频: {video_path}")
            logger.debug(f"输出目录: {output_folder}")
            
            if not os.path.exists(video_path):
                logger.error(f"视频文件不存在: {video_path}")
                return None, 0
            
            # 确保输出目录存在
            os.makedirs(output_folder, exist_ok=True)
            
            # 获取视频信息
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"无法打开视频文件: {video_path}")
                return None, 0
            
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.debug(f"视频信息: {width}x{height}, {fps}fps, {total_frames}帧")
            
            # 创建输出视频
            output_filename = os.path.join(output_folder, f"processed_{os.path.basename(video_path)}")
            # 确保输出为.mp4文件
            if not output_filename.lower().endswith('.mp4'):
                output_filename = os.path.splitext(output_filename)[0] + '.mp4'
            
            # 使用H264编码器
            fourcc = cv2.VideoWriter_fourcc(*'H264')
            out = cv2.VideoWriter(output_filename, fourcc, fps, (width, height))
            
            # 初始化用于平滑的队列
            damage_deque = deque(maxlen=20)
            frame_count = 0
            
            # 定义字体和颜色
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1
            text_position = (40, 80)
            font_color = (255, 255, 255)    # 白色文字
            background_color = (0, 0, 255)  # 红色背景
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 使用YOLO模型检测
                results = self.model.predict(source=frame, imgsz=640, conf=0.25)
                processed_frame = results[0].plot(boxes=False)
                
                # 初始化损坏百分比
                percentage_damage = 0
                
                # 如果有掩码，计算损坏区域
                if results[0].masks is not None:
                    total_area = 0
                    masks = results[0].masks.data.cpu().numpy()
                    image_area = frame.shape[0] * frame.shape[1]  # 图像总像素数
                    
                    for mask in masks:
                        binary_mask = (mask > 0).astype(np.uint8) * 255
                        contours, _ = cv2.findContours(binary_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            total_area += cv2.contourArea(contours[0])
                    
                    percentage_damage = (total_area / image_area) * 100
                
                # 更新平滑队列
                damage_deque.append(percentage_damage)
                smoothed_percentage_damage = sum(damage_deque) / len(damage_deque)
                
                # 绘制文本背景
                cv2.line(processed_frame, (text_position[0], text_position[1] - 10),
                        (text_position[0] + 350, text_position[1] - 10), background_color, 40)
                
                # 添加损坏百分比文本
                cv2.putText(processed_frame, f'Road Damage: {smoothed_percentage_damage:.2f}%',
                           text_position, font, font_scale, font_color, 2, cv2.LINE_AA)
                
                # 写入输出视频
                out.write(processed_frame)
                frame_count += 1
                
                if frame_count % 100 == 0:
                    logger.debug(f"已处理 {frame_count}/{total_frames} 帧")
            
            # 释放资源
            cap.release()
            out.release()
            
            # 计算最终的平均损坏率
            final_average_damage = sum(damage_deque) / len(damage_deque) if damage_deque else 0
            logger.info(f"视频处理完成: {output_filename}, 平均损坏率: {final_average_damage:.2f}%")
            
            return os.path.basename(output_filename), final_average_damage
            
        except Exception as e:
            logger.error(f"视频处理失败: {str(e)}")
            return None, 0 