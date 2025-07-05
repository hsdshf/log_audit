# routes/services.py
from threading import Thread
from flask import Blueprint, request, jsonify
from models.service import (
    get_all_services, add_service, update_service,
    delete_service, get_service_by_name
)
from models.log import audit_log_file
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('services', __name__, url_prefix='/api/services')

@bp.route('', methods=['GET'])
def get_services():
    """获取所有服务列表"""
    try:
        services = get_all_services()
        return jsonify(services)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

class AuditThread(Thread):
    """专用的审计线程类"""

    def __init__(self, service_id, log_path):
        super().__init__(daemon=True)
        self.service_id = service_id
        self.log_path = log_path

    def run(self):
        try:
            logger.info(f"开始审计服务 {self.service_id} 的日志: {self.log_path}")
            audit_log_file(self.service_id, self.log_path)
        except Exception as e:
            logger.error(f"服务 {self.service_id} 审计失败: {str(e)}")


def start_audit_thread(service_id, log_path):
    """启动审计线程（线程安全方式）"""
    thread = AuditThread(service_id, log_path)
    thread.start()
    return thread


@bp.route('', methods=['POST'])
def create_service():
    """创建服务并启动审计"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        required_fields = ['name', 'log_path', 'log_format']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必要字段: {field}'}), 400

        # 检查服务是否已存在
        existing_service = get_service_by_name(data['name'])
        if existing_service:
            return jsonify({
                'message': '服务已存在',
                'service': existing_service
            }), 200

        # 添加新服务
        service = add_service(
            name=data['name'],
            log_path=data['log_path'],
            log_format=data['log_format'],
            custom_regex=data.get('custom_regex')
        )
        # 启动审计线程
        start_audit_thread(service['id'], data['log_path'])

        return jsonify({
            'message': '服务创建成功,并已开始审计',
            'service': service
        }), 201


    except Exception as e:
        logger.exception("服务创建失败")
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:service_id>', methods=['PUT'])
def update_service_route(service_id):
    """更新服务并条件性启动审计"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '无效的请求数据'}), 400

        required_fields = ['name', 'log_path', 'log_format']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必要字段: {field}'}), 400

        # 检查服务是否存在
        existing_service = get_service_by_name(data['name'])
        if existing_service and existing_service['id'] != service_id:
            return jsonify({'error': '服务名称已存在'}), 400
            # 获取旧服务信息
        old_service = get_service_by_name(data['name'])
        log_path_changed = old_service and old_service['log_path'] != data['log_path']

        # 更新服务
        success = update_service(
            service_id=service_id,
            name=data['name'],
            log_path=data['log_path'],
            log_format=data['log_format'],
            custom_regex=data.get('custom_regex'),
            active=data.get('active', True)
        )

        if not success:
            return jsonify({'error': '服务不存在'}), 404

        if log_path_changed:
            start_audit_thread(service_id, data['log_path'])

        return jsonify({
            'message': '服务更新成功' + ('，审计已重启' if log_path_changed else ''),
            'service': get_service_by_name(data['name'])
        })
    except Exception as e:
        logger.exception("服务更新失败")
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:service_id>', methods=['DELETE'])
def delete_service_route(service_id):
    """删除服务"""
    try:
        success = delete_service(service_id)
        if not success:
            return jsonify({'error': '服务不存在'}), 404

        return jsonify({'message': '服务删除成功'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
