from flask import Blueprint, render_template, request, jsonify, send_from_directory, url_for, current_app, abort, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging
from app.utils.video_processor import VideoProcessor
import cv2
import base64
import re

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建蓝图
main = Blueprint('main', __name__)

# 创建全局视频处理器实例
video_processor = None

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_directories_exist():
    """确保必要的目录存在"""
    try:
        # 获取基础目录
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        # 创建上传目录
        upload_dir = os.path.join(base_dir, 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            logger.info(f"Created upload directory: {upload_dir}")
            
        # 创建处理后的文件目录
        processed_dir = os.path.join(base_dir, 'processed')
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)
            logger.info(f"Created processed directory: {processed_dir}")
            
        return upload_dir, processed_dir
    except Exception as e:
        logger.error(f"Error creating directories: {str(e)}")
        raise

def init_video_processor(model_path):
    """初始化视频处理器"""
    global video_processor
    try:
        # 获取去雾模型路径
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        dehaze_model_path = os.path.join(base_dir, 'models', 'dehaze_model.pth')
        
        # 检查去雾模型是否存在
        if os.path.exists(dehaze_model_path):
            logger.info(f"找到去雾模型: {dehaze_model_path}")
            video_processor = VideoProcessor(model_path, dehaze_model_path)
        else:
            logger.warning(f"未找到去雾模型: {dehaze_model_path}，将禁用去雾功能")
            video_processor = VideoProcessor(model_path)
            
        logger.info("视频处理器初始化成功")
    except Exception as e:
        logger.error(f"视频处理器初始化失败: {str(e)}")
        raise

@main.route('/')
@login_required
def index():
    """主页路由"""
    response = make_response(render_template('index.html'))
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@main.route('/uploads/<filename>')
def upload_file(filename):
    """Serve uploaded files"""
    try:
        logger.debug(f"Serving uploaded file: {filename}")
        upload_dir, _ = ensure_directories_exist()
        
        # 检查文件是否存在
        file_path = os.path.join(upload_dir, filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        response = send_from_directory(
            upload_dir, 
            filename,
            as_attachment=False
        )
        
        # 设置正确的MIME类型
        if filename.lower().endswith('.mp4'):
            response.headers['Content-Type'] = 'video/mp4'
        elif filename.lower().endswith('.avi'):
            response.headers['Content-Type'] = 'video/x-msvideo'
        elif filename.lower().endswith('.mov'):
            response.headers['Content-Type'] = 'video/quicktime'
        elif filename.lower().endswith('.wmv'):
            response.headers['Content-Type'] = 'video/x-ms-wmv'
            
        # 添加跨域支持
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        logger.error(f"Error serving uploaded file {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/processed/<filename>')
def processed_file(filename):
    """处理后的视频文件"""
    try:
        logger.debug(f"Serving processed file: {filename}")
        _, processed_dir = ensure_directories_exist()
        
        # 检查文件是否存在
        file_path = os.path.join(processed_dir, filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
            
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 设置分块传输的范围
        range_header = request.headers.get('Range', None)
        if range_header:
            byte1, byte2 = 0, None
            match = re.search('bytes=(\d+)-(\d*)', range_header)
            groups = match.groups()

            if groups[0]:
                byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])

            if byte2 is None:
                byte2 = file_size - 1
            length = byte2 - byte1 + 1

            resp = send_from_directory(
                processed_dir,
                filename,
                as_attachment=False
            )
            resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
            resp.headers.add('Accept-Ranges', 'bytes')
            resp.headers.add('Content-Length', str(length))
            resp.headers.add('Content-Type', 'video/mp4')
            resp.headers.add('Access-Control-Allow-Origin', '*')
            resp.status_code = 206
            return resp

        response = send_from_directory(
            processed_dir,
            filename,
            as_attachment=False
        )
        
        # 设置正确的MIME类型和headers
        response.headers.add('Content-Type', 'video/mp4')
        response.headers.add('Content-Length', str(file_size))
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Cache-Control', 'public, max-age=31536000')
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Range')
        
        return response
    except Exception as e:
        logger.error(f"Error serving processed file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/process_video', methods=['POST'])
def process_video():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
            
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        if not allowed_file(video_file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
            
        # 获取去雾选项
        enable_dehaze = request.form.get('enable_dehaze', 'false').lower() == 'true'
        
        # 确保目录存在
        upload_dir, processed_dir = ensure_directories_exist()
        
        # 生成安全的文件名
        original_filename = secure_filename(video_file.filename)
        processed_filename = f'processed_{original_filename}'
        
        # 保存原始视频
        original_path = os.path.join(upload_dir, original_filename)
        video_file.save(original_path)
        logger.info(f"Saved original video to: {original_path}")
        
        # 处理视频
        processed_filename, average_damage = video_processor.process_video(
            original_path, 
            processed_dir,
            enable_dehaze=enable_dehaze
        )
        
        if not processed_filename:
            return jsonify({'error': 'Video processing failed'}), 500
            
        logger.info(f"Processed video saved as: {processed_filename}")
        
        # 创建响应
        response = jsonify({
            'original_url': url_for('main.upload_file', filename=original_filename, _external=True),
            'processed_url': url_for('main.processed_file', filename=processed_filename, _external=True),
            'average_damage': average_damage
        })
        
        # 设置响应头
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Access-Control-Allow-Origin'] = '*'
        
        return response
        
    except Exception as e:
        logger.error(f"Video processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/jilu')
@login_required
def jilu():
    """历史记录页面"""
    return render_template('jilu.html')

@main.route('/brokeSign')
@login_required
def brokeSign():
    """损坏标志页面"""
    return render_template('brokeSign.html')

@main.route('/brokeRode')
@login_required
def brokeRode():
    """损坏道路页面"""
    return render_template('brokeRode.html')

@main.route('/dehaze')
@login_required
def dehaze():
    """去雾处理页面"""
    return render_template('dehaze.html')

@main.route('/upload_dehaze', methods=['POST'])
@login_required
def upload_dehaze():
    """处理图像去雾"""
    try:
        logger.debug('收到去雾处理请求')
        if 'file' not in request.files:
            logger.error('没有文件被上传')
            return jsonify({'success': False, 'message': '没有文件被上传'})
        
        file = request.files['file']
        if file.filename == '':
            logger.error('没有选择文件')
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        if not file or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            logger.error(f'不支持的文件类型: {file.filename}')
            return jsonify({'success': False, 'message': '不支持的文件类型，请上传PNG或JPG格式的图像'})
        
        # 保存上传的图像
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f'图像已保存: {filepath}')
        
        # 使用去雾处理器处理图像
        if video_processor and video_processor.dehaze_processor:
            # 读取图像
            image = cv2.imread(filepath)
            if image is None:
                raise ValueError('无法读取图像文件')
            
            # 进行去雾处理
            dehazed_image = video_processor.dehaze_processor.process_frame(image)
            
            # 保存处理后的图像
            dehazed_filename = f'dehazed_{filename}'
            dehazed_filepath = os.path.join(current_app.config['PROCESSED_VIDEOS_FOLDER'], dehazed_filename)
            cv2.imwrite(dehazed_filepath, dehazed_image)
            
            # 将处理后的图像转换为base64
            _, buffer = cv2.imencode('.jpg', dehazed_image)
            dehazed_image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'success': True,
                'dehazed_image': f'data:image/jpeg;base64,{dehazed_image_base64}'
            })
        else:
            return jsonify({'success': False, 'message': '去雾功能未启用'})
        
    except Exception as e:
        logger.error(f'去雾处理失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}) 