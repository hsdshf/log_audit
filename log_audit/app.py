# app.py
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from routes.index import index_bp
from routes.services import bp as services_bp
from routes.alerts import alerts_bp
from routes.stats import stats_bp
from models.db_utils import init_db, add_test_data, clear_database
from models.rule import import_rules_from_json

def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    # 初始化数据库

    init_db()
    # # 清空数据库
    clear_database()
    # 导入规则
    rules_count = import_rules_from_json('config/rules.json')
    print(f"已导入 {rules_count} 条规则")
    # 添加测试数据
    #add_test_data()
    
    # 注册路由
    app.register_blueprint(index_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(stats_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)  # 添加 debug=True 以便查看错误信息