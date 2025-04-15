from flask import Blueprint, render_template, request, jsonify, send_from_directory, url_for, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import logging
from app.utils.video_processor import VideoProcessor

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

def init_video_processor(model_path):
    """初始化视频处理器"""
    global video_processor
    try:
        video_processor = VideoProcessor(model_path)
        logger.info("视频处理器初始化成功")
    except Exception as e:
        logger.error(f"视频处理器初始化失败: {str(e)}")
        raise

@main.route('/')
@login_required
def index():
    """主页路由"""
    return render_template('index.html')

@main.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        logger.debug(f"Serving uploaded file: {filename}")
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'], 
            filename, 
            mimetype='video/mp4',
            as_attachment=False
        )
    except Exception as e:
        logger.error(f"Error serving uploaded file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@main.route('/processed_videos/<filename>')
def processed_file(filename):
    """Serve processed files"""
    try:
        logger.debug(f"Serving processed file: {filename}")
        return send_from_directory(
            current_app.config['PROCESSED_VIDEOS_FOLDER'], 
            filename, 
            mimetype='video/mp4',
            as_attachment=False
        )
    except Exception as e:
        logger.error(f"Error serving processed file {filename}: {str(e)}")
        return jsonify({'error': 'File not found'}), 404

@main.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """处理文件上传"""
    try:
        logger.debug('收到上传请求')
        if 'file' not in request.files:
            logger.error('没有文件被上传')
            return jsonify({'success': False, 'message': '没有文件被上传'})
        
        file = request.files['file']
        if file.filename == '':
            logger.error('没有选择文件')
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        if not file or not allowed_file(file.filename):
            logger.error(f'不支持的文件类型: {file.filename}')
            return jsonify({'success': False, 'message': '不支持的文件类型，请上传MP4、AVI、MOV或WMV格式的视频'})
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # 确保上传目录存在
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(current_app.config['PROCESSED_VIDEOS_FOLDER'], exist_ok=True)
        
        file.save(filepath)
        logger.info(f'文件已保存: {filepath}')
        
        # 获取视频预览
        preview = video_processor.get_video_preview(filepath)
        
        # 处理视频
        processed_filename, average_damage = video_processor.process_video(filepath, current_app.config['PROCESSED_VIDEOS_FOLDER'])
        
        if processed_filename:
            # 使用正确的路由生成URL
            processed_url = url_for('main.processed_file', filename=processed_filename)
            original_url = url_for('main.uploaded_file', filename=filename)
            
            logger.info(f'视频处理完成: {processed_filename}')
            logger.info(f'平均损坏率: {average_damage:.2f}%')
            logger.debug(f'处理后的视频URL: {processed_url}')
            logger.debug(f'原始视频URL: {original_url}')
            
            return jsonify({
                'success': True,
                'video_url': processed_url,
                'original_video_url': original_url,
                'average_damage': average_damage,
                'preview': preview
            })
        else:
            logger.error('视频处理失败')
            return jsonify({'success': False, 'message': '视频处理失败'})
        
    except Exception as e:
        logger.error(f'上传处理失败: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': str(e)}) 