# Linux日志审计系统

## 项目简介

**Linux日志审计系统**是一个基于Flask框架开发的Web应用程序，专注于对Linux系统日志进行集中管理和智能分析。系统通过采集、存储和分析服务器日志数据，帮助管理员快速识别系统异常和安全事件，同时提供可视化报表和告警功能

## 技术栈

- **后端框架**: Flask
- **前端技术**: HTML, CSS, JavaScript(*chart.js*) ,Bootstrap,
- **数据库**: MySQL

## 功能概述

1. 日志采集
   - **多源日志采集**
     - 支持syslog标准协议采集
     - 支持自定义应用日志采集
     - 支持Nginx/Apache等Web服务日志
     - ![image-20250608184744764](./Reverse/image-20250608184744764.png)

2. 安全审计与分析
   - **规则引擎审计**
     
     - 内置100+安全审计规则
     
     - 支持自定义规则扩展
     
       可以通过json规则表自行导入
     
       ![image-20250608185132653](./Reverse/image-20250608185132653.png)
     
     - 通过内置规则匹配告警

3. 可视化视图

   - 系统概览
   - 服务列表
   - 安全事件统计	

   

   ![image-20250608185505607](./Reverse/image-20250608185505607.png)

![image-20250608185551392](./Reverse/image-20250608185551392.png)

## 系统工作流程

通过提交需要审计日志服务报表。后端调用内置数据库rules表规则进行日志匹配。然后返回审计记录日志，数据，统计信息至前端界面。

## 数据库报表设计

| 表名              | 字段说明                                                     | 约束/索引                                                    |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **services**      | 记录监控的服务信息：<br>• `name`: 服务名称<br>• `log_path`: 日志路径<br>• `log_format`: 日志格式<br>• `custom_regex`: 自定义正则<br>• `active`: 激活状态 | 主键: `id`<br>注释: 包含各字段用途说明                       |
| **rules**         | 存储审计规则：<br>• `name`: 规则名称<br>• `pattern`: 匹配模式<br>• `level`: 告警级别<br>• `description`: 规则描述 | 主键: `id`<br>注释: 包含规则创建时间戳                       |
| **alerts**        | 记录触发的告警：<br>• `service_id`: 关联服务<br>• `rule_name`: 触发规则<br>• `log_entry`: 原始日志<br>• `level`: 告警级别 | 主键: `id`<br>外键: `service_id`关联services表<br>索引: 自动创建的外键索引 |
| **audited_logs**  | 存储已审计日志：<br>• `service_id`: 关联服务<br>• `log_entry`: 日志内容<br>• `audit_time`: 审计时间 | 主键: `id`<br>外键: `service_id`<br>唯一索引: `unique_log`防止重复日志(限制前255字符) |
| **log_positions** | 记录日志读取位置：<br>• `service_id`: 关联服务<br>• `file_path`: 文件路径<br>• `last_position`: 最后读取位置 | 主键: `id`<br>外键: `service_id`<br>唯一索引: `unique_file`确保每个服务文件唯一 |

### 关键设计说明：

1. **外键关系**：`alerts`、`audited_logs`、`log_positions`均通过`service_id`关联`services`表，并设置`ON DELETE CASCADE`
2. **唯一性控制**：<br>• `audited_logs`表通过`unique_log`索引避免重复存储相同日志<br>• `log_positions`表通过`unique_file`确保每个服务的日志文件只记录一个位置
3. **注释完善**：所有表和字段均包含详细的注释说明（COMMENT）

## 安装与部署

### 环境准备

- Python 3.10.12
- Flask 2.0.3
- MySQL 8.0
- 安装必要的依赖包
- Ubuntu 22.04.5 LTS

### 安装步骤

1. **解压**log_audit.zip:

   ```bash
   unzip log_audit.zip
   cd log_audit
   ```

2. **创建并激活虚拟环境**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **安装依赖**:

   ```bash
   pip install -r requirements.txt
   pip install Werkzeug==2.0.3 --force-reinstall #降级 Werkzeug
   ```

4. **配置 MySQL 数据库**:
   在 `config.py` 文件中配置 MySQL 数据库连接：

   ```python
   # config.py
   DB_CONFIG = {
       'host': 'localhost',
       'port': 3306,
       'user': 'root',
       'password': 'root',
       'db': 'log_audit',
       'charset': 'utf8mb4'
   }
   ```

   ![image-20250613181103370](./Reverse/image-20250613181103370.png)
   
   ```sql
   #这里得建数据库log_audit。
   create database if not exists log_audit default charset=utf8；
   
   ```
   
   
   
5. **运行服务器**:

   ```bash
   source .venv/bin/activate
   python app.py
   ```

6. **访问应用**:
   打开浏览器，输入 `http://127.0.0.1:5000/` 即可访问应用。第一次访问界面反应有点慢。

   ![image-20250608184723060](./Reverse/image-20250608184723060.png)

## 开发指南

### 目录结构

```
# Linux日志审计系统 (log_audit)

## 项目结构说明

### 核心目录
├── config/                          # 系统配置文件目录
│   ├── rules.json                   # 审计规则配置文件(JSON格式)
│   │   - 定义日志匹配规则和告警级别
│   └── services.json                # 服务监控配置文件(JSON格式)
│       - 定义需要监控的日志服务及其路径

├── config.py                        # 数据库配置文件
│   - 包含数据库连接参数(主机、端口、用户名、密码等)
│   - 可配置不同环境的数据库连接

├── db/                              # 数据库操作模块
│   ├── __init__.py                  # 数据库连接复用方法
│   │   - 提供统一的数据库连接池管理
│   │   - 实现连接重用和自动回收

### 数据模型层
├── models/                          # 数据模型层
│   ├── __init__.py                  # 模型包初始化文件
│   ├── alert.py                     # 告警模型
│   │   - 定义告警数据结构
│   │   - 处理告警的CRUD操作
│   ├── db_utils.py                  # 数据库工具
│   │   - 封装常用SQL操作
│   │   - 提供事务管理功能
│   ├── log.py                       # 日志模型  
│   │   - 日志条目数据结构
│   │   - 日志解析和存储逻辑
│   ├── rule.py                      # 规则模型
│   │   - 审计规则定义
│   │   - 规则匹配引擎实现
│   └── service.py                   # 服务模型
│       - 监控服务管理
│       - 服务状态检测逻辑

### 路由层
├── routes/                          # API路由层
│   ├── alerts.py                    # 告警相关API
│   │   - 告警查询/创建/删除接口
│   ├── index.py                     # 首页路由
│   ├── __init__.py                  # 路由初始化
│   ├── logs.py                      # 日志查询API
│   │   - 日志检索接口
│   │   - 日志分析接口
│   ├── services.py                  # 服务管理API
│   │   - 服务注册/注销接口
│   │   - 服务状态查询
│   └── stats.py                     # 统计信息API
│       - 系统运行统计
│       - 图表数据接口

### 主程序
├── __init__.py                      # 项目初始化文件
├── requirements.txt                 # 项目依赖列表
│   - Flask/PyMySQL等依赖包及版本
├── app.py                           # 应用入口
│   - Flask应用初始化
│   - 路由注册
│   - 中间件配置

### 前端资源
├── templates/                       # 前端模板
│   └── index.html                   # 主界面模板
│       - 基于Bootstrap的管理界面
│       - 实时日志展示区
│       - 统计图表区

### 测试资源
├── syslog/                          # 系统日志样例
│   - 用于测试的系统日志文件
└── test.log                         # 测试日志文件
    - 通用日志格式测试数据

```





## 系统演习

1.添加服务日志审计

![image-20250608191912536](./Reverse/image-20250608191912536.png)

![image-20250608192217637](./Reverse/image-20250608192217637.png)

![image-20250608192252123](./Reverse/image-20250608192252123.png)

2.安全事件统计

![image-20250608192453383](./Reverse/image-20250608192453383.png)

3.数据库审计日志记录

![image-20250608192749670](./Reverse/image-20250608192749670.png)

## 项目特点

1. **模块化设计**：清晰的分层结构(MVC模式)
2. **配置化**：审计规则和服务监控完全通过JSON配置
3. **可扩展**：易于添加新的日志解析规则
4. **安全性**：数据库连接池管理和参数化查询

可以通过查看各模块的详细注释了解具体实现细节。

## 系统不足

1.前端静态样式调用网络资源，需联网才能使用。

2.审计功能可以引入实时审计更新。

3.搜索功能未完善。

## 总结

由于时间原因有许多地方或有不足。不过对我自己来说该项目能从零到有，也是相当锻炼到自己。