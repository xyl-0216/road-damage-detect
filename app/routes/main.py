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

@main.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """提供上传的文件"""
    try:
        logger.debug(f"尝试提供文件: {filename}")
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        logger.error(f"提供文件失败: {str(e)}")
        abort(404)

@main.route('/processed_videos/<path:filename>')
@login_required
def processed_file(filename):
    """提供处理后的视频文件"""
    try:
        logger.debug(f"尝试提供处理后的文件: {filename}")
        file_path = os.path.join(current_app.config['PROCESSED_VIDEOS_FOLDER'], filename)
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            abort(404)
        return send_from_directory(current_app.config['PROCESSED_VIDEOS_FOLDER'], filename)
    except Exception as e:
        logger.error(f"提供处理后的文件失败: {str(e)}")
        abort(500)

@main.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """处理文件上传"""
    try:
        if 'file' not in request.files:
            logger.error("没有文件被上传")
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.error("没有选择文件")
            return jsonify({'error': '没有选择文件'}), 400
        
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            logger.debug(f"保存文件到: {file_path}")
            file.save(file_path)
            
            # 检查视频处理器是否可用
            if video_processor is None:
                logger.warning("视频处理器未初始化，跳过处理步骤")
                return jsonify({
                    'message': '文件上传成功，但视频处理功能不可用',
                    'original_video_url': url_for('main.uploaded_file', filename=filename)
                })
            
            # 处理视频
            logger.debug("开始处理视频")
            processed_filename = video_processor.process_video(file_path, current_app.config['PROCESSED_VIDEOS_FOLDER'])
            logger.debug(f"视频处理完成: {processed_filename}")
            
            if not processed_filename:
                logger.error("视频处理失败")
                return jsonify({'error': '视频处理失败'}), 500
            
            # 生成URL
            original_video_url = url_for('main.uploaded_file', filename=filename)
            video_url = url_for('main.processed_file', filename=processed_filename)
            
            logger.info(f"文件上传成功: {filename}")
            return jsonify({
                'message': '文件上传成功',
                'original_video_url': original_video_url,
                'video_url': video_url
            })
            
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({'error': str(e)}), 500 