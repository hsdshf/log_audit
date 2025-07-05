# stats.py
from flask import Blueprint, jsonify
from models.alert import (
    get_today_alerts_count,
    get_alert_count_by_level,
    get_alert_stats_with_services
)
from models.service import get_services_with_status
from models.rule import get_total_rules_count

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/overview')
def get_stats_overview():
    """获取系统概览统计信息（优化版）"""
    try:
        # 合并查询获取告警统计和服务数据
        alert_stats = get_alert_stats_with_services()

        return jsonify({
            'today_alerts': get_today_alerts_count(),
            'running_services': alert_stats['running_services'],
            'total_rules': get_total_rules_count(),
            'critical_count': alert_stats['critical_count'],
            'warning_count': alert_stats['warning_count'],
            'info_count': alert_stats['info_count'],
            'services': alert_stats['services']
        })
    except Exception as e:
        return jsonify({'error': '服务器内部错误', 'details': str(e)}), 500


@stats_bp.route('/api/stats/services/status')
def get_services_status():
    """获取所有服务状态（优化版）"""
    try:
        services = get_services_with_status()
        return jsonify(services)
    except Exception as e:
        return jsonify({'error': '服务器内部错误', 'details': str(e)}), 500