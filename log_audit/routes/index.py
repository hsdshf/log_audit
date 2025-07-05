# routes/index.py

from flask import Blueprint, render_template

# 创建蓝图
index_bp = Blueprint('index', __name__)

@index_bp.route('/')
def index():
    return render_template('index.html')