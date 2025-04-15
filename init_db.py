import pymysql
from app import create_app, db
from app.models.user import User
from app.config.config import Config

def create_database():
    """创建MySQL数据库"""
    try:
        # 连接MySQL服务器
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            charset='utf8'  # 使用基本的utf8字符集
        )
        
        # 创建游标
        cursor = conn.cursor()
        
        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DB} CHARACTER SET utf8 COLLATE utf8_general_ci")
        
        # 提交更改
        conn.commit()
        print(f"数据库 {Config.MYSQL_DB} 创建成功")
        
    except Exception as e:
        print(f"创建数据库时出错: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def init_db():
    """初始化数据库"""
    # 创建数据库
    create_database()
    
    # 创建应用实例
    app = create_app()
    
    with app.app_context():
        # 创建所有表
        db.create_all()
        
        # 检查是否已存在管理员用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # 创建管理员用户
            admin = User(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('管理员用户已创建')
        else:
            print('管理员用户已存在')

if __name__ == '__main__':
    init_db() 