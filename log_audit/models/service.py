import json
import os

import pymysql

from db import get_conn

def get_all_services():
    """获取所有服务列表"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM services ORDER BY name')
            services = []
            for row in cursor.fetchall():
                services.append({
                    'id': row[0],
                    'name': row[1],
                    'log_path': row[2],
                    'log_format': row[3],
                    'custom_regex': row[4],
                    'active': row[5],
                    'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S'),
                    'completed':row[7]
                })
            return services
    finally:
        conn.close()

def get_service_by_name(name):
    """根据名称获取服务"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM services WHERE name = %s', (name,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'log_path': row[2],
                    'log_format': row[3],
                    'custom_regex': row[4],
                    'active': row[5],
                    'created_at': row[6].strftime('%Y-%m-%d %H:%M:%S')
                }
            return None
    finally:
        conn.close()

def add_service(name, log_path, log_format, custom_regex=None):
    """添加新服务，如果服务已存在则返回现有服务"""
    # 检查服务是否已存在
    existing_service = get_service_by_name(name)
    if existing_service:
        return existing_service

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO services (name, log_path, log_format, custom_regex)
                VALUES (%s, %s, %s, %s)
            ''', (name, log_path, log_format, custom_regex))
            conn.commit()
            
            # 获取新添加的服务
            return get_service_by_name(name)
    finally:
        conn.close()

def update_service(service_id, name, log_path, log_format, custom_regex=None, active=True):
    """更新服务信息"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE services 
                SET name = %s, log_path = %s, log_format = %s, custom_regex = %s, active = %s
                WHERE id = %s
            ''', (name, log_path, log_format, custom_regex, active, service_id))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()

def delete_service(service_id):
    """删除服务"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM services WHERE id = %s', (service_id,))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()

def update_service_status(service_id, status):
    """更新服务状态"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE services SET completed = %s WHERE id = %s', (status, service_id))
            conn.commit()
            return cursor.rowcount > 0
    finally:
        conn.close()

def get_service_alert_counts():
    """获取各服务的告警数量统计"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('''
                SELECT s.id, s.name, COUNT(a.id) as alert_count 
                FROM services s
                LEFT JOIN alerts a ON s.id = a.service_id
                GROUP BY s.id, s.name
            ''')
            return cursor.fetchall()
    finally:
        conn.close()
def get_running_services_count():
    """获取真正运行中的服务数量(active=1且completed=0)"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) FROM services 
                WHERE active = 1 AND completed = 0
            ''')
            return cursor.fetchone()[0]
    finally:
        conn.close()


def get_services_with_status():
    """获取服务状态信息（根据实际表结构调整）"""
    conn = None
    try:
        conn = get_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 修改查询语句，只查询实际存在的字段
            cursor.execute('''
                SELECT 
                    id, 
                    name, 
                    active,
                    completed,
                    CASE 
                        WHEN completed = 1 THEN 'completed'
                        WHEN active = 1 THEN 'running'
                        ELSE 'stopped'
                    END as status,
                    created_at  -- 使用已有的created_at字段替代last_checked
                FROM services
            ''')

            # 处理结果
            services = []
            for row in cursor.fetchall():
                service = {
                    'id': row['id'],
                    'name': row['name'],
                    'active': bool(row['active']),
                    'completed': bool(row['completed']),
                    'status': row['status'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                }
                services.append(service)

            return services

    except Exception as e:
        raise e
    finally:
        if conn:
            try:
                conn.close()
            except:

                pass

def import_services_from_json(file_path):
    """从JSON文件导入服务配置"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"服务配置文件不存在: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'services' not in data:
        raise ValueError("JSON文件格式错误：缺少 'services' 字段")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 获取现有服务
            cursor.execute('SELECT name, log_path, log_format, custom_regex, active, completed FROM services')
            existing_services = {
                (row[0], row[1], row[2], row[3], row[4], row[5]): True
                for row in cursor.fetchall()
            }

            # 统计新增和更新的服务
            new_services = []
            updated_services = []

            for service in data['services']:
                service_tuple = (
                    service['name'],
                    service.get('log_path', ''),
                    service.get('log_format', 'syslog'),  # 默认syslog格式
                    service.get('custom_regex', None),
                    service.get('active', 1),  # 默认激活
                    service.get('completed', 0)  # 默认未完成
                )

                if service_tuple not in existing_services:
                    # 检查是否存在同名服务
                    cursor.execute('SELECT id FROM services WHERE name = %s', (service['name'],))
                    existing_service = cursor.fetchone()

                    if existing_service:
                        # 更新现有服务
                        cursor.execute('''
                            UPDATE services 
                            SET log_path = %s, 
                                log_format = %s, 
                                custom_regex = %s,
                                active = %s,
                                completed = %s
                            WHERE name = %s
                        ''', (
                            service.get('log_path', ''),
                            service.get('log_format', 'syslog'),
                            service.get('custom_regex', None),
                            service.get('active', 1),
                            service.get('completed', 0),
                            service['name']
                        ))
                        updated_services.append(service['name'])
                    else:
                        # 添加新服务
                        cursor.execute('''
                            INSERT INTO services 
                            (name, log_path, log_format, custom_regex, active, completed)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        ''', service_tuple)
                        new_services.append(service['name'])

            conn.commit()

            # 返回导入结果
            return {
                'total': len(data['services']),
                'new': len(new_services),
                'updated': len(updated_services),
                'new_services': new_services,
                'updated_services': updated_services
            }
    finally:
        conn.close()