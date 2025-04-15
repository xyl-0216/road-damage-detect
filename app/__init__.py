import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'

def create_app(config_class=None):
    """创建并配置Flask应用"""
    try:
        logger.debug("开始创建应用实例")
        
        # 获取项目根目录
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(base_dir, 'templates')
        static_dir = os.path.join(base_dir, 'static')
        
        logger.debug(f"模板目录: {template_dir}")
        logger.debug(f"静态文件目录: {static_dir}")
        
        # 创建Flask应用
        app = Flask(__name__,
                   template_folder=template_dir,
                   static_folder=static_dir)
        
        # 配置应用
        logger.debug("加载配置")
        if config_class is None:
            from app.config.config import Config
            config_class = Config
        app.config.from_object(config_class)
        
        # 确保上传目录存在
        logger.debug("检查并创建上传目录")
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['PROCESSED_VIDEOS_FOLDER'], exist_ok=True)
        
        # 初始化扩展
        logger.debug("初始化数据库")
        db.init_app(app)
        
        logger.debug("初始化登录管理器")
        login_manager.init_app(app)
        
        # 创建数据库表
        with app.app_context():
            logger.debug("创建数据库表")
            db.create_all()
        
        # 注册蓝图
        logger.debug("注册蓝图")
        from app.routes.main import main
        from app.routes.auth import auth
        app.register_blueprint(main)
        app.register_blueprint(auth)
        
        # 初始化视频处理器（如果模型文件存在）
        model_path = app.config['MODEL_PATH']
        if os.path.exists(model_path):
            logger.debug("初始化视频处理器")
            from app.routes.main import init_video_processor
            init_video_processor(model_path)
        else:
            logger.warning(f"模型文件不存在: {model_path}，视频处理功能将不可用")
        
        logger.info("应用创建成功")
        return app
        
    except Exception as e:
        logger.error(f"应用创建失败: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id)) 