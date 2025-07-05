from flask import Blueprint, jsonify, request
from models.alert import get_alerts

bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')


@bp.route('/', methods=['GET'])
def get_alerts_route():
    """
    获取告警列表
    查询参数:
        service_id: 按服务ID过滤
        level: 按告警级别过滤
        rule_name: 按规则名称过滤
        since: 起始时间(ISO格式)
        until: 结束时间(ISO格式)
        page: 页码(默认1)
        per_page: 每页数量(默认10)
    """
    try:
        # 获取查询参数
        service_id = request.args.get('service_id', type=int)
        level = request.args.get('level')
        rule_name = request.args.get('rule_name')
        since = request.args.get('since')
        until = request.args.get('until')
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)

        # 获取告警数据
        alerts = get_alerts(
            page=page,
            per_page=per_page,
            service_id=service_id,
            level=level,
            rule_name=rule_name,
            since=since,
            until=until
        )

        return jsonify(alerts)
    except ValueError as e:
        return jsonify({'error': '参数格式错误', 'details': str(e)}), 400
    except Exception as e:
        return jsonify({'error': '服务器错误', 'details': str(e)}), 500