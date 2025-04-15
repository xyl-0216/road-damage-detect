import os
import logging
from app import create_app

# 配置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    # 创建应用实例
    app = create_app()
    logger.info('Flask application created successfully')
    
    if __name__ == '__main__':
        logger.info('Starting Flask application...')
        app.run(debug=True, host='0.0.0.0', port=5000)
except Exception as e:
    logger.error(f'Error starting application: {str(e)}', exc_info=True) 