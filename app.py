#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import yaml
import subprocess
import threading
import time
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from flask_socketio import SocketIO, emit
import logging
import zipfile
import tempfile
import uuid
import schedule
import psutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量存储同步任务状态
sync_tasks = {}

# 仓库配置管理类
class RegistryConfig:
    """私服配置管理类"""
    def __init__(self, config_file='config/registries.yaml'):
        self.config_file = config_file
        self.registries = self.load_config()
    
    def load_config(self):
        """加载私服配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('registries', [])
        except FileNotFoundError:
            logger.warning(f"配置文件 {self.config_file} 不存在，使用默认配置")
            return self.get_default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """默认配置"""
        return [
            {
                'name': 'Harbor私服',
                'type': 'harbor',
                'url': 'harbor.example.com',
                'username': 'admin',
                'password': 'Harbor12345',
                'project': 'library'
            },
            {
                'name': '阿里云ACR',
                'type': 'acr',
                'url': 'registry.cn-hangzhou.aliyuncs.com',
                'username': 'your-username',
                'password': 'your-password',
                'namespace': 'your-namespace'
            }
        ]

class UserManager:
    """用户管理类"""
    def __init__(self, config_file='config/users.yaml'):
        self.config_file = config_file
        self.config = self.load_config()
        self.login_attempts = {}  # 登录尝试记录
        
        # 更新Flask secret key
        if self.config.get('session', {}).get('secret_key'):
            app.config['SECRET_KEY'] = self.config['session']['secret_key']
    
    def load_config(self):
        """加载用户配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"用户配置文件 {self.config_file} 不存在")
            return self.create_default_config()
        except Exception as e:
            logger.error(f"加载用户配置失败: {e}")
            return self.create_default_config()
    
    def create_default_config(self):
        """创建默认用户配置"""
        default_config = {
            'users': {
                'admin': {
                    'username': 'admin',
                    'password_hash': self.hash_password('admin123'),
                    'role': 'admin',
                    'display_name': '管理员',
                    'active': True
                }
            },
            'session': {
                'secret_key': secrets.token_hex(32),
                'session_timeout': 3600,
                'remember_me_duration': 604800
            },
            'security': {
                'max_login_attempts': 5,
                'lockout_duration': 300,
                'password_min_length': 6
            }
        }
        
        # 保存默认配置
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"已创建默认用户配置文件: {self.config_file}")
        except Exception as e:
            logger.error(f"创建用户配置文件失败: {e}")
        
        return default_config
    
    def hash_password(self, password):
        """哈希密码"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password, password_hash):
        """验证密码"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"密码验证失败: {e}")
            return False
    
    def get_user(self, username):
        """获取用户信息"""
        users = self.config.get('users', {})
        return users.get(username)
    
    def authenticate(self, username, password, request_ip=None):
        """用户认证"""
        # 检查账户锁定
        if self.is_account_locked(username, request_ip):
            return False, "账户已被锁定，请稍后再试"
        
        user = self.get_user(username)
        if not user:
            self.record_login_attempt(username, request_ip, False)
            return False, "用户名或密码错误"
        
        if not user.get('active', True):
            return False, "账户已被禁用"
        
        if self.verify_password(password, user['password_hash']):
            # 登录成功，清除登录尝试记录
            self.clear_login_attempts(username, request_ip)
            self.update_last_login(username)
            return True, "登录成功"
        else:
            self.record_login_attempt(username, request_ip, False)
            return False, "用户名或密码错误"
    
    def is_account_locked(self, username, request_ip):
        """检查账户是否被锁定"""
        key = f"{username}:{request_ip}" if request_ip else username
        attempts = self.login_attempts.get(key, [])
        
        security_config = self.config.get('security', {})
        max_attempts = security_config.get('max_login_attempts', 5)
        lockout_duration = security_config.get('lockout_duration', 300)
        
        if len(attempts) >= max_attempts:
            last_attempt = attempts[-1]
            if datetime.now() - last_attempt < timedelta(seconds=lockout_duration):
                return True
        
        return False
    
    def record_login_attempt(self, username, request_ip, success):
        """记录登录尝试"""
        key = f"{username}:{request_ip}" if request_ip else username
        
        if success:
            # 成功登录，清除记录
            self.login_attempts.pop(key, None)
        else:
            # 失败登录，记录时间
            if key not in self.login_attempts:
                self.login_attempts[key] = []
            self.login_attempts[key].append(datetime.now())
            
            # 只保留最近的尝试记录
            security_config = self.config.get('security', {})
            max_attempts = security_config.get('max_login_attempts', 5)
            self.login_attempts[key] = self.login_attempts[key][-max_attempts:]
    
    def clear_login_attempts(self, username, request_ip):
        """清除登录尝试记录"""
        key = f"{username}:{request_ip}" if request_ip else username
        self.login_attempts.pop(key, None)
    
    def update_last_login(self, username):
        """更新最后登录时间"""
        try:
            self.config['users'][username]['last_login'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            logger.error(f"更新最后登录时间失败: {e}")
    
    def is_session_valid(self, session_data):
        """检查会话是否有效"""
        if not session_data:
            return False
        
        username = session_data.get('username')
        login_time = session_data.get('login_time')
        
        if not username or not login_time:
            return False
        
        # 检查用户是否存在且活跃
        user = self.get_user(username)
        if not user or not user.get('active', True):
            return False
        
        # 检查会话是否过期
        session_config = self.config.get('session', {})
        session_timeout = session_config.get('session_timeout', 3600)
        
        try:
            login_datetime = datetime.fromisoformat(login_time)
            if datetime.now() - login_datetime > timedelta(seconds=session_timeout):
                return False
        except Exception:
            return False
        
        return True

def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not user_manager.is_session_valid(session):
            if request.is_json:
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not user_manager.is_session_valid(session):
            if request.is_json:
                return jsonify({'error': '需要登录', 'redirect': '/login'}), 401
            return redirect(url_for('login'))
        
        username = session.get('username')
        user = user_manager.get_user(username)
        
        if not user or user.get('role') != 'admin':
            if request.is_json:
                return jsonify({'error': '需要管理员权限'}), 403
            return render_template('error.html', 
                                 error_code=403, 
                                 error_message='需要管理员权限才能访问此页面')
        
        return f(*args, **kwargs)
    return decorated_function

# 创建用户管理实例
user_manager = UserManager()
# 创建仓库配置管理实例
registry_config = RegistryConfig()

class ImageSyncer:
    """镜像同步类"""
    def __init__(self, registry_config):
        self.registry_config = registry_config
        self.current_task_id = None
    
    def check_skopeo(self):
        """检查Skopeo是否安装"""
        try:
            result = subprocess.run(['skopeo', '--version'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def sync_images(self, task_id, images, target_registry, replace_level, source_auth=None, proxy_config=None, target_project=None):
        """同步镜像列表"""
        self.current_task_id = task_id
        sync_tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'total': len(images),
            'current_image': '',
            'logs': [],
            'start_time': datetime.now(),
            'errors': []
        }
        
        try:
            # 检查Skopeo是否安装
            if not self.check_skopeo():
                self.emit_log(task_id, "错误: Skopeo工具未安装，请先安装Skopeo", "error")
                sync_tasks[task_id]['status'] = 'failed'
                return
            
            registry = next((r for r in self.registry_config.registries if r['name'] == target_registry), None)
            if not registry:
                self.emit_log(task_id, f"错误: 找不到私服配置 {target_registry}", "error")
                sync_tasks[task_id]['status'] = 'failed'
                return
            
            self.emit_log(task_id, f"开始同步 {len(images)} 个镜像到 {target_registry}")
            
            # 如果配置了源认证信息，记录日志
            if source_auth:
                self.emit_log(task_id, f"已配置源仓库认证信息，用户名: {source_auth['username']}")
            
            # 如果配置了代理，记录日志
            if proxy_config:
                http_proxy = proxy_config.get('http_proxy', '')
                https_proxy = proxy_config.get('https_proxy', '')
                self.emit_log(task_id, f"已配置网络代理 - HTTP: {http_proxy}, HTTPS: {https_proxy}")
                if proxy_config.get('no_proxy'):
                    self.emit_log(task_id, f"不使用代理的地址: {proxy_config['no_proxy']}")
            
            for i, image in enumerate(images):
                if sync_tasks[task_id]['status'] == 'cancelled':
                    self.emit_log(task_id, "同步任务已取消")
                    return
                
                sync_tasks[task_id]['current_image'] = image
                self.emit_log(task_id, f"正在同步镜像 ({i+1}/{len(images)}): {image}")
                
                target_image = self.sync_single_image(task_id, image, registry, replace_level, source_auth, proxy_config, target_project)
                
                if target_image:
                    self.emit_log(task_id, f"📋 同步任务完成: {image}", "success")
                    self.emit_log(task_id, f"   ➤ 目标地址: {target_image}", "success")
                else:
                    self.emit_log(task_id, f"❌ 镜像 {image} 同步失败", "error")
                    sync_tasks[task_id]['errors'].append(image)
                
                sync_tasks[task_id]['progress'] = i + 1
                self.emit_progress(task_id)
            
            sync_tasks[task_id]['status'] = 'completed'
            sync_tasks[task_id]['end_time'] = datetime.now()
            
            error_count = len(sync_tasks[task_id]['errors'])
            if error_count == 0:
                self.emit_log(task_id, f"所有镜像同步完成！", "success")
            else:
                self.emit_log(task_id, f"同步完成，但有 {error_count} 个镜像失败", "warning")
        
        except Exception as e:
            self.emit_log(task_id, f"同步过程中发生错误: {str(e)}", "error")
            import traceback
            self.emit_log(task_id, f"异常详情: {traceback.format_exc()}", "error")
            return False
    
    def sync_single_image(self, task_id, source_image, registry, replace_level, source_auth=None, proxy_config=None, target_project=None):
        """同步单个镜像"""
        try:
            self.emit_log(task_id, f"开始处理镜像: {source_image}")
            
            # 检查是否是本地文件导出
            if registry['type'] == 'local_file':
                return self.export_image_to_file(task_id, source_image, registry, replace_level, source_auth, proxy_config, target_project)
            
            # 获取基础URL和命名空间/项目
            base_url = registry['url']
            
            # 优先使用用户输入的目标项目/命名空间，否则使用配置文件中的默认值
            if target_project:
                namespace = target_project
                self.emit_log(task_id, f"使用用户指定的项目/命名空间: {namespace}")
            else:
                # 使用配置文件中的默认值
                if registry['type'] == 'harbor':
                    namespace = registry.get('project', 'library')
                elif registry['type'] == 'acr':
                    namespace = registry.get('namespace', 'default')
                elif registry['type'] == 'nexus':
                    namespace = registry.get('repository', 'docker-hosted')
                elif registry['type'] == 'swr':
                    namespace = registry.get('namespace', 'default')
                elif registry['type'] == 'tcr':
                    namespace = registry.get('namespace', 'default')
                else:
                    namespace = 'library'  # 默认命名空间
                self.emit_log(task_id, f"使用配置文件默认项目/命名空间: {namespace}")
            
            self.emit_log(task_id, f"私服类型: {registry['type']}, 最终命名空间: {namespace}")
            
            # 应用替换级别构建目标镜像地址
            target_image_path = self.apply_replace_level(source_image, namespace, replace_level)
            self.emit_log(task_id, f"替换级别处理结果: {target_image_path}")
            
            # target_image_path已经包含了namespace，所以直接用base_url拼接
            if target_image_path.startswith(namespace + '/'):
                # 如果已经包含namespace，直接拼接
                target_image = f"{base_url}/{target_image_path}"
            else:
                # 如果不包含namespace，需要添加
                target_image = f"{base_url}/{namespace}/{target_image_path}"
            
            self.emit_log(task_id, f"最终目标镜像: {target_image}")
            
            # 构建skopeo命令
            cmd = ['skopeo', 'copy']
            
            # 添加基本参数，兼容当前skopeo版本
            cmd.extend(['--dest-tls-verify=false', '--src-tls-verify=false'])
            
            # 添加网络优化参数（移除不支持的--retry-times）
            cmd.extend([
                '--format', 'v2s2'     # 使用较新的镜像格式
            ])
            
            # 对于阿里云ACR，添加特殊处理
            if 'aliyuncs.com' in registry['url']:
                self.emit_log(task_id, "检测到阿里云ACR，启用优化配置")
                # 阿里云ACR建议使用的参数
                cmd.extend(['--dest-compress-format', 'gzip'])
            
            # 添加源认证信息（如果提供）
            if source_auth and source_auth.get('username') and source_auth.get('password'):
                cmd.extend(['--src-creds', f"{source_auth['username']}:{source_auth['password']}"])
                self.emit_log(task_id, f"添加源仓库认证信息，用户名: {source_auth['username']}")
            else:
                self.emit_log(task_id, "源仓库: 公开访问")
            
            # 添加目标认证信息
            if registry.get('username') and registry.get('password'):
                cmd.extend(['--dest-creds', f"{registry['username']}:{registry['password']}"])
                self.emit_log(task_id, f"添加目标仓库认证信息，用户名: {registry['username']}")
            else:
                self.emit_log(task_id, "目标仓库: 未配置认证信息")
            
            # 添加源和目标地址
            cmd.extend([f'docker://{source_image}', f'docker://{target_image}'])
            
            # 显示完整命令（隐藏密码）
            safe_cmd = cmd.copy()
            for i, part in enumerate(safe_cmd):
                if ('--dest-creds' in safe_cmd or '--src-creds' in safe_cmd) and i > 0:
                    if safe_cmd[i-1] in ['--dest-creds', '--src-creds']:
                        safe_cmd[i] = safe_cmd[i].split(':')[0] + ':***'
            self.emit_log(task_id, f"执行命令: {' '.join(safe_cmd)}")
            
            # 执行同步命令
            self.emit_log(task_id, "开始执行skopeo命令...")
            try:
                # 准备环境变量
                env = os.environ.copy()
                
                # 如果配置了代理，设置环境变量
                if proxy_config:
                    # 智能处理代理排除列表，自动添加目标私服地址
                    no_proxy_list = []
                    if proxy_config.get('no_proxy'):
                        no_proxy_list = [addr.strip() for addr in proxy_config['no_proxy'].split(',')]
                    
                    # 自动添加目标私服地址到排除列表
                    target_registry_url = registry['url']
                    if target_registry_url not in no_proxy_list:
                        no_proxy_list.append(target_registry_url)
                        self.emit_log(task_id, f"自动将目标私服添加到代理排除列表: {target_registry_url}")
                    
                    if proxy_config.get('http_proxy'):
                        env['HTTP_PROXY'] = proxy_config['http_proxy']
                        env['http_proxy'] = proxy_config['http_proxy']
                        self.emit_log(task_id, f"设置HTTP代理: {proxy_config['http_proxy']}")
                    
                    if proxy_config.get('https_proxy'):
                        env['HTTPS_PROXY'] = proxy_config['https_proxy']
                        env['https_proxy'] = proxy_config['https_proxy']
                        self.emit_log(task_id, f"设置HTTPS代理: {proxy_config['https_proxy']}")
                    
                    # 设置更新后的排除列表
                    if no_proxy_list:
                        no_proxy_str = ','.join(no_proxy_list)
                        env['NO_PROXY'] = no_proxy_str
                        env['no_proxy'] = no_proxy_str
                        self.emit_log(task_id, f"代理排除列表: {no_proxy_str}")
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,  # 分别处理stderr
                    text=True,
                    universal_newlines=True,
                    env=env  # 传递环境变量
                )
                
                # 对于阿里云ACR，使用更长的超时时间
                timeout_seconds = 300  # 默认5分钟
                if 'aliyuncs.com' in registry['url']:
                    timeout_seconds = 600  # 阿里云ACR使用10分钟超时
                    self.emit_log(task_id, f"阿里云ACR同步，设置超时时间: {timeout_seconds}秒")
                
                # 设置超时
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                
                # 输出标准输出
                if stdout:
                    for line in stdout.strip().split('\n'):
                        if line.strip():
                            self.emit_log(task_id, f"  {line}")
                
                # 输出错误信息
                if stderr:
                    for line in stderr.strip().split('\n'):
                        if line.strip():
                            # 判断是否是网络相关错误
                            if any(keyword in line.lower() for keyword in ['timeout', 'dial tcp', 'connection', 'network']):
                                self.emit_log(task_id, f"  网络错误: {line}", "error")
                            else:
                                self.emit_log(task_id, f"  错误: {line}", "warning")
                
                self.emit_log(task_id, f"命令执行完成，返回码: {process.returncode}")
                
                if process.returncode == 0:
                    self.emit_log(task_id, f"✅ 镜像同步成功", "success")
                    self.emit_log(task_id, f"   源镜像: {source_image}", "info")
                    self.emit_log(task_id, f"   目标镜像: {target_image}", "info")
                    return target_image  # 返回目标镜像地址而不是True
                else:
                    # 根据错误类型给出不同的提示
                    if stderr and any(keyword in stderr.lower() for keyword in ['timeout', 'dial tcp', 'connection']):
                        self.emit_log(task_id, f"网络连接超时或失败，可能原因：", "error")
                        self.emit_log(task_id, f"  1. 无法访问源镜像仓库 (如Docker Hub被墙)", "error")
                        self.emit_log(task_id, f"  2. 网络连接不稳定", "error")
                        self.emit_log(task_id, f"  3. 建议使用国内镜像源或本地镜像", "error")
                    elif stderr and 'aliyuncs.com' in stderr and 'unexpected EOF' in stderr:
                        self.emit_log(task_id, f"阿里云ACR认证连接中断，可能原因：", "error")
                        self.emit_log(task_id, f"  1. 网络连接不稳定，认证过程中断", "error")
                        self.emit_log(task_id, f"  2. 阿里云ACR服务暂时不可用", "error")
                        self.emit_log(task_id, f"  3. 镜像层过大，传输超时", "error")
                        self.emit_log(task_id, f"  4. 建议：稍后重试或检查网络连接", "error")
                        self.emit_log(task_id, f"  5. 确认阿里云ACR认证信息是否正确", "error")
                    elif stderr and 'aliyuncs.com' in stderr:
                        self.emit_log(task_id, f"阿里云ACR推送失败，建议检查：", "error")
                        self.emit_log(task_id, f"  1. 账号权限是否足够（需要push权限）", "error")
                        self.emit_log(task_id, f"  2. 命名空间是否存在且可访问", "error")
                        self.emit_log(task_id, f"  3. 网络连接是否稳定", "error")
                        self.emit_log(task_id, f"  4. 认证信息是否正确", "error")
                    else:
                        self.emit_log(task_id, f"skopeo命令执行失败，返回码: {process.returncode}", "error")
                    return False
                    
            except subprocess.TimeoutExpired:
                process.kill()
                self.emit_log(task_id, f"镜像同步超时(3分钟)，请检查网络连接", "error")
                self.emit_log(task_id, f"建议：使用国内镜像源或检查网络配置", "error")
                return False
        
        except Exception as e:
            self.emit_log(task_id, f"同步镜像 {source_image} 时发生异常: {str(e)}", "error")
            import traceback
            self.emit_log(task_id, f"异常详情: {traceback.format_exc()}", "error")
            return False
    
    def apply_replace_level(self, source_image, namespace, replace_level):
        """根据替换级别应用镜像路径变换"""
        # 移除可能的registry前缀 (如 docker.io/, gcr.io/ 等)
        if '/' in source_image and '.' in source_image.split('/')[0]:
            # 如果第一部分包含点，可能是registry地址，去除它
            parts = source_image.split('/')
            if len(parts) > 1 and ('.' in parts[0] or ':' in parts[0]):
                source_image = '/'.join(parts[1:])
        
        # 分割镜像路径
        path_parts = source_image.split('/')
        
        if replace_level == 'all':
            # 替换所有级：只保留最后的镜像名
            image_name = path_parts[-1]
            return f"{namespace}/{image_name}"
        elif replace_level == 'none':
            # 无替换：保留完整路径
            return f"{namespace}/{source_image}"
        elif replace_level in ['1', '2', '3']:
            # 替换指定级别
            replace_count = int(replace_level)
            if len(path_parts) > replace_count:
                # 去除前面的指定级别
                remaining_parts = path_parts[replace_count:]
                remaining_path = '/'.join(remaining_parts)
                return f"{namespace}/{remaining_path}"
            else:
                # 如果路径级别不够，只保留镜像名
                image_name = path_parts[-1]
                return f"{namespace}/{image_name}"
        else:
            # 默认处理：替换1级
            if len(path_parts) > 1:
                remaining_parts = path_parts[1:]
                remaining_path = '/'.join(remaining_parts)
                return f"{namespace}/{remaining_path}"
            else:
                return f"{namespace}/{source_image}"
    
    def image_exists(self, image, registry):
        """检查镜像是否存在"""
        try:
            cmd = ['skopeo', 'inspect', f'docker://{image}']
            if registry.get('username') and registry.get('password'):
                cmd.extend(['--creds', f"{registry['username']}:{registry['password']}"])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def emit_log(self, task_id, message, level="info"):
        """发送日志到前端"""
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': level,
            'message': message
        }
        sync_tasks[task_id]['logs'].append(log_entry)
        socketio.emit('sync_log', {'task_id': task_id, 'log': log_entry})
    
    def emit_progress(self, task_id):
        """发送进度到前端"""
        task = sync_tasks[task_id]
        progress_data = {
            'task_id': task_id,
            'progress': task['progress'],
            'total': task['total'],
            'current_image': task['current_image'],
            'status': task['status']
        }
        socketio.emit('sync_progress', progress_data)

    def export_image_to_file(self, task_id, source_image, registry, replace_level, source_auth=None, proxy_config=None, target_project=None):
        """导出镜像到本地文件"""
        try:
            # 确保下载目录存在
            downloads_dir = registry['url']
            os.makedirs(downloads_dir, exist_ok=True)
            
            # 生成安全的文件名
            safe_image_name = source_image.replace('/', '_').replace(':', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{safe_image_name}_{timestamp}.tar"
            file_path = os.path.join(downloads_dir, filename)
            
            self.emit_log(task_id, f"导出类型: 本地文件")
            self.emit_log(task_id, f"文件路径: {file_path}")
            
            # 构建skopeo命令 - 使用保留名称的格式
            cmd = ['skopeo', 'copy']
            
            # 添加基本参数
            cmd.extend(['--src-tls-verify=false'])
            
            # 添加源认证信息（如果提供）
            if source_auth and source_auth.get('username') and source_auth.get('password'):
                cmd.extend(['--src-creds', f"{source_auth['username']}:{source_auth['password']}"])
                self.emit_log(task_id, f"添加源仓库认证信息，用户名: {source_auth['username']}")
            else:
                self.emit_log(task_id, "源仓库: 公开访问")
            
            # 使用docker-archive格式，但指定目标镜像名称来保留标签
            # 格式：docker-archive:文件路径:镜像名:标签
            if ':' in source_image:
                image_name, tag = source_image.rsplit(':', 1)
                # 清理镜像名称中的registry前缀
                if '/' in image_name and '.' in image_name.split('/')[0]:
                    image_name = '/'.join(image_name.split('/')[1:])
                target_spec = f"docker-archive:{file_path}:{image_name}:{tag}"
            else:
                # 没有标签的情况，使用latest
                image_name = source_image
                if '/' in image_name and '.' in image_name.split('/')[0]:
                    image_name = '/'.join(image_name.split('/')[1:])
                target_spec = f"docker-archive:{file_path}:{image_name}:latest"
            
            cmd.extend([f'docker://{source_image}', target_spec])
            
            self.emit_log(task_id, f"目标规格: {target_spec}")
            
            # 显示完整命令（隐藏密码）
            safe_cmd = cmd.copy()
            for i, part in enumerate(safe_cmd):
                if '--src-creds' in safe_cmd and i > 0:
                    if safe_cmd[i-1] == '--src-creds':
                        safe_cmd[i] = safe_cmd[i].split(':')[0] + ':***'
            self.emit_log(task_id, f"执行命令: {' '.join(safe_cmd)}")
            
            # 执行导出命令
            self.emit_log(task_id, "开始执行skopeo导出命令...")
            try:
                # 准备环境变量
                env = os.environ.copy()
                
                # 如果配置了代理，设置环境变量
                if proxy_config:
                    if proxy_config.get('http_proxy'):
                        env['HTTP_PROXY'] = proxy_config['http_proxy']
                        env['http_proxy'] = proxy_config['http_proxy']
                        self.emit_log(task_id, f"设置HTTP代理: {proxy_config['http_proxy']}")
                    
                    if proxy_config.get('https_proxy'):
                        env['HTTPS_PROXY'] = proxy_config['https_proxy']
                        env['https_proxy'] = proxy_config['https_proxy']
                        self.emit_log(task_id, f"设置HTTPS代理: {proxy_config['https_proxy']}")
                    
                    if proxy_config.get('no_proxy'):
                        env['NO_PROXY'] = proxy_config['no_proxy']
                        env['no_proxy'] = proxy_config['no_proxy']
                        self.emit_log(task_id, f"代理排除列表: {proxy_config['no_proxy']}")
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    universal_newlines=True,
                    env=env
                )
                
                # 设置超时时间（导出可能需要更长时间）
                timeout_seconds = 600  # 10分钟
                self.emit_log(task_id, f"设置导出超时时间: {timeout_seconds}秒")
                
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                
                # 输出标准输出
                if stdout:
                    for line in stdout.strip().split('\n'):
                        if line.strip():
                            self.emit_log(task_id, f"  {line}")
                
                # 输出错误信息
                if stderr:
                    for line in stderr.strip().split('\n'):
                        if line.strip():
                            self.emit_log(task_id, f"  {line}", "warning")
                
                self.emit_log(task_id, f"命令执行完成，返回码: {process.returncode}")
                
                if process.returncode == 0:
                    # 检查文件是否存在并获取大小
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        self.emit_log(task_id, f"✅ 镜像导出成功", "success")
                        self.emit_log(task_id, f"   源镜像: {source_image}", "info")
                        self.emit_log(task_id, f"   导出文件: {filename}", "info")
                        self.emit_log(task_id, f"   文件大小: {file_size_mb:.2f} MB", "info")
                        
                        # 生成下载链接和标签脚本
                        download_url = f"/downloads/{filename}"
                        
                        # 提取镜像名称和标签用于生成标记脚本
                        if ':' in source_image:
                            final_image_name, final_tag = source_image.rsplit(':', 1)
                        else:
                            final_image_name, final_tag = source_image, 'latest'
                        
                        # 清理镜像名称中的registry前缀
                        if '/' in final_image_name and '.' in final_image_name.split('/')[0]:
                            final_image_name = '/'.join(final_image_name.split('/')[1:])
                        
                        expected_name = f"{final_image_name}:{final_tag}"
                        
                        self.emit_log(task_id, f"   下载地址: {download_url}", "success")
                        self.emit_log(task_id, f"   导入命令: docker load < {filename}", "info")
                        self.emit_log(task_id, f"   预期镜像名称: {expected_name}", "info")
                        self.emit_log(task_id, f"   💡 如果导入后显示<none>，使用以下命令重新标记:", "info")
                        self.emit_log(task_id, f"   docker tag <IMAGE_ID> {expected_name}", "info")
                        
                        # 生成标记脚本
                        script_name = f"tag_{safe_image_name}_{timestamp}.sh"
                        script_path = os.path.join(downloads_dir, script_name)
                        
                        tag_script_content = f"""#!/bin/bash
# 镜像标记脚本 - 自动生成
# 源镜像: {source_image}
# 目标名称: {expected_name}

echo "正在为导入的镜像设置正确的标签..."

# 首先载入镜像
echo "载入镜像文件: {filename}"

# 方法1: 尝试从docker load输出中获取镜像信息
LOAD_OUTPUT=$(docker load < {filename} 2>&1)
echo "Docker load 输出: $LOAD_OUTPUT"

# 提取镜像ID或镜像名（使用更兼容的方式）
IMAGE_ID=""

# 尝试匹配 "Loaded image ID: sha256:xxxx" 格式
if echo "$LOAD_OUTPUT" | grep -q "Loaded image ID:"; then
    IMAGE_ID=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image ID: sha256:\\([a-f0-9]*\\).*/\\1/p')
    if [ -n "$IMAGE_ID" ]; then
        IMAGE_ID="sha256:$IMAGE_ID"
        echo "✅ 检测到镜像ID: $IMAGE_ID"
    fi
fi

# 尝试匹配 "Loaded image: xxxx" 格式
if [ -z "$IMAGE_ID" ] && echo "$LOAD_OUTPUT" | grep -q "Loaded image:"; then
    IMAGE_ID=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image: \\(.*\\)/\\1/p')
    if [ -n "$IMAGE_ID" ]; then
        echo "✅ 检测到镜像名: $IMAGE_ID"
    fi
fi

# 方法2: 如果上面的方法失败，尝试查找最近导入的镜像
if [ -z "$IMAGE_ID" ]; then
    echo "⚠️ 无法从docker load输出中解析镜像信息，尝试其他方法..."
    
    # 查找可能的候选镜像（最近创建的，或者名称匹配的）
    CANDIDATES=$(docker images --format "table {{{{.Repository}}}}:{{{{.Tag}}}}\\t{{{{.ID}}}}\\t{{{{.CreatedAt}}}}" | grep -E "({final_image_name}|<none>)" | head -5)
    
    if [ -n "$CANDIDATES" ]; then
        echo "找到可能的候选镜像:"
        echo "$CANDIDATES"
        echo ""
        
        # 尝试找到<none>标签的镜像
        NONE_IMAGE=$(docker images --format "{{{{.ID}}}}" --filter "dangling=true" | head -1)
        if [ -n "$NONE_IMAGE" ]; then
            IMAGE_ID="$NONE_IMAGE"
            echo "✅ 找到<none>标签镜像: $IMAGE_ID"
        else
            # 尝试找到最近的匹配镜像
            RECENT_IMAGE=$(docker images --format "{{{{.ID}}}}" {final_image_name} 2>/dev/null | head -1)
            if [ -n "$RECENT_IMAGE" ]; then
                IMAGE_ID="$RECENT_IMAGE"
                echo "✅ 找到已存在的镜像: $IMAGE_ID"
            fi
        fi
    fi
fi

# 方法3: 最后的手动提示
if [ -z "$IMAGE_ID" ]; then
    echo "❌ 无法自动获取镜像ID，请手动处理："
    echo ""
    echo "1. 查看所有镜像:"
    docker images
    echo ""
    echo "2. 找到刚导入的镜像（可能显示为<none>），复制其IMAGE ID"
    echo "3. 手动添加标签:"
    echo "   docker tag <IMAGE_ID> {expected_name}"
    echo ""
    echo "或者，如果镜像已经正确导入并显示为 {expected_name}，则无需任何操作。"
    exit 1
fi

echo ""
echo "处理镜像: $IMAGE_ID"

# 检查镜像是否已经有正确的标签
EXISTING_TAG=$(docker images --format "{{{{.Repository}}}}:{{{{.Tag}}}}" --filter "reference={expected_name}" 2>/dev/null)

if [ "$EXISTING_TAG" = "{expected_name}" ]; then
    echo "✅ 镜像已经有正确的标签: {expected_name}"
    echo "无需进行标记操作。"
else
    # 需要添加标签
    if echo "$IMAGE_ID" | grep -q "^sha256:"; then
        # 这是一个完整的镜像ID
        echo "为镜像ID添加标签: $IMAGE_ID -> {expected_name}"
        if docker tag "$IMAGE_ID" "{expected_name}"; then
            echo "✅ 标记成功!"
        else
            echo "❌ 标记失败，请手动执行: docker tag $IMAGE_ID {expected_name}"
            exit 1
        fi
    elif [ -n "$IMAGE_ID" ]; then
        # 这可能是一个短ID或镜像名
        echo "为镜像添加标签: $IMAGE_ID -> {expected_name}"
        if docker tag "$IMAGE_ID" "{expected_name}"; then
            echo "✅ 标记成功!"
        else
            echo "❌ 标记失败，请手动执行: docker tag $IMAGE_ID {expected_name}"
            exit 1
        fi
    fi
fi

echo ""
echo "✅ 镜像处理完成!"
echo "验证结果:"
docker images | grep "{final_image_name}" || echo "未找到匹配的镜像，请检查上面的输出"
echo ""
echo "📋 总结:"
echo "- 源文件: {filename}"
echo "- 目标镜像: {expected_name}"
echo "- 状态: 已完成"
"""
                        
                        try:
                            with open(script_path, 'w', encoding='utf-8') as f:
                                f.write(tag_script_content)
                            os.chmod(script_path, 0o755)  # 设置可执行权限
                            
                            self.emit_log(task_id, f"   📝 已生成标记脚本: {script_name}", "success")
                            self.emit_log(task_id, f"   使用方法: bash {script_name}", "info")
                        except Exception as e:
                            self.emit_log(task_id, f"   ⚠️ 生成标记脚本失败: {e}", "warning")
                        
                        return download_url
                    else:
                        self.emit_log(task_id, f"❌ 导出的文件不存在: {file_path}", "error")
                        return False
                else:
                    self.emit_log(task_id, f"skopeo导出命令失败，返回码: {process.returncode}", "error")
                    return False
                    
            except subprocess.TimeoutExpired:
                process.kill()
                self.emit_log(task_id, f"镜像导出超时({timeout_seconds}秒)，请检查网络连接", "error")
                return False
        
        except Exception as e:
            self.emit_log(task_id, f"导出镜像 {source_image} 时发生异常: {str(e)}", "error")
            import traceback
            self.emit_log(task_id, f"异常详情: {traceback.format_exc()}", "error")
            return False

# 初始化组件
registry_config = RegistryConfig()
image_syncer = ImageSyncer(registry_config)

# 认证相关路由
@app.route('/login')
def login():
    """登录页面"""
    if user_manager.is_session_valid(session):
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """登录API"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        
        # 获取客户端IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', ''))
        
        # 验证用户
        success, message = user_manager.authenticate(username, password, client_ip)
        
        if success:
            # 设置会话
            session['username'] = username
            session['login_time'] = datetime.now().isoformat()
            session['user_agent'] = request.headers.get('User-Agent', '')
            session['client_ip'] = client_ip
            
            if remember_me:
                session_config = user_manager.config.get('session', {})
                remember_duration = session_config.get('remember_me_duration', 604800)
                session.permanent = True
                app.permanent_session_lifetime = timedelta(seconds=remember_duration)
            
            user = user_manager.get_user(username)
            logger.info(f"用户 {username} 登录成功，IP: {client_ip}")
            
            return jsonify({
                'success': True,
                'message': message,
                'user': {
                    'username': user['username'],
                    'display_name': user.get('display_name', username),
                    'role': user.get('role', 'user')
                }
            })
        else:
            logger.warning(f"用户 {username} 登录失败: {message}, IP: {client_ip}")
            return jsonify({'error': message}), 401
    
    except Exception as e:
        logger.error(f"登录处理异常: {e}")
        return jsonify({'error': '登录处理失败'}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """登出API"""
    username = session.get('username')
    if username:
        logger.info(f"用户 {username} 登出")
    
    session.clear()
    return jsonify({'success': True, 'message': '已成功登出'})

@app.route('/api/user/info')
@login_required
def get_user_info():
    """获取当前用户信息"""
    username = session.get('username')
    user = user_manager.get_user(username)
    
    if user:
        return jsonify({
            'username': user['username'],
            'display_name': user.get('display_name', username),
            'role': user.get('role', 'user'),
            'email': user.get('email', ''),
            'last_login': user.get('last_login'),
            'login_time': session.get('login_time')
        })
    else:
        return jsonify({'error': '用户不存在'}), 404

@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    try:
        data = request.get_json()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return jsonify({'error': '旧密码和新密码不能为空'}), 400
        
        username = session.get('username')
        user = user_manager.get_user(username)
        
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        # 验证旧密码
        if not user_manager.verify_password(old_password, user['password_hash']):
            return jsonify({'error': '当前密码不正确'}), 401
        
        # 检查新密码长度
        security_config = user_manager.config.get('security', {})
        min_length = security_config.get('password_min_length', 6)
        
        if len(new_password) < min_length:
            return jsonify({'error': f'新密码长度至少{min_length}个字符'}), 400
        
        # 更新密码
        new_password_hash = user_manager.hash_password(new_password)
        user_manager.config['users'][username]['password_hash'] = new_password_hash
        
        # 保存配置
        try:
            with open(user_manager.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(user_manager.config, f, allow_unicode=True, default_flow_style=False)
            
            logger.info(f"用户 {username} 修改密码成功")
            return jsonify({'success': True, 'message': '密码修改成功'})
        
        except Exception as e:
            logger.error(f"保存用户配置失败: {e}")
            return jsonify({'error': '密码修改失败，请重试'}), 500
    
    except Exception as e:
        logger.error(f"修改密码异常: {e}")
        return jsonify({'error': '服务器内部错误'}), 500

@app.route('/')
@login_required
def index():
    """主页"""
    return render_template('index.html')

@app.route('/debug.html')
@login_required
def debug():
    """调试页面"""
    return render_template('debug.html')

@app.route('/demo.html')
@login_required
def demo():
    """演示页面"""
    return render_template('demo.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    """管理员控制面板"""
    return render_template('admin/dashboard.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    """用户管理页面"""
    return render_template('admin/users.html')

@app.route('/admin/registries')
@admin_required
def admin_registries():
    """仓库管理页面"""
    return render_template('admin/registries.html')

@app.route('/api/registries')
@login_required
def get_registries():
    """获取私服列表"""
    return jsonify(registry_config.registries)

@app.route('/api/sync', methods=['POST'])
@login_required
def start_sync():
    """开始同步镜像"""
    try:
        data = request.get_json()
        images = data.get('images', [])
        target_registry = data.get('target_registry')
        target_project = data.get('target_project', '').strip()  # 目标项目/命名空间
        replace_level = data.get('replace_level', '1')
        source_auth = data.get('source_auth')  # 源仓库认证信息
        proxy_config = data.get('proxy_config')  # 代理配置
        
        if not images:
            return jsonify({'error': '镜像列表不能为空'}), 400
        if not target_registry:
            return jsonify({'error': '目标私服不能为空'}), 400
        
        # 生成任务ID
        task_id = f"sync_{int(time.time())}"
        
        # 记录操作日志
        username = session.get('username')
        project_info = f" (项目: {target_project})" if target_project else " (使用默认项目)"
        logger.info(f"用户 {username} 启动同步任务 {task_id}: {len(images)}个镜像 -> {target_registry}{project_info}")
        
        # 启动同步任务
        thread = threading.Thread(
            target=image_syncer.sync_images,
            args=(task_id, images, target_registry, replace_level, source_auth, proxy_config, target_project)
        )
        thread.start()
        
        return jsonify({'task_id': task_id, 'message': '同步任务已启动'})
    
    except Exception as e:
        logger.error(f"启动同步任务失败: {e}")
        return jsonify({'error': '启动同步任务失败'}), 500

@app.route('/api/task/<task_id>')
@login_required
def get_task_status(task_id):
    """获取任务状态"""
    task = sync_tasks.get(task_id)
    if task:
        return jsonify(task)
    else:
        return jsonify({'error': '任务不存在'}), 404

@app.route('/api/task/<task_id>/cancel', methods=['POST'])
@login_required
def cancel_task(task_id):
    """取消任务"""
    task = sync_tasks.get(task_id)
    if task:
        task['status'] = 'cancelled'
        username = session.get('username')
        logger.info(f"用户 {username} 取消了同步任务 {task_id}")
        return jsonify({'message': '任务已取消'})
    else:
        return jsonify({'error': '任务不存在'}), 404

# 文件下载和管理相关路由
@app.route('/downloads/<filename>')
@login_required
def download_file(filename):
    """下载导出的镜像文件"""
    try:
        downloads_dir = 'downloads'
        file_path = os.path.join(downloads_dir, filename)
        
        # 安全检查：确保文件在downloads目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(downloads_dir)):
            return jsonify({'error': '无效的文件路径'}), 400
        
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 记录下载日志
        username = session.get('username')
        logger.info(f"用户 {username} 下载文件: {filename}")
        
        # 返回文件
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/x-tar'
        )
    
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        return jsonify({'error': '下载失败'}), 500

@app.route('/api/files')
@login_required
def list_files():
    """获取下载文件列表"""
    try:
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            return jsonify([])
        
        files = []
        scripts = {}  # 用于存储对应的脚本文件
        
        # 首先收集所有脚本文件
        for filename in os.listdir(downloads_dir):
            if filename.startswith('tag_') and filename.endswith('.sh'):
                # 提取对应的tar文件名
                # tag_镜像名_时间戳.sh -> 镜像名_时间戳.tar
                script_base = filename[4:-3]  # 去掉 'tag_' 前缀和 '.sh' 后缀
                tar_filename = f"{script_base}.tar"
                scripts[tar_filename] = filename
        
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('.tar'):
                stat = os.stat(file_path)
                file_info = {
                    'name': filename,
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'download_url': f'/downloads/{filename}',
                    'type': 'tar'
                }
                
                # 检查是否有对应的标记脚本
                if filename in scripts:
                    script_filename = scripts[filename]
                    script_path = os.path.join(downloads_dir, script_filename)
                    if os.path.exists(script_path):
                        file_info['script'] = {
                            'name': script_filename,
                            'download_url': f'/downloads/{script_filename}',
                            'size': os.path.getsize(script_path)
                        }
                
                files.append(file_info)
        
        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return jsonify(files)
    
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        return jsonify({'error': '获取文件列表失败'}), 500

@app.route('/api/files/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    """删除下载文件"""
    try:
        downloads_dir = 'downloads'
        file_path = os.path.join(downloads_dir, filename)
        
        # 安全检查：确保文件在downloads目录内
        if not os.path.abspath(file_path).startswith(os.path.abspath(downloads_dir)):
            return jsonify({'error': '无效的文件路径'}), 400
        
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 删除文件
        os.remove(file_path)
        
        # 记录删除日志
        username = session.get('username')
        logger.info(f"用户 {username} 删除文件: {filename}")
        
        return jsonify({'message': '文件删除成功'})
    
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        return jsonify({'error': '删除失败'}), 500

@app.route('/api/files/cleanup', methods=['POST'])
@login_required
def cleanup_files():
    """清理下载文件"""
    try:
        data = request.get_json() or {}
        max_age_days = data.get('max_age_days', 7)  # 默认清理7天前的文件
        max_files = data.get('max_files', 50)  # 默认最多保留50个文件
        
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            return jsonify({'deleted_count': 0, 'message': '下载目录不存在'})
        
        files = []
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('.tar'):
                stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'path': file_path,
                    'mtime': stat.st_mtime
                })
        
        deleted_count = 0
        current_time = time.time()
        
        # 删除超过指定天数的文件
        for file_info in files[:]:
            age_days = (current_time - file_info['mtime']) / (24 * 3600)
            if age_days > max_age_days:
                os.remove(file_info['path'])
                files.remove(file_info)
                deleted_count += 1
        
        # 如果文件数量仍然超过限制，删除最旧的文件
        if len(files) > max_files:
            files.sort(key=lambda x: x['mtime'])
            files_to_delete = files[:len(files) - max_files]
            for file_info in files_to_delete:
                os.remove(file_info['path'])
                deleted_count += 1
        
        # 记录清理日志
        username = session.get('username')
        logger.info(f"用户 {username} 清理了 {deleted_count} 个文件")
        
        return jsonify({
            'deleted_count': deleted_count,
            'message': f'清理完成，删除了 {deleted_count} 个文件'
        })
    
    except Exception as e:
        logger.error(f"清理文件失败: {e}")
        return jsonify({'error': '清理失败'}), 500

@app.route('/api/files/batch-download', methods=['POST'])
@login_required
def batch_download_files():
    """批量下载文件（打包为zip）"""
    try:
        data = request.get_json()
        filenames = data.get('filenames', [])
        target_registry = data.get('target_registry', '')  # 新增：目标仓库
        
        if not filenames:
            return jsonify({'error': '文件列表不能为空'}), 400
        
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            return jsonify({'error': '下载目录不存在'}), 404
        
        # 验证所有文件都存在
        missing_files = []
        valid_files = []
        
        for filename in filenames:
            file_path = os.path.join(downloads_dir, filename)
            # 安全检查：确保文件在downloads目录内
            if not os.path.abspath(file_path).startswith(os.path.abspath(downloads_dir)):
                continue
            
            if os.path.exists(file_path):
                valid_files.append((filename, file_path))
            else:
                missing_files.append(filename)
        
        if not valid_files:
            return jsonify({'error': '没有找到有效的文件'}), 404
        
        # 检查磁盘空间 - 计算总文件大小
        total_size = sum(os.path.getsize(file_path) for _, file_path in valid_files)
        available_space = os.statvfs(downloads_dir).f_frsize * os.statvfs(downloads_dir).f_bavail
        
        if total_size * 1.5 > available_space:  # 预留50%空间用于压缩
            return jsonify({
                'error': f'磁盘空间不足。需要约 {total_size * 1.5 / (1024*1024):.1f} MB，可用 {available_space / (1024*1024):.1f} MB'
            }), 507  # HTTP 507 Insufficient Storage
        
        # 创建临时zip文件
        # 生成唯一的zip文件名
        zip_filename = f"batch_download_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(downloads_dir, zip_filename)
        
        # 生成批量推送脚本
        script_filename = f"batch_push_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sh"
        script_path = os.path.join(downloads_dir, script_filename)
        
        try:
            # 创建zip文件，使用流式压缩避免内存溢出和超时
            logger.info(f"开始创建ZIP文件: {zip_filename}，包含 {len(valid_files)} 个文件，总大小: {total_size / (1024*1024):.2f} MB")
            
            # 设置最低压缩级别以提高速度
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
                for i, (filename, file_path) in enumerate(valid_files):
                    try:
                        # 检查文件是否仍然存在
                        if not os.path.exists(file_path):
                            logger.warning(f"文件在压缩过程中被删除: {filename}")
                            continue
                        
                        # 获取文件大小用于进度计算
                        file_size = os.path.getsize(file_path)
                        logger.info(f"正在压缩文件 ({i+1}/{len(valid_files)}): {filename} ({file_size / (1024*1024):.2f} MB)")
                        
                        # 使用流式方式添加大文件，避免内存溢出
                        if file_size > 100 * 1024 * 1024:  # 大于100MB的文件使用流式处理
                            # 手动添加ZIP文件头
                            info = zipfile.ZipInfo(filename)
                            info.file_size = file_size
                            info.compress_type = zipfile.ZIP_DEFLATED
                            
                            with zipf.open(info, 'w') as zf, open(file_path, 'rb') as src:
                                # 分块写入，每次1MB
                                chunk_size = 1024 * 1024
                                while True:
                                    chunk = src.read(chunk_size)
                                    if not chunk:
                                        break
                                    zf.write(chunk)
                        else:
                            # 小文件直接添加
                            zipf.write(file_path, filename)
                        
                        logger.debug(f"已添加文件到ZIP: {filename}")
                        
                        # 定期检查是否应该停止（例如，如果有其他信号）
                        # 这里可以添加中断检查逻辑
                        
                    except Exception as file_error:
                        logger.error(f"添加文件 {filename} 到ZIP时出错: {file_error}")
                        # 继续处理其他文件，不中断整个过程
                        continue
            
            # 验证zip文件是否创建成功
            if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                raise Exception("ZIP文件创建失败或为空")
            
            zip_size = os.path.getsize(zip_path)
            compression_ratio = (1 - zip_size / total_size) * 100 if total_size > 0 else 0
            logger.info(f"ZIP文件创建成功: {zip_filename}，大小: {zip_size / (1024*1024):.2f} MB，压缩率: {compression_ratio:.1f}%")
            
            # 生成批量推送脚本
            script_content = generate_batch_push_script(valid_files, target_registry)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)  # 设置可执行权限
            
            # 记录操作日志
            username = session.get('username')
            logger.info(f"用户 {username} 创建批量下载文件: {zip_filename}, 包含 {len(valid_files)} 个文件")
            if target_registry:
                logger.info(f"用户 {username} 生成批量推送脚本: {script_filename}, 目标仓库: {target_registry}")
            
            # 返回下载信息
            result = {
                'zip_filename': zip_filename,
                'download_url': f'/downloads/{zip_filename}',
                'zip_size': zip_size,
                'zip_size_mb': round(zip_size / (1024*1024), 2),
                'original_size_mb': round(total_size / (1024*1024), 2),
                'compression_ratio': round(compression_ratio, 1),
                'included_files': [f[0] for f in valid_files],
                'file_count': len(valid_files),
                'script': {
                    'filename': script_filename,
                    'download_url': f'/downloads/{script_filename}',
                    'target_registry': target_registry
                }
            }
            
            if missing_files:
                result['missing_files'] = missing_files
                result['warning'] = f'有 {len(missing_files)} 个文件未找到，已跳过'
            
            return jsonify(result)
            
        except zipfile.BadZipFile as zip_error:
            logger.error(f"ZIP文件格式错误: {zip_error}")
            # 清理失败的文件
            for cleanup_file in [zip_path, script_path]:
                if os.path.exists(cleanup_file):
                    try:
                        os.remove(cleanup_file)
                    except:
                        pass
            return jsonify({'error': '创建压缩包时出现格式错误，请重试'}), 500
            
        except OSError as os_error:
            logger.error(f"文件系统错误: {os_error}")
            # 清理失败的文件
            for cleanup_file in [zip_path, script_path]:
                if os.path.exists(cleanup_file):
                    try:
                        os.remove(cleanup_file)
                    except:
                        pass
            return jsonify({'error': f'文件系统错误: {str(os_error)}'}), 507
            
        except Exception as e:
            logger.error(f"创建ZIP过程中的未知错误: {e}")
            # 清理失败的文件
            for cleanup_file in [zip_path, script_path]:
                if os.path.exists(cleanup_file):
                    try:
                        os.remove(cleanup_file)
                    except:
                        pass
            raise e
    
    except Exception as e:
        logger.error(f"批量下载失败: {e}")
        return jsonify({'error': f'批量下载失败: {str(e)}'}), 500

def generate_batch_push_script(valid_files, target_registry):
    """生成批量推送脚本"""
    script_content = f"""#!/bin/bash
# 批量镜像加载和推送脚本 - 自动生成
# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 文件数量: {len(valid_files)}
{'# 目标仓库: ' + target_registry if target_registry else '# 目标仓库: 请手动指定'}

set -e  # 遇到错误时退出

# 颜色输出函数
print_info() {{
    echo -e "\\033[34m[INFO]\\033[0m $1"
}}

print_success() {{
    echo -e "\\033[32m[SUCCESS]\\033[0m $1"
}}

print_error() {{
    echo -e "\\033[31m[ERROR]\\033[0m $1"
}}

print_warning() {{
    echo -e "\\033[33m[WARNING]\\033[0m $1"
}}

# 脚本参数说明
usage() {{
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -r, --registry <registry>    目标仓库地址 (例如: harbor.example.com)"
    echo "  -n, --namespace <namespace>  目标命名空间 (例如: library)"
    echo "  -u, --username <username>    仓库用户名"
    echo "  -p, --password <password>    仓库密码"
    echo "  --no-push                    只加载和标记，不推送"
    echo "  --dry-run                    模拟运行，不实际执行"
    echo "  -h, --help                   显示此帮助信息"
    echo ""
    echo "使用模式:"
    echo "  1. 命令行参数模式 (推荐用于自动化脚本):"
    echo "     $0 -r harbor.example.com -n library -u admin -p password"
    echo ""
    echo "  2. 交互式输入模式 (推荐用于手动操作):"
    echo "     $0"
    echo "     # 脚本会引导您输入目标仓库地址和认证信息"
    echo ""
    echo "  3. 仅加载模式 (不推送到远程仓库):"
    echo "     $0 --no-push"
    echo ""
    echo "示例:"
    echo "  $0 -r registry.cn-hangzhou.aliyuncs.com -n mynamespace -u myuser -p mypass"
    echo "  $0 --dry-run  # 模拟运行，查看将要执行的操作"
    echo "  $0 --no-push  # 只加载镜像到本地，不推送"
}}

# 默认参数
TARGET_REGISTRY="{target_registry if target_registry else ''}"
TARGET_NAMESPACE="library"
USERNAME=""
PASSWORD=""
NO_PUSH=false
DRY_RUN=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            TARGET_REGISTRY="$2"
            shift 2
            ;;
        -n|--namespace)
            TARGET_NAMESPACE="$2"
            shift 2
            ;;
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -p|--password)
            PASSWORD="$2"
            shift 2
            ;;
        --no-push)
            NO_PUSH=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            usage
            exit 1
            ;;
    esac
done

# 交互式输入目标仓库（如果未通过参数指定且需要推送）
if [[ -z "$TARGET_REGISTRY" ]] && [[ "$NO_PUSH" == "false" ]]; then
    echo ""
    print_info "=== 目标仓库配置 ==="
    echo "当前未指定目标仓库地址，请选择一种方式："
    echo ""
    echo "1. 输入目标仓库地址"
    echo "2. 仅加载镜像，不推送到远程仓库"
    echo ""
    
    while true; do
        read -p "请选择 (1-2): " choice
        case $choice in
            1)
                echo ""
                read -p "请输入目标仓库地址 (例如: harbor.example.com): " TARGET_REGISTRY
                if [[ -n "$TARGET_REGISTRY" ]]; then
                    print_success "目标仓库已设置为: $TARGET_REGISTRY"
                    
                    # 询问是否需要输入认证信息
                    echo ""
                    read -p "是否需要输入认证信息? (y/N): " need_auth
                    if [[ "$need_auth" =~ ^[Yy] ]]; then
                        read -p "用户名: " USERNAME
                        read -s -p "密码: " PASSWORD
                        echo ""
                        print_info "认证信息已设置"
                    fi
                    
                    # 询问命名空间
                    echo ""
                    read -p "请输入目标命名空间 (默认: library): " input_namespace
                    if [[ -n "$input_namespace" ]]; then
                        TARGET_NAMESPACE="$input_namespace"
                    fi
                    
                    break
                else
                    print_error "仓库地址不能为空，请重新输入"
                fi
                ;;
            2)
                NO_PUSH=true
                print_info "已设置为仅加载模式，不会推送到远程仓库"
                break
                ;;
            *)
                print_error "无效选择，请输入 1 或 2"
                ;;
        esac
    done
    echo ""
fi

# 验证必需参数（更新后的逻辑）
if [[ -z "$TARGET_REGISTRY" ]] && [[ "$NO_PUSH" == "false" ]]; then
    print_error "请通过 -r 参数指定目标仓库地址，或使用 --no-push 参数仅加载镜像"
    usage
    exit 1
fi

# 显示配置信息
print_info "=== 批量镜像处理配置 ==="
print_info "目标仓库: ${{TARGET_REGISTRY:-'未指定'}}"
print_info "命名空间: $TARGET_NAMESPACE"
print_info "用户名: ${{USERNAME:-'未指定'}}"
if [[ "$NO_PUSH" == "true" ]]; then
    print_info "推送模式: 仅加载标记"
else
    print_info "推送模式: 加载标记并推送"
fi
if [[ "$DRY_RUN" == "true" ]]; then
    print_info "执行模式: 模拟运行"
else
    print_info "执行模式: 实际执行"
fi
print_info "文件数量: {len(valid_files)}"
echo ""

# 检查Docker命令
if ! command -v docker &> /dev/null; then
    print_error "Docker命令未找到，请确保Docker已安装并在PATH中"
    exit 1
fi

# 登录到目标仓库（如果需要）
if [[ "$NO_PUSH" == "false" ]] && [[ -n "$USERNAME" ]] && [[ -n "$PASSWORD" ]]; then
    print_info "正在登录到目标仓库..."
    if [[ "$DRY_RUN" == "false" ]]; then
        if echo "$PASSWORD" | docker login "$TARGET_REGISTRY" -u "$USERNAME" --password-stdin; then
            print_success "登录成功"
        else
            print_error "登录失败"
            exit 1
        fi
    else
        print_info "[模拟] docker login $TARGET_REGISTRY -u $USERNAME"
    fi
    echo ""
fi

# 处理每个镜像文件
PROCESSED=0
FAILED=0

"""

    # 为每个文件生成处理代码
    for filename, file_path in valid_files:
        # 提取镜像名称和标签
        base_name = filename.replace('.tar', '')
        
        script_content += f"""
# 处理文件: {filename}
print_info "处理文件: {filename}"

if [[ ! -f "{filename}" ]]; then
    print_error "文件不存在: {filename}"
    ((FAILED++)) || true
else
    # 加载镜像
    print_info "  正在加载镜像..."
    if [[ "$DRY_RUN" == "false" ]]; then
        LOAD_OUTPUT=$(docker load < "{filename}" 2>&1)
        if [[ $? -eq 0 ]]; then
            print_success "  镜像加载成功"
            echo "    $LOAD_OUTPUT"
            
            # 提取镜像ID或名称
            if echo "$LOAD_OUTPUT" | grep -q "Loaded image:"; then
                IMAGE_REF=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image: \\(.*\\)/\\1/p')
                print_info "  检测到镜像: $IMAGE_REF"
            elif echo "$LOAD_OUTPUT" | grep -q "Loaded image ID:"; then
                IMAGE_ID=$(echo "$LOAD_OUTPUT" | sed -n 's/.*Loaded image ID: sha256:\\([a-f0-9]*\\).*/\\1/p')
                IMAGE_REF="sha256:$IMAGE_ID"
                print_info "  检测到镜像ID: $IMAGE_REF"
            else
                print_warning "  无法自动检测镜像信息，使用文件名推测"
                IMAGE_REF="{base_name}"
            fi
            
            # 构建目标镜像名称 - 改进的名称清理逻辑
            if [[ -n "$TARGET_REGISTRY" ]]; then
                # 从文件名中提取原始镜像名称，去除时间戳
                # 支持格式: redis_20250524_185515.tar -> redis:latest
                # 支持格式: nginx_1.21_20250524_185515.tar -> nginx:1.21
                FILENAME_BASE=$(basename "{filename}" .tar)
                
                # 使用更精确的正则表达式去除时间戳
                # 匹配模式: 镜像名_版本号_日期_时间 或 镜像名_日期_时间
                if [[ "$FILENAME_BASE" =~ ^(.+)_([0-9]{{8}}_[0-9]{{6}})$ ]]; then
                    # 去除时间戳部分
                    CLEAN_NAME="${{BASH_REMATCH[1]}}"
                    print_info "  提取的镜像名: $CLEAN_NAME"
                    
                    # 处理镜像名称中的版本标签
                    # 如果镜像名包含下划线，将最后一个下划线替换为冒号（作为标签分隔符）
                    if [[ "$CLEAN_NAME" == *"_"* ]]; then
                        # 检查是否包含版本号（数字、点、字母等）
                        if [[ "$CLEAN_NAME" =~ ^(.+)_([0-9].*|[a-z].*)$ ]]; then
                            # 可能的版本格式：1.21, v1.0, alpine等
                            CLEAN_NAME="${{BASH_REMATCH[1]}}:${{BASH_REMATCH[2]}}"
                            print_info "  检测到版本标签，格式化为: $CLEAN_NAME"
                        fi
                    fi
                    
                    # 如果没有标签，添加latest
                    if [[ "$CLEAN_NAME" != *":"* ]]; then
                        CLEAN_NAME="$CLEAN_NAME:latest"
                        print_info "  添加默认标签: $CLEAN_NAME"
                    fi
                else
                    # 如果没有匹配到时间戳模式，直接使用文件名
                    CLEAN_NAME="$FILENAME_BASE:latest"
                    print_warning "  未检测到标准时间戳格式，使用文件名: $CLEAN_NAME"
                fi
                
                TARGET_IMAGE="$TARGET_REGISTRY/$TARGET_NAMESPACE/$CLEAN_NAME"
                
                print_info "  目标镜像: $TARGET_IMAGE"
                
                # 重新标记镜像
                if docker tag "$IMAGE_REF" "$TARGET_IMAGE"; then
                    print_success "  镜像标记成功"
                    
                    # 推送镜像（如果需要）
                    if [[ "$NO_PUSH" == "false" ]]; then
                        print_info "  正在推送镜像..."
                        if docker push "$TARGET_IMAGE"; then
                            print_success "  镜像推送成功"
                        else
                            print_error "  镜像推送失败"
                            ((FAILED++)) || true
                        fi
                    fi
                else
                    print_error "  镜像标记失败"
                    ((FAILED++)) || true
                fi
            else
                print_info "  跳过推送（未指定目标仓库）"
            fi
            
            ((PROCESSED++)) || true
        else
            print_error "  镜像加载失败: $LOAD_OUTPUT"
            ((FAILED++)) || true
        fi
    else
        # 模拟运行模式下的名称处理预览
        FILENAME_BASE=$(basename "{filename}" .tar)
        if [[ "$FILENAME_BASE" =~ ^(.+)_([0-9]{{8}}_[0-9]{{6}})$ ]]; then
            CLEAN_NAME="${{BASH_REMATCH[1]}}"
            if [[ "$CLEAN_NAME" == *"_"* ]] && [[ "$CLEAN_NAME" =~ ^(.+)_([0-9].*|[a-z].*)$ ]]; then
                CLEAN_NAME="${{BASH_REMATCH[1]}}:${{BASH_REMATCH[2]}}"
            fi
            if [[ "$CLEAN_NAME" != *":"* ]]; then
                CLEAN_NAME="$CLEAN_NAME:latest"
            fi
        else
            CLEAN_NAME="$FILENAME_BASE:latest"
        fi
        
        print_info "  [模拟] docker load < {filename}"
        print_info "  [模拟] 目标镜像名: $TARGET_REGISTRY/$TARGET_NAMESPACE/$CLEAN_NAME"
        print_info "  [模拟] docker tag ... $TARGET_REGISTRY/$TARGET_NAMESPACE/$CLEAN_NAME"
        if [[ "$NO_PUSH" == "false" ]]; then
            print_info "  [模拟] docker push $TARGET_REGISTRY/$TARGET_NAMESPACE/$CLEAN_NAME"
        fi
        ((PROCESSED++)) || true
    fi
fi

echo ""
"""

    # 添加脚本结尾
    script_content += f"""
# 处理完成总结
print_info "=== 处理完成 ==="
print_success "成功处理: $PROCESSED 个镜像"
if [[ $FAILED -gt 0 ]]; then
    print_error "失败: $FAILED 个镜像"
    exit 1
else
    print_success "所有镜像处理完成！"
fi

# 清理Docker登录信息（如果需要）
if [[ "$NO_PUSH" == "false" ]] && [[ -n "$USERNAME" ]] && [[ "$DRY_RUN" == "false" ]]; then
    print_info "正在登出..."
    docker logout "$TARGET_REGISTRY" 2>/dev/null || true
fi

print_info "脚本执行完成。"
"""

    return script_content

# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    """WebSocket连接"""
    # 检查认证状态
    if not user_manager.is_session_valid(session):
        return False  # 拒绝连接
    
    username = session.get('username')
    logger.info(f"用户 {username} WebSocket连接成功")
    emit('connected', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开连接"""
    username = session.get('username', 'unknown')
    logger.info(f"用户 {username} WebSocket连接断开")

@socketio.on('ping')
def handle_ping():
    """处理心跳ping，返回pong"""
    emit('pong', {'timestamp': time.time()})

# 添加自动清理功能
def auto_cleanup_downloads():
    """自动清理下载目录中的旧文件"""
    try:
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            logger.debug("下载目录不存在，跳过自动清理")
            return
        
        # 从环境变量读取配置
        max_age_hours = int(os.getenv('MAX_FILE_AGE', 24))  # 默认24小时
        current_time = time.time()
        cleanup_count = 0
        
        logger.info(f"开始自动清理下载目录中的旧文件... (保留{max_age_hours}小时内的文件)")
        
        # 获取所有文件
        files_to_process = []
        try:
            for filename in os.listdir(downloads_dir):
                file_path = os.path.join(downloads_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        file_age_hours = (current_time - file_mtime) / 3600
                        files_to_process.append((filename, file_path, file_age_hours))
                    except OSError as e:
                        logger.warning(f"无法获取文件 {filename} 的修改时间: {e}")
                        continue
        except Exception as e:
            logger.error(f"无法读取下载目录: {e}")
            return 0
        
        logger.info(f"发现 {len(files_to_process)} 个文件待检查")
        
        # 按文件年龄排序
        files_to_process.sort(key=lambda x: x[2], reverse=True)  # 最老的文件在前
        
        # 清理超过指定时间的文件
        for filename, file_path, file_age_hours in files_to_process:
            if file_age_hours > max_age_hours:
                try:
                    # 安全检查：确保文件在downloads目录内
                    if not os.path.abspath(file_path).startswith(os.path.abspath(downloads_dir)):
                        logger.warning(f"跳过不安全的文件路径: {file_path}")
                        continue
                    
                    os.remove(file_path)
                    cleanup_count += 1
                    logger.debug(f"已删除过期文件: {filename} (已存在{file_age_hours:.1f}小时)")
                    
                except Exception as e:
                    logger.warning(f"删除文件 {filename} 失败: {e}")
        
        # 始终输出清理结果
        logger.info(f"自动清理完成，删除了 {cleanup_count} 个过期文件")
            
        # 检查剩余文件数量，如果太多则保留最新的100个
        remaining_files = []
        try:
            for filename in os.listdir(downloads_dir):
                file_path = os.path.join(downloads_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        remaining_files.append((filename, file_path, file_mtime))
                    except OSError:
                        continue
        except Exception as e:
            logger.warning(f"检查剩余文件时出错: {e}")
        
        # 如果剩余文件超过100个，删除最旧的
        max_files = 100
        if len(remaining_files) > max_files:
            logger.info(f"发现 {len(remaining_files)} 个文件超过最大保留数量 {max_files}，开始清理多余文件")
            remaining_files.sort(key=lambda x: x[2])  # 按时间排序，最旧在前
            files_to_delete = remaining_files[:len(remaining_files) - max_files]
            
            extra_cleanup_count = 0
            for filename, file_path, _ in files_to_delete:
                try:
                    os.remove(file_path)
                    extra_cleanup_count += 1
                    logger.debug(f"已删除多余文件: {filename}")
                except Exception as e:
                    logger.warning(f"删除多余文件 {filename} 失败: {e}")
            
            if extra_cleanup_count > 0:
                logger.info(f"额外清理了 {extra_cleanup_count} 个多余文件，保留最新的 {max_files} 个")
                cleanup_count += extra_cleanup_count
        
        return cleanup_count
            
    except Exception as e:
        logger.error(f"自动清理过程中发生错误: {e}")
        return 0

def start_cleanup_scheduler():
    """启动定时清理任务"""
    cleanup_interval = int(os.getenv('CLEANUP_INTERVAL', 6))  # 默认6小时
    max_age_hours = int(os.getenv('MAX_FILE_AGE', 24))  # 默认24小时
    schedule.every(cleanup_interval).hours.do(auto_cleanup_downloads)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # 启动时立即执行一次清理
    def initial_cleanup():
        try:
            cleanup_count = auto_cleanup_downloads()
            logger.info(f"启动时清理完成，删除了 {cleanup_count} 个文件")
        except Exception as e:
            logger.error(f"启动时清理失败: {e}")
    
    initial_cleanup_thread = threading.Thread(target=initial_cleanup, daemon=True)
    initial_cleanup_thread.start()
    
    logger.info(f"下载目录自动清理调度器已启动 (每{cleanup_interval}小时运行一次，保留{max_age_hours}小时内文件)")

# 手动清理API
@app.route('/api/files/auto-cleanup', methods=['POST'])
@login_required
def manual_auto_cleanup():
    """手动触发自动清理"""
    try:
        # 在后台线程中执行清理
        def cleanup_task():
            try:
                cleanup_count = auto_cleanup_downloads()
                logger.info(f"手动清理完成，删除了 {cleanup_count} 个文件")
            except Exception as e:
                logger.error(f"手动清理失败: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_task)
        cleanup_thread.start()
        
        username = session.get('username')
        logger.info(f"用户 {username} 手动触发了自动清理")
        
        return jsonify({
            'success': True, 
            'message': '自动清理已在后台启动，请稍后查看日志'
        })
    
    except Exception as e:
        logger.error(f"手动清理失败: {e}")
        return jsonify({'error': f'清理失败: {str(e)}'}), 500

# === 管理员API接口 ===

@app.route('/api/admin/users')
@admin_required
def get_all_users():
    """获取所有用户列表"""
    try:
        users = []
        for username, user_data in user_manager.config.get('users', {}).items():
            user_info = {
                'username': user_data['username'],
                'display_name': user_data.get('display_name', username),
                'role': user_data.get('role', 'user'),
                'email': user_data.get('email', ''),
                'active': user_data.get('active', True),
                'created_at': user_data.get('created_at', ''),
                'last_login': user_data.get('last_login', '')
            }
            users.append(user_info)
        
        return jsonify(users)
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return jsonify({'error': '获取用户列表失败'}), 500

@app.route('/api/admin/users', methods=['POST'])
@admin_required
def create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', 'user')
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
        
        if username in user_manager.config.get('users', {}):
            return jsonify({'error': '用户名已存在'}), 400
        
        # 验证密码长度
        security_config = user_manager.config.get('security', {})
        min_length = security_config.get('password_min_length', 6)
        if len(password) < min_length:
            return jsonify({'error': f'密码长度至少{min_length}个字符'}), 400
        
        # 创建用户
        user_data = {
            'username': username,
            'password_hash': user_manager.hash_password(password),
            'display_name': display_name or username,
            'email': email,
            'role': role if role in ['admin', 'user'] else 'user',
            'active': True,
            'created_at': datetime.now().isoformat()
        }
        
        user_manager.config['users'][username] = user_data
        
        # 保存配置
        with open(user_manager.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(user_manager.config, f, allow_unicode=True, default_flow_style=False)
        
        current_user = session.get('username')
        logger.info(f"管理员 {current_user} 创建了新用户: {username}, 角色: {role}")
        
        return jsonify({'success': True, 'message': '用户创建成功'})
    
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return jsonify({'error': '创建用户失败'}), 500

@app.route('/api/admin/users/<username>', methods=['PUT'])
@admin_required
def update_user(username):
    """更新用户信息"""
    try:
        if username not in user_manager.config.get('users', {}):
            return jsonify({'error': '用户不存在'}), 404
        
        data = request.get_json()
        user_data = user_manager.config['users'][username]
        
        # 更新允许的字段
        if 'display_name' in data:
            user_data['display_name'] = data['display_name'].strip()
        if 'email' in data:
            user_data['email'] = data['email'].strip()
        if 'role' in data and data['role'] in ['admin', 'user']:
            user_data['role'] = data['role']
        if 'active' in data:
            user_data['active'] = bool(data['active'])
        
        # 如果提供了新密码，更新密码
        if data.get('password'):
            security_config = user_manager.config.get('security', {})
            min_length = security_config.get('password_min_length', 6)
            if len(data['password']) < min_length:
                return jsonify({'error': f'密码长度至少{min_length}个字符'}), 400
            user_data['password_hash'] = user_manager.hash_password(data['password'])
        
        # 保存配置
        with open(user_manager.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(user_manager.config, f, allow_unicode=True, default_flow_style=False)
        
        current_user = session.get('username')
        logger.info(f"管理员 {current_user} 更新了用户 {username} 的信息")
        
        return jsonify({'success': True, 'message': '用户信息更新成功'})
    
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        return jsonify({'error': '更新用户失败'}), 500

@app.route('/api/admin/users/<username>', methods=['DELETE'])
@admin_required
def delete_user(username):
    """删除用户"""
    try:
        if username not in user_manager.config.get('users', {}):
            return jsonify({'error': '用户不存在'}), 404
        
        current_user = session.get('username')
        if username == current_user:
            return jsonify({'error': '不能删除自己的账户'}), 400
        
        # 删除用户
        del user_manager.config['users'][username]
        
        # 保存配置
        with open(user_manager.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(user_manager.config, f, allow_unicode=True, default_flow_style=False)
        
        logger.info(f"管理员 {current_user} 删除了用户: {username}")
        
        return jsonify({'success': True, 'message': '用户删除成功'})
    
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return jsonify({'error': '删除用户失败'}), 500

@app.route('/api/admin/registries', methods=['GET'])
@admin_required
def get_all_registries():
    """获取所有仓库配置"""
    return jsonify(registry_config.registries)

@app.route('/api/admin/registries', methods=['POST'])
@admin_required
def create_registry():
    """创建新的仓库配置"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'type', 'url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} 字段不能为空'}), 400
        
        # 检查名称是否已存在
        for registry in registry_config.registries:
            if registry['name'] == data['name']:
                return jsonify({'error': '仓库名称已存在'}), 400
        
        # 创建新的仓库配置
        new_registry = {
            'name': data['name'],
            'type': data['type'],
            'url': data['url'],
            'username': data.get('username', ''),
            'password': data.get('password', ''),
            'project': data.get('project', ''),
            'namespace': data.get('namespace', ''),
            'repository': data.get('repository', ''),
            'description': data.get('description', ''),
            'insecure': data.get('insecure', False),
            'active': data.get('active', True)
        }
        
        registry_config.registries.append(new_registry)
        
        # 保存配置
        config_data = {'registries': registry_config.registries}
        with open(registry_config.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        current_user = session.get('username')
        logger.info(f"管理员 {current_user} 创建了新的仓库配置: {data['name']}")
        
        return jsonify({'success': True, 'message': '仓库配置创建成功'})
    
    except Exception as e:
        logger.error(f"创建仓库配置失败: {e}")
        return jsonify({'error': '创建仓库配置失败'}), 500

@app.route('/api/admin/registries/<int:registry_index>', methods=['PUT'])
@admin_required
def update_registry(registry_index):
    """更新仓库配置"""
    try:
        if registry_index >= len(registry_config.registries):
            return jsonify({'error': '仓库配置不存在'}), 404
        
        data = request.get_json()
        
        required_fields = ['name', 'type', 'url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} 字段不能为空'}), 400
        
        # 检查名称是否与其他仓库冲突
        for i, registry in enumerate(registry_config.registries):
            if i != registry_index and registry['name'] == data['name']:
                return jsonify({'error': '仓库名称已存在'}), 400
        
        # 更新仓库配置
        registry_config.registries[registry_index] = {
            'name': data['name'],
            'type': data['type'],
            'url': data['url'],
            'username': data.get('username', ''),
            'password': data.get('password', ''),
            'project': data.get('project', ''),
            'namespace': data.get('namespace', ''),
            'repository': data.get('repository', ''),
            'description': data.get('description', ''),
            'insecure': data.get('insecure', False),
            'active': data.get('active', True)
        }
        
        # 保存配置
        config_data = {'registries': registry_config.registries}
        with open(registry_config.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        current_user = session.get('username')
        logger.info(f"管理员 {current_user} 更新了仓库配置: {data['name']}")
        
        return jsonify({'success': True, 'message': '仓库配置更新成功'})
    
    except Exception as e:
        logger.error(f"更新仓库配置失败: {e}")
        return jsonify({'error': '更新仓库配置失败'}), 500

@app.route('/api/admin/registries/<int:registry_index>', methods=['DELETE'])
@admin_required
def delete_registry(registry_index):
    """删除仓库配置"""
    try:
        if registry_index >= len(registry_config.registries):
            return jsonify({'error': '仓库配置不存在'}), 404
        
        deleted_registry = registry_config.registries.pop(registry_index)
        
        # 保存配置
        config_data = {'registries': registry_config.registries}
        with open(registry_config.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
        
        current_user = session.get('username')
        logger.info(f"管理员 {current_user} 删除了仓库配置: {deleted_registry['name']}")
        
        return jsonify({'success': True, 'message': '仓库配置删除成功'})
    
    except Exception as e:
        logger.error(f"删除仓库配置失败: {e}")
        return jsonify({'error': '删除仓库配置失败'}), 500

@app.route('/health')
def health_check():
    """健康检查端点"""
    try:
        # 检查基本服务状态
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'service': 'docker-image-sync'
        }
        
        # 检查Skopeo工具
        try:
            result = subprocess.run(['skopeo', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                status['skopeo'] = 'available'
                status['skopeo_version'] = result.stdout.strip()
            else:
                status['skopeo'] = 'unavailable'
        except Exception:
            status['skopeo'] = 'unavailable'
        
        # 检查配置文件
        config_status = {}
        config_files = ['config/registries.yaml', 'config/users.yaml']
        for config_file in config_files:
            if os.path.exists(config_file):
                config_status[config_file] = 'exists'
            else:
                config_status[config_file] = 'missing'
        status['config'] = config_status
        
        # 检查目录
        directories = ['logs', 'downloads', 'templates', 'static']
        dir_status = {}
        for directory in directories:
            if os.path.exists(directory):
                dir_status[directory] = 'exists'
            else:
                dir_status[directory] = 'missing'
        status['directories'] = dir_status
        
        # 检查活跃任务
        status['active_tasks'] = len(sync_tasks)
        
        # 检查内存使用（简单检查）
        try:
            memory = psutil.virtual_memory()
            status['memory'] = {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent
            }
        except ImportError:
            status['memory'] = 'psutil not available'
        
        return jsonify(status), 200
        
    except Exception as e:
        error_status = {
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'service': 'docker-image-sync'
        }
        return jsonify(error_status), 500

@app.route('/metrics')
def metrics():
    """Prometheus指标端点"""
    try:
        metrics_data = []
        
        # 基本指标
        metrics_data.append('# HELP docker_sync_info Application info')
        metrics_data.append('# TYPE docker_sync_info gauge')
        metrics_data.append('docker_sync_info{version="1.0.0",service="docker-image-sync"} 1')
        
        # 活跃任务数
        metrics_data.append('# HELP docker_sync_active_tasks Number of active sync tasks')
        metrics_data.append('# TYPE docker_sync_active_tasks gauge')
        metrics_data.append(f'docker_sync_active_tasks {len(sync_tasks)}')
        
        # 用户数量
        user_count = len(user_manager.config.get('users', {}))
        metrics_data.append('# HELP docker_sync_users_total Total number of users')
        metrics_data.append('# TYPE docker_sync_users_total gauge')
        metrics_data.append(f'docker_sync_users_total {user_count}')
        
        # 仓库配置数量
        registry_count = len(registry_config.registries)
        metrics_data.append('# HELP docker_sync_registries_total Total number of configured registries')
        metrics_data.append('# TYPE docker_sync_registries_total gauge')
        metrics_data.append(f'docker_sync_registries_total {registry_count}')
        
        # 下载文件数量
        downloads_dir = 'downloads'
        if os.path.exists(downloads_dir):
            file_count = len([f for f in os.listdir(downloads_dir) if os.path.isfile(os.path.join(downloads_dir, f))])
            metrics_data.append('# HELP docker_sync_download_files_total Total number of download files')
            metrics_data.append('# TYPE docker_sync_download_files_total gauge')
            metrics_data.append(f'docker_sync_download_files_total {file_count}')
        
        # Skopeo状态
        try:
            result = subprocess.run(['skopeo', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            skopeo_status = 1 if result.returncode == 0 else 0
        except Exception:
            skopeo_status = 0
        
        metrics_data.append('# HELP docker_sync_skopeo_available Skopeo tool availability')
        metrics_data.append('# TYPE docker_sync_skopeo_available gauge')
        metrics_data.append(f'docker_sync_skopeo_available {skopeo_status}')
        
        return '\n'.join(metrics_data), 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except Exception as e:
        return f'# Error generating metrics: {str(e)}', 500, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    # 确保配置目录存在
    os.makedirs('config', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)  # 创建下载目录
    
    # 创建默认配置文件
    if not os.path.exists('config/registries.yaml'):
        with open('config/registries.yaml', 'w', encoding='utf-8') as f:
            yaml.dump({
                'registries': registry_config.get_default_config()
            }, f, default_flow_style=False, allow_unicode=True)
    
    # 启动自动清理调度器
    start_cleanup_scheduler()
    
    print("Docker镜像同步服务器启动中...")
    print("访问地址: http://localhost:5000")
    print("功能特性:")
    print("  - 🔐 用户认证系统")
    print("  - 🐳 镜像同步到私服")
    print("  - 📦 导出镜像为tar包")
    print("  - 🌐 网络代理支持")
    print("  - 🔑 私有仓库认证")
    print("  - 📥 批量下载和推送脚本")
    print("  - 🧹 自动清理 (保留1天)")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 