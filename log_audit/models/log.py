import pymysql

from db import get_conn
from models.service import update_service_status
import re
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor
import time
from pymysql import OperationalError

# Constants
BATCH_SIZE = 100  # Number of logs to process before bulk DB operations
MAX_RETRIES = 3  # Maximum retries for database operations
LOCK_WAIT_TIMEOUT = 2  # Seconds to wait between retries


def get_log_position(service_id, file_path):
    """获取日志文件的最后读取位置"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT last_position, last_modified 
                FROM log_positions 
                WHERE service_id = %s AND file_path = %s
            ''', (service_id, file_path))
            result = cursor.fetchone()
            return result if result else (0, None)
    finally:
        conn.close()


def update_log_position(service_id, file_path, position, modified_time):
    """更新日志文件的读取位置"""
    for attempt in range(MAX_RETRIES):
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO log_positions (service_id, file_path, last_position, last_modified, last_check)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE 
                        last_position = VALUES(last_position),
                        last_modified = VALUES(last_modified),
                        last_check = NOW()
                ''', (service_id, file_path, position, modified_time))
                conn.commit()
                return
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1 and "Lock wait timeout" in str(e):
                time.sleep(LOCK_WAIT_TIMEOUT)
                continue
            raise
        finally:
            conn.close()


def audit_log_file(service_id, file_path):
    """审计日志文件"""
    if not os.path.exists(file_path):
        print(f"日志文件不存在: {file_path}")
        return

    # 获取文件信息
    file_stat = os.stat(file_path)
    modified_time = datetime.fromtimestamp(file_stat.st_mtime)

    # 获取上次读取位置和检查时间
    last_position, last_modified = get_log_position(service_id, file_path)

    # 如果文件被修改过，从头开始读取
    if last_modified and modified_time > last_modified:
        last_position = 0

    # 批量处理日志
    logs_buffer = []

    # 使用流式读取处理大文件
    with open(file_path, 'r', encoding='utf-8') as f:
        f.seek(last_position)

        for line in f:  # 逐行读取，避免内存问题
            if line.strip():
                logs_buffer.append((service_id, line.strip()))

                # 批量处理达到阈值
                if len(logs_buffer) >= BATCH_SIZE:
                    process_log_batch(logs_buffer)
                    logs_buffer = []

        # 处理剩余的日志
        if logs_buffer:
            process_log_batch(logs_buffer)

        current_position = f.tell()

    # 更新文件位置和检查时间
    update_log_position(service_id, file_path, current_position, modified_time)


def process_log_batch(logs_batch):
    """批量处理日志"""
    # 使用线程池并行处理
    with ThreadPoolExecutor() as executor:
        futures = []
        for service_id, log_entry in logs_batch:
            futures.append(executor.submit(audit_single_log, service_id, log_entry))

        # 等待所有任务完成
        for future in futures:
            future.result()


def audit_single_log(service_id, log_entry):
    """审计单条日志（线程安全版本）"""
    if is_log_audited(service_id, log_entry):
        return None

    # 获取规则
    from models.rule import get_rules_for_service
    rules = get_rules_for_service(service_id)

    # 规则匹配
    alert_created = False
    for rule_name, pattern, level in rules:
        try:
            if re.search(pattern, log_entry):
                create_alert(service_id, rule_name, log_entry, level)
                alert_created = True
                break  # 匹配到第一个规则就停止
        except re.error as e:
            print(f"规则 {rule_name} 的正则表达式无效: {e}")
            continue

    # 标记为已审计
    mark_log_as_audited(service_id, log_entry)

    if alert_created:
        return {
            'rule_name': rule_name,
            'level': level,
            'log_entry': log_entry
        }
    return None


def is_log_audited(service_id, log_entry):
    """检查日志是否已经审计过（带重试）"""
    for attempt in range(MAX_RETRIES):
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id FROM audited_logs 
                    WHERE service_id = %s AND log_entry = %s
                ''', (service_id, log_entry))
                return cursor.fetchone() is not None
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1 and "Lock wait timeout" in str(e):
                time.sleep(LOCK_WAIT_TIMEOUT)
                continue
            raise
        finally:
            conn.close()


def mark_log_as_audited(service_id, log_entry):
    """标记日志为已审计（带重试）"""
    for attempt in range(MAX_RETRIES):
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT IGNORE INTO audited_logs (service_id, log_entry)
                    VALUES (%s, %s)
                ''', (service_id, log_entry))
                conn.commit()
                break
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:  # 如果是重复键错误
                break  # 直接忽略，因为日志已存在
            raise  # 其他错误继续抛出
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1 and "Lock wait timeout" in str(e):
                time.sleep(LOCK_WAIT_TIMEOUT)
                continue
            raise
        finally:
            conn.close()

    # 更新服务状态（单独事务）
    update_service_status_with_retry(service_id, '1')


def update_service_status_with_retry(service_id, status):
    """带重试的服务状态更新"""
    for attempt in range(MAX_RETRIES):
        try:
            update_service_status(service_id, status)
            break
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1 and "Lock wait timeout" in str(e):
                time.sleep(LOCK_WAIT_TIMEOUT)
                continue
            raise


def create_alert(service_id, rule_name, log_entry, level):
    """创建新的告警记录（带重试）"""
    for attempt in range(MAX_RETRIES):
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                # 检查是否已存在相同的告警（2分钟内）
                cursor.execute('''
                    SELECT id FROM alerts 
                    WHERE service_id = %s 
                    AND rule_name = %s 
                    AND log_entry = %s 
                    AND timestamp > DATE_SUB(NOW(), INTERVAL 2 MINUTE)
                ''', (service_id, rule_name, log_entry))

                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO alerts (service_id, rule_name, log_entry, level)
                        VALUES (%s, %s, %s, %s)
                    ''', (service_id, rule_name, log_entry, level))
                    conn.commit()
                return
        except OperationalError as e:
            if attempt < MAX_RETRIES - 1 and "Lock wait timeout" in str(e):
                time.sleep(LOCK_WAIT_TIMEOUT)
                continue
            raise
        finally:
            conn.close()

