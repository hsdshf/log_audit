# models/rule.py
import json
from db import get_conn
import os
def get_rules_for_service(service_id):
    """获取服务相关的所有规则（全局+服务特定）"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 获取全局规则
            cursor.execute('SELECT name, pattern, level FROM rules')
            rules = cursor.fetchall()

            # 获取并解析服务特定规则
            cursor.execute('SELECT custom_regex FROM services WHERE id = %s', (service_id,))
            custom_regex = cursor.fetchone()[0]

            if custom_regex:
                for line in custom_regex.split('\n'):
                    line = line.strip()
                    if line and '|' in line:
                        name, pattern, level = line.split('|', 2)
                        rules.append((name, pattern, level.strip()))

            return rules
    finally:
        conn.close()
#添加规则
def import_rules_from_json(file_path):
    """从JSON文件导入规则"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"规则配置文件不存在: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'rules' not in data:
        raise ValueError("JSON文件格式错误：缺少 'rules' 字段")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 获取现有规则
            cursor.execute('SELECT name, pattern, level, description FROM rules')
            existing_rules = {
                (row[0], row[1], row[2], row[3]): True
                for row in cursor.fetchall()
            }

            # 统计新增和更新的规则
            new_rules = []
            updated_rules = []

            for rule in data['rules']:
                rule_tuple = (
                    rule['name'],
                    rule['pattern'],
                    rule['level'],
                    rule['description']
                )

                if rule_tuple not in existing_rules:
                    # 检查是否存在同名规则
                    cursor.execute('SELECT id FROM rules WHERE name = %s', (rule['name'],))
                    existing_rule = cursor.fetchone()

                    if existing_rule:
                        # 更新现有规则
                        cursor.execute('''
                            UPDATE rules 
                            SET pattern = %s, level = %s, description = %s
                            WHERE name = %s
                        ''', (rule['pattern'], rule['level'], rule['description'], rule['name']))
                        updated_rules.append(rule['name'])
                    else:
                        # 添加新规则
                        cursor.execute('''
                            INSERT INTO rules (name, pattern, level, description)
                            VALUES (%s, %s, %s, %s)
                        ''', rule_tuple)
                        new_rules.append(rule['name'])

            conn.commit()

            # 返回导入结果
            return {
                'total': len(data['rules']),
                'new': len(new_rules),
                'updated': len(updated_rules),
                'new_rules': new_rules,
                'updated_rules': updated_rules
            }
    finally:
        conn.close()


def get_total_rules_count():
    """统计规则表中的总记录数"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rules")
        return cursor.fetchone()[0]
    finally:
        conn.close()


