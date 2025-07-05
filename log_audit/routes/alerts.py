# routes/alerts.py

from flask import Blueprint, jsonify, request
from models.alert import get_alerts

# 创建蓝图
alerts_bp = Blueprint('alerts', __name__)

@alerts_bp.route('/api/alerts')
def get_alerts_api():
    # 获取查询参数
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    service_id = request.args.get('service_id')
    
    # 转换 service_id 为整数（如果提供）
    if service_id:
        service_id = int(service_id)
    
    # 获取告警数据
    result = get_alerts(page=page, per_page=per_page, service_id=service_id)
    return jsonify(result)