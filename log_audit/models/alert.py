from db import get_conn
from datetime import datetime
import pymysql

def get_alerts(page=1, per_page=20, service_id=None, level=None, rule_name=None, since=None, until=None):
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 构建基础查询
            base_query = '''
                SELECT a.*, s.name AS service_name 
                FROM alerts a
                LEFT JOIN services s ON a.service_id = s.id
            '''

            # 构建 WHERE 条件
            conditions = []
            params = []

            if service_id is not None:
                conditions.append('a.service_id = %s')
                params.append(service_id)

            if level:
                conditions.append('a.level = %s')
                params.append(level)

            if rule_name:
                conditions.append('a.rule_name = %s')
                params.append(rule_name)

            if since:
                if isinstance(since, str):
                    since = datetime.fromisoformat(since.rstrip('Z'))
                conditions.append('a.timestamp >= %s')
                params.append(since)

            if until:
                if isinstance(until, str):
                    until = datetime.fromisoformat(until.rstrip('Z'))
                conditions.append('a.timestamp <= %s')
                params.append(until)

            where_clause = 'WHERE ' + ' AND '.join(conditions) if conditions else ''

            # 获取总记录数
            count_query = f'SELECT COUNT(*) FROM alerts a {where_clause}'
            cursor.execute(count_query, params)
            total = cursor.fetchone()['COUNT(*)']

            # 获取分页数据
            query = f'''
                {base_query}
                {where_clause}
                ORDER BY a.timestamp DESC
                LIMIT %s OFFSET %s
            '''
            params.extend([per_page, (page - 1) * per_page])

            cursor.execute(query, params)
            alerts = cursor.fetchall()

            return {
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page,
                'items': [{
                    'id': row['id'],
                    'service_id': row['service_id'],
                    'service': row['service_name'],
                    'rule': row['rule_name'],
                    'message': row['log_entry'],
                    'level': row['level'],
                    'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None
                } for row in alerts]
            }
    finally:
        conn.close()



def get_today_alerts_count():
    """获取今日新增告警数量"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''SELECT COUNT(*) FROM alerts 
                          WHERE timestamp >= CURDATE()''')
            return cursor.fetchone()[0]
    finally:
        conn.close()


def get_alert_count_by_level(level):
    """获取指定级别的告警数量"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''SELECT COUNT(*) FROM alerts 
                          WHERE level = %s''', (level,))
            return cursor.fetchone()[0]
    finally:
        conn.close()


def get_alert_stats():
    """获取告警统计信息"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 获取各级别告警数量
            cursor.execute('''
                SELECT level, COUNT(*) as count 
                FROM alerts 
                GROUP BY level
            ''')
            level_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # 获取今日告警趋势
            cursor.execute('''
                SELECT HOUR(timestamp) as hour, COUNT(*) as count
                FROM alerts
                WHERE timestamp >= CURDATE()
                GROUP BY HOUR(timestamp)
                ORDER BY hour
            ''')
            hourly_trend = cursor.fetchall()

            return {
                'level_stats': level_stats,
                'hourly_trend': hourly_trend
            }
    finally:
        conn.close()
def get_alert_stats_with_services():
    """获取告警统计信息（包含服务数据）"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 一次性获取所有需要的统计信息
            cursor.execute('''
                SELECT 
                    SUM(CASE WHEN level = 'critical' THEN 1 ELSE 0 END) as critical_count,
                    SUM(CASE WHEN level = 'warning' THEN 1 ELSE 0 END) as warning_count,
                    SUM(CASE WHEN level = 'info' THEN 1 ELSE 0 END) as info_count,
                    COUNT(DISTINCT CASE WHEN active = 1 AND completed = 0 THEN s.id END) as running_services
                FROM alerts a
                LEFT JOIN services s ON a.service_id = s.id
            ''')
            stats = cursor.fetchone()

            # 获取各服务告警数量
            cursor.execute('''
                SELECT s.id, s.name, COUNT(a.id) as alert_count 
                FROM services s
                LEFT JOIN alerts a ON s.id = a.service_id
                GROUP BY s.id, s.name
            ''')
            services = cursor.fetchall()

            return {
                'critical_count': stats['critical_count'] or 0,
                'warning_count': stats['warning_count'] or 0,
                'info_count': stats['info_count'] or 0,
                'running_services': stats['running_services'] or 0,
                'services': services
            }
    finally:
        conn.close()