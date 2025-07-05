import json
import os
from db import get_conn  # 从连接池获取连接
def init_db():
        """初始化数据库表结构"""
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                # 1. 创建服务表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS services (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL COMMENT '服务名称',
                        log_path VARCHAR(255) NOT NULL COMMENT '日志路径',
                        log_format VARCHAR(50) NOT NULL COMMENT '日志格式',
                        custom_regex TEXT NULL COMMENT '自定义正则表达式',
                        active TINYINT(1) DEFAULT 1 COMMENT '是否激活',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                        completed TINYINT DEFAULT 0 COMMENT '是否完成配置'
                    )
                ''')

                # 2. 创建规则表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS rules (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL COMMENT '规则名称',
                        pattern TEXT NOT NULL COMMENT '匹配模式',
                        level VARCHAR(20) NOT NULL COMMENT '告警级别',
                        description TEXT NULL COMMENT '规则描述',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                    )
                ''')

                # 3. 创建告警表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        service_id INT NULL COMMENT '关联服务ID',
                        rule_name VARCHAR(100) NULL COMMENT '触发规则名称',
                        log_entry TEXT NOT NULL COMMENT '原始日志内容',
                        level VARCHAR(20) NOT NULL COMMENT '告警级别',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '触发时间',
                        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
                    )
                ''')

                # 4. 创建已审计日志表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audited_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        service_id INT NOT NULL COMMENT '关联服务ID',
                        log_entry TEXT NOT NULL COMMENT '日志内容',
                        audit_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '审计时间',
                        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
                        UNIQUE KEY unique_log (service_id, log_entry(255)) COMMENT '避免重复日志'
                    )
                ''')

                # 5. 创建日志位置记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS log_positions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        service_id INT NOT NULL COMMENT '关联服务ID',
                        file_path VARCHAR(255) NOT NULL COMMENT '日志文件路径',
                        last_position BIGINT NOT NULL DEFAULT 0 COMMENT '最后读取位置',
                        last_modified TIMESTAMP NULL COMMENT '文件最后修改时间',
                        last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '最后检查时间',
                        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
                        UNIQUE KEY unique_file (service_id, file_path) COMMENT '每个服务文件唯一'
                    )
                ''')

                conn.commit()
                print("数据库表结构初始化完成")
        except Exception as e:
            print(f"数据库初始化失败: {str(e)}")
            raise
        finally:
            conn.close()


def import_services_from_json(file_path):
        """
        从JSON文件导入服务配置
        :param file_path: JSON文件路径
        :return: 导入结果字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"服务配置文件不存在: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'services' not in data:
            raise ValueError("JSON文件格式错误：缺少 'services' 字段")

        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                # 获取现有服务用于比对
                cursor.execute('''
                    SELECT name, log_path, log_format, custom_regex, active, completed 
                    FROM services
                ''')
                existing_services = {
                    (row[0], row[1], row[2], row[3], row[4], row[5]): True
                    for row in cursor.fetchall()
                }

                new_services = []
                updated_services = []

                for service in data['services']:
                    # 准备服务数据元组
                    service_tuple = (
                        service['name'],
                        service.get('log_path', ''),
                        service.get('log_format', 'syslog'),
                        service.get('custom_regex', None),
                        service.get('active', 1),
                        service.get('completed', 0)
                    )

                    if service_tuple not in existing_services:
                        # 检查是否已有同名服务
                        cursor.execute('SELECT id FROM services WHERE name = %s', (service['name'],))
                        existing_service = cursor.fetchone()

                        if existing_service:
                            # 更新现有服务
                            cursor.execute('''
                                UPDATE services SET
                                    log_path = %s,
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
                            # 新增服务
                            cursor.execute('''
                                INSERT INTO services 
                                (name, log_path, log_format, custom_regex, active, completed)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            ''', service_tuple)
                            new_services.append(service['name'])

                conn.commit()

                return {
                    'total': len(data['services']),
                    'new': len(new_services),
                    'updated': len(updated_services),
                    'new_services': new_services,
                    'updated_services': updated_services
                }
        except Exception as e:
            conn.rollback()
            raise Exception(f"导入服务配置失败: {str(e)}")
        finally:
            conn.close()


def add_test_data():
        """添加测试数据"""
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                # 添加测试服务
                cursor.execute('''
                    INSERT IGNORE INTO services 
                    (name, log_path, log_format, completed)
                    VALUES 
                    ('ssh', '/var/log/auth.log', 'syslog', 0),
                    ('apache', '/var/log/apache2/access.log', 'apache', 1),
                    ('mysql', '/var/log/mysql/error.log', 'mysql', 0)
                ''')

                # 添加测试规则
                cursor.execute('''
                    INSERT IGNORE INTO rules 
                    (name, pattern, level, description)
                    VALUES 
                    ('SSH登录失败', 'Failed password', 'high', 'SSH登录失败尝试'),
                    ('Apache 404错误', 'HTTP/1.1" 404', 'medium', '访问不存在的页面')
                ''')

                conn.commit()
                print("测试数据添加完成")
        except Exception as e:
            conn.rollback()
            print(f"添加测试数据失败: {str(e)}")
            raise
        finally:
            conn.close()

def clear_database():
        """清空数据库所有表数据"""
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                # 临时禁用外键约束
                cursor.execute('SET FOREIGN_KEY_CHECKS = 0')

                # 清空所有表
                tables = ['alerts', 'audited_logs', 'log_positions', 'rules', 'services']
                for table in tables:
                    cursor.execute(f'TRUNCATE TABLE {table}')
                    print(f"已清空表: {table}")

                # 恢复外键约束
                cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
                conn.commit()
                print("数据库已清空")
        except Exception as e:
            conn.rollback()
            print(f"清空数据库失败: {str(e)}")
            raise
        finally:
            conn.close()

