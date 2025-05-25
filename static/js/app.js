// Docker镜像同步工具前端逻辑

// 用户认证管理
class UserAuth {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    async init() {
        await this.loadUserInfo();
    }

    // 加载用户信息
    async loadUserInfo() {
        try {
            const response = await fetch('/api/user/info');
            if (response.ok) {
                this.currentUser = await response.json();
                this.updateUserUI();
            } else if (response.status === 401) {
                // 未登录，重定向到登录页
                window.location.href = '/login';
                return;
            }
        } catch (error) {
            console.error('获取用户信息失败:', error);
            // 网络错误，也重定向到登录页
            window.location.href = '/login';
        }
    }

    // 更新用户界面
    updateUserUI() {
        if (!this.currentUser) return;

        // 更新用户显示名称
        const displayNameElement = document.getElementById('user-display-name');
        if (displayNameElement) {
            displayNameElement.textContent = this.currentUser.display_name || this.currentUser.username;
        }

        // 更新用户角色
        const roleElement = document.getElementById('user-role');
        if (roleElement) {
            roleElement.textContent = this.currentUser.role === 'admin' ? '管理员' : '用户';
            roleElement.className = `badge ${this.currentUser.role === 'admin' ? 'bg-warning' : 'bg-success'} me-2`;
        }

        // 更新登录时间
        const loginTimeElement = document.getElementById('login-time');
        if (loginTimeElement && this.currentUser.login_time) {
            const loginTime = new Date(this.currentUser.login_time);
            loginTimeElement.textContent = loginTime.toLocaleString('zh-CN');
        }

        // 显示/隐藏管理员菜单
        const adminMenuItem = document.getElementById('admin-menu-item');
        const adminDivider = document.getElementById('admin-divider');
        if (this.currentUser.role === 'admin') {
            if (adminMenuItem) adminMenuItem.style.display = '';
            if (adminDivider) adminDivider.style.display = '';
        } else {
            if (adminMenuItem) adminMenuItem.style.display = 'none';
            if (adminDivider) adminDivider.style.display = 'none';
        }
    }

    // 登出
    async logout() {
        try {
            const response = await fetch('/api/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                // 清除用户信息
                this.currentUser = null;
                // 重定向到登录页
                window.location.href = '/login';
            } else {
                throw new Error('登出失败');
            }
        } catch (error) {
            console.error('登出错误:', error);
            // 即使登出失败，也强制跳转到登录页
            window.location.href = '/login';
        }
    }
}

// 全局认证实例
let userAuth;

// 登出函数
function logout() {
    if (confirm('确定要退出登录吗？')) {
        userAuth.logout();
    }
}

// 修改密码函数
function changePassword() {
    // 显示修改密码模态框
    showChangePasswordModal();
}

// 显示修改密码模态框
function showChangePasswordModal() {
    // 创建模态框HTML
    const modalHtml = `
        <div class="modal fade" id="changePasswordModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-key me-2"></i>修改密码
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="changePasswordForm">
                            <div class="mb-3">
                                <label for="oldPassword" class="form-label">当前密码</label>
                                <input type="password" class="form-control" id="oldPassword" required>
                            </div>
                            <div class="mb-3">
                                <label for="newPassword" class="form-label">新密码</label>
                                <input type="password" class="form-control" id="newPassword" required minlength="6">
                                <div class="form-text">密码长度至少6个字符</div>
                            </div>
                            <div class="mb-3">
                                <label for="confirmPassword" class="form-label">确认新密码</label>
                                <input type="password" class="form-control" id="confirmPassword" required>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="submitChangePassword()">
                            <i class="fas fa-save me-1"></i>保存修改
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // 添加模态框到页面
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('changePasswordModal'));
    modal.show();
    
    // 模态框关闭时移除DOM
    document.getElementById('changePasswordModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

// 提交修改密码
async function submitChangePassword() {
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (!oldPassword || !newPassword || !confirmPassword) {
        alert('请填写所有字段');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        alert('新密码和确认密码不匹配');
        return;
    }
    
    if (newPassword.length < 6) {
        alert('新密码长度至少6个字符');
        return;
    }
    
    try {
        const response = await fetch('/api/user/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('密码修改成功');
            bootstrap.Modal.getInstance(document.getElementById('changePasswordModal')).hide();
        } else {
            alert(data.error || '密码修改失败');
        }
    } catch (error) {
        console.error('修改密码错误:', error);
        alert('网络错误，请稍后重试');
    }
}

class DockerSyncApp {
    constructor() {
        this.socket = null;
        this.currentTaskId = null;
        this.hasReceivedWebSocketMessage = false;
        this.pollingInterval = null;
        this.init();
    }

    init() {
        this.initSocket();
        this.bindEvents();
        this.loadRegistries();
    }

    // 初始化WebSocket连接
    initSocket() {
        try {
            this.socket = io();
            
            this.socket.on('connect', () => {
                console.log('WebSocket连接成功');
                this.updateConnectionStatus('connected');
            });

            this.socket.on('disconnect', () => {
                console.log('WebSocket连接断开');
                this.updateConnectionStatus('disconnected');
            });

            this.socket.on('connected', (data) => {
                console.log('服务器响应:', data.message);
            });

            this.socket.on('sync_log', (data) => {
                this.hasReceivedWebSocketMessage = true;
                this.addLogEntry(data.log);
            });

            this.socket.on('sync_progress', (data) => {
                this.hasReceivedWebSocketMessage = true;
                this.updateProgress(data);
            });

        } catch (error) {
            console.error('WebSocket连接失败:', error);
            this.updateConnectionStatus('disconnected');
        }
    }

    // 绑定事件处理器
    bindEvents() {
        // 表单提交
        document.getElementById('sync-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startSync();
        });

        // 终止同步
        document.getElementById('terminate-sync').addEventListener('click', () => {
            this.terminateSync();
        });

        // 清空日志
        document.getElementById('clear-logs').addEventListener('click', () => {
            this.clearLogs();
        });

        // 镜像输入框失焦时格式化
        document.getElementById('images-input').addEventListener('blur', () => {
            this.formatImagesList();
        });

        // 文件管理相关事件
        document.getElementById('refresh-files').addEventListener('click', () => {
            this.loadFilesList();
        });

        document.getElementById('cleanup-files').addEventListener('click', () => {
            this.cleanupFiles();
        });

        // 自动清理按钮
        document.getElementById('auto-cleanup-files').addEventListener('click', () => {
            this.autoCleanupFiles();
        });
    }

    // 更新连接状态
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connection-status');
        statusElement.className = `badge badge-${status}`;
        
        const statusText = {
            'connected': '已连接',
            'connecting': '连接中...',
            'disconnected': '已断开'
        };
        
        statusElement.textContent = statusText[status] || '未知状态';
    }

    // 加载私服列表
    async loadRegistries() {
        try {
            const response = await fetch('/api/registries');
            if (!response.ok) {
                throw new Error('获取私服列表失败');
            }
            
            const registries = await response.json();
            const select = document.getElementById('target-registry');
            
            // 清空现有选项（保留默认选项）
            select.innerHTML = '<option value="">请选择私服...</option>';
            
            // 添加私服选项
            registries.forEach(registry => {
                const option = document.createElement('option');
                option.value = registry.name;
                option.textContent = `${registry.name} (${registry.type}) - ${registry.url}`;
                select.appendChild(option);
            });
            
        } catch (error) {
            console.error('加载私服列表失败:', error);
            this.showError('无法加载私服列表，请检查配置文件');
        }
    }

    // 格式化镜像列表
    formatImagesList() {
        const textarea = document.getElementById('images-input');
        const lines = textarea.value.split('\n');
        
        // 过滤空行并去除多余空格，保留注释行
        const formattedLines = lines
            .map(line => line.trim())
            .filter(line => line.length > 0 || line === ''); // 保留空行用于分组
        
        textarea.value = formattedLines.join('\n');
    }

    // 开始同步
    async startSync() {
        try {
            // 获取表单数据
            const imagesText = document.getElementById('images-input').value.trim();
            const targetRegistry = document.getElementById('target-registry').value;
            const targetProject = document.getElementById('target-project').value.trim(); // 目标项目/命名空间
            const replaceLevel = document.getElementById('replace-level').value;
            
            // 获取私有认证信息
            const usePrivateAuth = document.getElementById('use-private-auth').checked;
            const sourceUsername = document.getElementById('source-username').value.trim();
            const sourcePassword = document.getElementById('source-password').value.trim();

            // 获取代理配置信息
            const useProxy = document.getElementById('use-proxy').checked;
            const proxyHttp = document.getElementById('proxy-http').value.trim();
            const proxyHttps = document.getElementById('proxy-https').value.trim();
            const proxyNoProxy = document.getElementById('proxy-no-proxy').value.trim();

            // 验证输入
            if (!imagesText) {
                this.showError('请输入要同步的镜像列表');
                return;
            }

            if (!targetRegistry) {
                this.showError('请选择目标私服');
                return;
            }

            // 如果勾选了私有认证但未填写完整信息
            if (usePrivateAuth && (!sourceUsername || !sourcePassword)) {
                this.showError('勾选了私有认证选项，请填写完整的用户名和密码');
                return;
            }

            // 如果勾选了代理但未填写代理地址
            if (useProxy && !proxyHttp && !proxyHttps) {
                this.showError('勾选了代理选项，请至少填写HTTP或HTTPS代理地址');
                return;
            }

            // 解析镜像列表
            const images = imagesText.split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0 && !line.startsWith('#')); // 过滤空行和注释行

            if (images.length === 0) {
                this.showError('镜像列表不能为空');
                return;
            }

            // 准备请求数据
            const requestData = {
                images: images,
                target_registry: targetRegistry,
                target_project: targetProject,
                replace_level: replaceLevel || '1',  // 默认为替换1级
                source_auth: usePrivateAuth ? {
                    username: sourceUsername,
                    password: sourcePassword
                } : null,
                proxy_config: useProxy ? {
                    http_proxy: proxyHttp,
                    https_proxy: proxyHttps || proxyHttp, // 如果未填写HTTPS代理，使用HTTP代理
                    no_proxy: proxyNoProxy
                } : null
            };

            // 发送同步请求
            const response = await fetch('/api/sync', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '启动同步任务失败');
            }

            const result = await response.json();
            this.currentTaskId = result.task_id;

            // 更新UI状态
            this.updateSyncUI(true);
            this.clearLogs();
            this.addLogEntry({
                timestamp: new Date().toLocaleString(),
                level: 'info',
                message: `同步任务已启动 (任务ID: ${this.currentTaskId})`
            });

            // 添加目标信息日志
            this.addLogEntry({
                timestamp: new Date().toLocaleString(),
                level: 'info',
                message: `目标私服: ${targetRegistry}${targetProject ? ` | 项目: ${targetProject}` : ' | 使用默认项目'}`
            });

            // 如果使用了私有认证，添加提示日志
            if (usePrivateAuth) {
                this.addLogEntry({
                    timestamp: new Date().toLocaleString(),
                    level: 'info',
                    message: `已配置源仓库认证信息，用户名: ${sourceUsername}`
                });
            }

            // 如果使用了代理，添加提示日志
            if (useProxy) {
                this.addLogEntry({
                    timestamp: new Date().toLocaleString(),
                    level: 'info',
                    message: `已配置网络代理 - HTTP: ${proxyHttp || '未设置'}, HTTPS: ${proxyHttps || proxyHttp || '未设置'}`
                });
            }

            // 检查WebSocket连接状态，如果未连接则启用轮询模式
            if (!this.socket || !this.socket.connected) {
                console.log('WebSocket未连接，启用轮询模式');
                this.addLogEntry({
                    timestamp: new Date().toLocaleString(),
                    level: 'warning',
                    message: 'WebSocket连接异常，切换到轮询模式获取进度'
                });
                this.startStatusPolling();
            } else {
                console.log('WebSocket已连接，使用实时模式');
                // 启动轮询作为备选方案（3秒后检查）
                setTimeout(() => {
                    if (this.currentTaskId && !this.hasReceivedWebSocketMessage) {
                        console.log('WebSocket消息未收到，启动备选轮询');
                        this.addLogEntry({
                            timestamp: new Date().toLocaleString(),
                            level: 'info',
                            message: '启动备选轮询模式获取进度...'
                        });
                        this.startStatusPolling();
                    }
                }, 3000);
            }

        } catch (error) {
            console.error('启动同步失败:', error);
            this.showError(error.message);
        }
    }

    // 终止同步
    async terminateSync() {
        if (!this.currentTaskId) {
            return;
        }

        try {
            const response = await fetch(`/api/task/${this.currentTaskId}/cancel`, {
                method: 'POST'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '终止任务失败');
            }

            const result = await response.json();
            this.addLogEntry({
                timestamp: new Date().toLocaleString(),
                level: 'warning',
                message: result.message || '同步任务已终止'
            });

        } catch (error) {
            console.error('终止同步失败:', error);
            this.showError(error.message);
        }
    }

    // 更新同步UI状态
    updateSyncUI(isRunning) {
        const startBtn = document.getElementById('start-sync');
        const cancelBtn = document.getElementById('terminate-sync');
        const taskStatus = document.getElementById('task-status');
        
        if (isRunning) {
            startBtn.style.display = 'none';
            cancelBtn.style.display = 'block';
            taskStatus.style.display = 'block';
            startBtn.classList.add('pulsing');
        } else {
            startBtn.style.display = 'block';
            cancelBtn.style.display = 'none';
            startBtn.classList.remove('pulsing');
            
            // 延迟隐藏任务状态，让用户能看到最终结果
            setTimeout(() => {
                if (!this.isTaskRunning()) {
                    taskStatus.style.display = 'none';
                }
            }, 5000);
        }
    }

    // 检查任务是否正在运行
    isTaskRunning() {
        // 这里可以添加更复杂的逻辑来检查任务状态
        return document.getElementById('terminate-sync').style.display !== 'none';
    }

    // 更新进度显示
    updateProgress(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const currentImage = document.getElementById('current-image');

        const percentage = data.total > 0 ? (data.progress / data.total * 100) : 0;
        
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
        
        progressText.textContent = `${data.progress} / ${data.total} (${percentage.toFixed(1)}%)`;
        
        if (data.current_image) {
            currentImage.textContent = `当前: ${data.current_image}`;
        }

        // 根据状态更新进度条颜色
        progressBar.className = 'progress-bar progress-bar-striped';
        if (data.status === 'running') {
            progressBar.classList.add('progress-bar-animated', 'bg-primary');
        } else if (data.status === 'completed') {
            progressBar.classList.add('bg-success');
            this.updateSyncUI(false);
        } else if (data.status === 'failed') {
            progressBar.classList.add('bg-danger');
            this.updateSyncUI(false);
        } else if (data.status === 'cancelled') {
            progressBar.classList.add('bg-warning');
            this.updateSyncUI(false);
        }
    }

    // 添加日志条目
    addLogEntry(log) {
        const logContainer = document.getElementById('log-container');
        
        // 如果是第一条日志，清空占位内容
        if (logContainer.children.length === 1 && logContainer.children[0].classList.contains('text-center')) {
            logContainer.innerHTML = '';
        }

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${log.level}`;
        
        logEntry.innerHTML = `
            <span class="log-timestamp">${log.timestamp}</span>
            <span class="log-level ${log.level}">${log.level}</span>
            <span class="log-message">${this.escapeHtml(log.message)}</span>
        `;

        logContainer.appendChild(logEntry);
        
        // 自动滚动到底部
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // 清空日志
    clearLogs() {
        const logContainer = document.getElementById('log-container');
        logContainer.innerHTML = `
            <div class="text-center text-muted p-4">
                <i class="fas fa-info-circle"></i>
                等待开始同步任务...
            </div>
        `;
    }

    // 显示错误信息
    showError(message) {
        const errorModal = document.getElementById('errorModal');
        const errorMessage = document.getElementById('error-message');
        
        errorMessage.textContent = message;
        
        // 使用Bootstrap的Modal API
        if (window.bootstrap && window.bootstrap.Modal) {
            const modal = new bootstrap.Modal(errorModal);
            modal.show();
        } else {
            // 备用方案：使用jQuery Modal（如果Bootstrap 4）
            if (window.$ && window.$.fn.modal) {
                $(errorModal).modal('show');
            } else {
                // 最后备用方案：使用alert
                alert('错误: ' + message);
            }
        }
    }

    // HTML转义
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 获取任务状态
    async getTaskStatus(taskId) {
        try {
            const response = await fetch(`/api/task/${taskId}`);
            if (!response.ok) {
                throw new Error('获取任务状态失败');
            }
            return await response.json();
        } catch (error) {
            console.error('获取任务状态失败:', error);
            return null;
        }
    }

    // 定时刷新任务状态（备用方案）
    startStatusPolling() {
        if (!this.currentTaskId) return;

        // 清除已有的轮询
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }

        console.log(`开始轮询任务状态: ${this.currentTaskId}`);
        
        const pollTask = async () => {
            try {
                const status = await this.getTaskStatus(this.currentTaskId);
                if (status) {
                    // 显示进度
                    this.updateProgress({
                        task_id: this.currentTaskId,
                        progress: status.progress,
                        total: status.total,
                        current_image: status.current_image,
                        status: status.status
                    });

                    // 显示新的日志条目
                    if (status.logs && status.logs.length > 0) {
                        // 只显示新的日志（简单判断：比当前显示的多）
                        const currentLogs = document.querySelectorAll('.log-entry').length;
                        const startIndex = Math.max(0, currentLogs - 1); // 减1因为可能有启动消息
                        
                        for (let i = startIndex; i < status.logs.length; i++) {
                            this.addLogEntry(status.logs[i]);
                        }
                    }

                    // 如果任务完成，停止轮询
                    if (status.status !== 'running') {
                        console.log(`任务${status.status}，停止轮询`);
                        this.clearPolling();
                        this.currentTaskId = null;
                    }
                } else {
                    console.error('获取任务状态失败');
                }
            } catch (error) {
                console.error('轮询任务状态失败:', error);
                this.addLogEntry({
                    timestamp: new Date().toLocaleString(),
                    level: 'error',
                    message: `获取任务状态失败: ${error.message}`
                });
            }
        };

        // 立即执行一次
        pollTask();
        
        // 每2秒轮询一次
        this.pollingInterval = setInterval(pollTask, 2000);

        // 5分钟后自动停止轮询
        setTimeout(() => {
            this.clearPolling();
        }, 300000);
    }

    // 清理轮询
    clearPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            console.log('轮询已停止');
        }
    }

    // 加载文件列表
    async loadFilesList() {
        try {
            const response = await fetch('/api/files');
            if (!response.ok) {
                throw new Error('获取文件列表失败');
            }
            
            const files = await response.json();
            this.renderFilesList(files);
        } catch (error) {
            console.error('加载文件列表失败:', error);
            this.renderFilesError('加载文件列表失败');
        }
    }

    // 渲染文件列表
    renderFilesList(files) {
        const container = document.getElementById('files-container');
        
        if (files.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted p-4">
                    <i class="fas fa-folder-open fa-3x mb-3"></i>
                    <h5>暂无导出文件</h5>
                    <p class="small">完成镜像同步后，导出的文件将显示在这里</p>
                </div>
            `;
            return;
        }

        // 计算总文件大小和统计信息
        const totalSize = files.reduce((sum, file) => sum + file.size, 0);
        const totalSizeMB = (totalSize / (1024 * 1024)).toFixed(2);
        const maxSize = Math.max(...files.map(f => f.size));

        let html = `
            <div class="mb-3">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <div class="d-flex align-items-center">
                            <button id="select-all-files" class="btn btn-sm btn-outline-primary me-2">
                                <i class="fas fa-check-square"></i> 全选
                            </button>
                            <button id="select-none-files" class="btn btn-sm btn-outline-secondary me-2">
                                <i class="fas fa-square"></i> 全不选
                            </button>
                            <span class="badge bg-info">
                                <i class="fas fa-file-archive"></i> ${files.length} 个文件
                            </span>
                            <span class="badge bg-secondary ms-2">
                                <i class="fas fa-weight-hanging"></i> 总计 ${totalSizeMB} MB
                            </span>
                        </div>
                    </div>
                    <div class="col-md-6 text-end">
                        <button id="batch-download-selected" class="btn btn-sm btn-success me-1" disabled>
                            <i class="fas fa-download"></i> 批量下载 (<span id="selected-count">0</span>)
                        </button>
                        <button id="delete-selected" class="btn btn-sm btn-danger" disabled>
                            <i class="fas fa-trash"></i> 删除选中项
                        </button>
                    </div>
                </div>
                
                <!-- 搜索和过滤栏 -->
                <div class="row mt-2">
                    <div class="col-md-6">
                        <div class="input-group input-group-sm">
                            <span class="input-group-text">
                                <i class="fas fa-search"></i>
                            </span>
                            <input type="text" id="file-search" class="form-control" 
                                   placeholder="搜索文件名..." onkeyup="filterFiles()">
                            <button class="btn btn-outline-secondary" type="button" onclick="clearFileSearch()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="d-flex gap-2">
                            <select id="size-filter" class="form-select form-select-sm" onchange="filterFiles()">
                                <option value="">所有大小</option>
                                <option value="small">小文件 (&lt;50MB)</option>
                                <option value="medium">中等文件 (50-200MB)</option>
                                <option value="large">大文件 (&gt;200MB)</option>
                            </select>
                            <select id="date-filter" class="form-select form-select-sm" onchange="filterFiles()">
                                <option value="">所有时间</option>
                                <option value="today">今天</option>
                                <option value="week">本周</option>
                                <option value="month">本月</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            <div class="table-responsive">
                <table class="table table-hover mb-0">
                    <thead class="table-light">
                        <tr>
                            <th width="40">
                                <input type="checkbox" id="select-all-checkbox" class="form-check-input">
                            </th>
                            <th><i class="fas fa-file"></i> 文件名</th>
                            <th><i class="fas fa-weight-hanging"></i> 大小</th>
                            <th><i class="fas fa-clock"></i> 创建时间</th>
                            <th><i class="fas fa-cogs"></i> 操作</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        files.forEach((file, index) => {
            const createTime = new Date(file.created_time).toLocaleString('zh-CN');
            const sizePercent = ((file.size / maxSize) * 100).toFixed(1);
            
            // 主要文件行
            html += `
                <tr data-file-index="${index}" class="file-row">
                    <td>
                        <input type="checkbox" class="file-checkbox form-check-input" 
                               data-filename="${file.name}" 
                               data-download-url="${file.download_url}">
                    </td>
                    <td>
                        <div class="d-flex align-items-center">
                            <i class="fas fa-file-archive text-primary me-2"></i>
                            <div>
                                <div class="fw-medium">${this.escapeHtml(file.name)}</div>
                                ${file.script ? '<small class="text-success"><i class="fas fa-file-code"></i> 包含推送脚本</small>' : ''}
                            </div>
                        </div>
                    </td>
                    <td>
                        <div class="file-size-info">
                            <div class="d-flex align-items-center mb-1">
                                <span class="badge bg-info me-2">${file.size_mb} MB</span>
                                <div class="progress flex-grow-1" style="height: 4px;">
                                    <div class="progress-bar bg-info" style="width: ${sizePercent}%"></div>
                                </div>
                            </div>
                            ${file.script ? `<small class="text-muted">${(file.script.size / 1024).toFixed(1)} KB 脚本</small>` : ''}
                        </div>
                    </td>
                    <td>
                        <small class="text-muted">${createTime}</small>
                    </td>
                    <td>
                        <div class="btn-group-vertical btn-group-sm w-100">
                            <div class="btn-group btn-group-sm mb-1">
                                <a href="${file.download_url}" class="btn btn-success btn-sm" title="下载tar包">
                                    <i class="fas fa-download"></i> 下载
                                </a>
                                <button class="btn btn-outline-secondary btn-sm" 
                                        onclick="copyLoadCommand('${file.name}')" 
                                        title="复制docker load命令">
                                    <i class="fas fa-copy"></i> 导入命令
                                </button>
                            </div>
                            ${file.script ? `
                            <div class="btn-group btn-group-sm mb-1">
                                <a href="${file.script.download_url}" class="btn btn-outline-success btn-sm" 
                                   title="下载推送脚本">
                                    <i class="fas fa-file-code"></i> 下载脚本
                                </a>
                                <button class="btn btn-outline-info btn-sm" 
                                        onclick="copyTagCommand('${file.script.name}')" 
                                        title="复制执行脚本命令">
                                    <i class="fas fa-copy"></i> 脚本命令
                                </button>
                            </div>
                            ` : ''}
                            <button class="btn btn-danger btn-sm" 
                                    onclick="deleteFile('${file.name}')" 
                                    title="删除文件">
                                <i class="fas fa-trash"></i> 删除
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
            <div class="mt-3 p-3 bg-light rounded">
                <div class="row">
                    <div class="col-md-4">
                        <h6><i class="fas fa-info-circle text-primary"></i> 快速操作</h6>
                        <ul class="small mb-2">
                            <li><strong>批量下载：</strong>勾选文件后点击"批量下载"</li>
                            <li><strong>快速导入：</strong>点击"导入命令"复制docker load命令</li>
                            <li><strong>自动推送：</strong>使用推送脚本自动标记并推送镜像</li>
                        </ul>
                    </div>
                    <div class="col-md-4">
                        <h6><i class="fas fa-magic text-success"></i> 智能功能</h6>
                        <ul class="small mb-2">
                            <li><strong>脚本生成：</strong>批量下载时自动生成推送脚本</li>
                            <li><strong>参数化配置：</strong>脚本支持命令行参数</li>
                            <li><strong>多仓库支持：</strong>可指定不同目标仓库</li>
                        </ul>
                    </div>
                    <div class="col-md-4">
                        <h6><i class="fas fa-shield-alt text-warning"></i> 安全特性</h6>
                        <ul class="small mb-2">
                            <li><strong>安全复制：</strong>多层级复制策略确保兼容性</li>
                            <li><strong>自动清理：</strong>默认保留1天，避免磁盘占满</li>
                            <li><strong>权限控制：</strong>仅复制命令，不直接执行</li>
                        </ul>
                    </div>
                </div>
                <div class="alert alert-info small mb-0">
                    <strong>💡 推荐工作流：</strong>
                    1. 选择需要的文件 → 2. 批量下载(含脚本) → 3. 在目标环境执行脚本 → 4. 自动完成导入和推送
                </div>
            </div>
        `;

        container.innerHTML = html;
        
        // 绑定批量操作事件
        this.bindBatchOperationEvents();
        
        // 添加文件行悬停效果
        this.addFileRowInteractions();
    }

    // 渲染文件列表错误
    renderFilesError(message) {
        const container = document.getElementById('files-container');
        container.innerHTML = `
            <div class="text-center text-danger p-4">
                <i class="fas fa-exclamation-circle"></i>
                ${message}
            </div>
        `;
    }

    // 删除文件
    async deleteFile(filename) {
        if (!confirm(`确定要删除文件 "${filename}" 吗？`)) {
            return;
        }

        try {
            const response = await fetch(`/api/files/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '删除失败');
            }

            const result = await response.json();
            alert(result.message);
            this.loadFilesList(); // 重新加载列表
        } catch (error) {
            console.error('删除文件失败:', error);
            alert(`删除失败: ${error.message}`);
        }
    }

    // 清理文件
    async cleanupFiles() {
        const maxAgeDays = prompt('请输入要清理的文件天数（默认7天）:', '7');
        if (maxAgeDays === null) {
            return;
        }

        const maxFiles = prompt('请输入最多保留的文件数量（默认50个）:', '50');
        if (maxFiles === null) {
            return;
        }

        try {
            const response = await fetch('/api/files/cleanup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    max_age_days: parseInt(maxAgeDays) || 7,
                    max_files: parseInt(maxFiles) || 50
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '清理失败');
            }

            const result = await response.json();
            alert(result.message);
            this.loadFilesList(); // 重新加载列表
        } catch (error) {
            console.error('清理文件失败:', error);
            alert(`清理失败: ${error.message}`);
        }
    }

    // 绑定批量操作事件
    bindBatchOperationEvents() {
        // 全选checkbox处理
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', () => {
                const checkboxes = document.querySelectorAll('.file-checkbox');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = selectAllCheckbox.checked;
                });
                this.updateSelectedCount();
            });
        }
        
        // 全选按钮
        document.getElementById('select-all-files').addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.file-checkbox');
            const selectAllCheckbox = document.getElementById('select-all-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
            if (selectAllCheckbox) selectAllCheckbox.checked = true;
            this.updateSelectedCount();
        });

        // 全不选按钮
        document.getElementById('select-none-files').addEventListener('click', () => {
            const checkboxes = document.querySelectorAll('.file-checkbox');
            const selectAllCheckbox = document.getElementById('select-all-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            if (selectAllCheckbox) selectAllCheckbox.checked = false;
            this.updateSelectedCount();
        });

        // 文件checkbox变化监听
        const fileCheckboxes = document.querySelectorAll('.file-checkbox');
        fileCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateSelectedCount();
                
                // 更新全选checkbox状态
                const allCheckboxes = document.querySelectorAll('.file-checkbox');
                const checkedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
                const selectAllCheckbox = document.getElementById('select-all-checkbox');
                
                if (selectAllCheckbox) {
                    if (checkedCheckboxes.length === 0) {
                        selectAllCheckbox.indeterminate = false;
                        selectAllCheckbox.checked = false;
                    } else if (checkedCheckboxes.length === allCheckboxes.length) {
                        selectAllCheckbox.indeterminate = false;
                        selectAllCheckbox.checked = true;
                    } else {
                        selectAllCheckbox.indeterminate = true;
                        selectAllCheckbox.checked = false;
                    }
                }
            });
        });

        // 批量下载
        document.getElementById('batch-download-selected').addEventListener('click', () => {
            this.batchDownloadSelected();
        });

        // 删除选中项
        document.getElementById('delete-selected').addEventListener('click', () => {
            this.deleteSelectedFiles();
        });
        
        // 初始化选择计数
        this.updateSelectedCount();
    }
    
    // 更新选中文件计数
    updateSelectedCount() {
        const checkedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
        const count = checkedCheckboxes.length;
        
        const countElement = document.getElementById('selected-count');
        if (countElement) {
            countElement.textContent = count;
        }
        
        // 更新批量操作按钮状态
        const batchDownloadBtn = document.getElementById('batch-download-selected');
        const deleteSelectedBtn = document.getElementById('delete-selected');
        
        if (batchDownloadBtn) batchDownloadBtn.disabled = count === 0;
        if (deleteSelectedBtn) deleteSelectedBtn.disabled = count === 0;
    }
    
    // 批量下载选中文件
    batchDownloadSelected() {
        const selectedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
        
        if (selectedCheckboxes.length === 0) {
            alert('请选择要下载的文件');
            return;
        }
        
        const filenames = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-filename'));
        
        // 显示目标仓库选择对话框
        this.showTargetRegistryDialog(filenames);
    }
    
    // 显示目标仓库选择对话框
    showTargetRegistryDialog(filenames) {
        const modalHtml = `
            <div class="modal fade" id="targetRegistryModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-download me-2"></i>批量下载配置 (${filenames.length} 个文件)
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                选择目标仓库将自动生成推送脚本，可用于将镜像重新标记并推送到指定仓库。
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <h6><i class="fas fa-list"></i> 选中的文件：</h6>
                                    <div class="list-group list-group-flush small" style="max-height: 200px; overflow-y: auto;">
                                        ${filenames.map(filename => `
                                            <div class="list-group-item py-1">
                                                <i class="fas fa-file-archive text-primary"></i> ${filename}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <h6><i class="fas fa-server"></i> 目标仓库配置：</h6>
                                    <div class="form-group mb-3">
                                        <label for="target-registry-select" class="form-label">选择目标仓库 (可选)</label>
                                        <select id="target-registry-select" class="form-select">
                                            <option value="">-- 不指定目标仓库 --</option>
                                        </select>
                                        <div class="form-text">选择后将生成对应的推送脚本</div>
                                    </div>
                                    
                                    <div id="custom-registry-section" style="display: none;">
                                        <div class="form-group mb-3">
                                            <label for="custom-registry-url" class="form-label">自定义仓库地址</label>
                                            <input type="text" id="custom-registry-url" class="form-control" 
                                                   placeholder="例如: harbor.example.com">
                                        </div>
                                    </div>
                                    
                                    <div class="alert alert-secondary small">
                                        <strong>💡 脚本使用提示：</strong><br>
                                        • <strong>不选择仓库</strong>：仅打包下载文件<br>
                                        • <strong>选择仓库</strong>：生成预配置推送脚本<br>
                                        • <strong>交互式运行</strong>：直接运行脚本，在运行时输入仓库信息<br>
                                        • <strong>命令行模式</strong>：使用 -r 参数指定仓库地址<br>
                                        <br>
                                        <kbd>./script.sh</kbd> - 交互式输入模式<br>
                                        <kbd>./script.sh -r harbor.example.com -u admin -p pass</kbd> - 命令行模式
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-success" id="confirm-batch-download-btn">
                                <i class="fas fa-download"></i> 开始打包下载
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除已存在的模态框
        const existingModal = document.getElementById('targetRegistryModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 添加新模态框
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 加载仓库列表
        this.loadRegistriesForBatchDownload();
        
        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('targetRegistryModal'));
        modal.show();
        
        // 绑定确认下载按钮事件
        document.getElementById('confirm-batch-download-btn').addEventListener('click', () => {
            this.confirmBatchDownload();
        });
        
        // 模态框关闭时移除DOM
        document.getElementById('targetRegistryModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
        
        // 存储文件列表供后续使用
        window.batchDownloadFilenames = filenames;
    }
    
    // 加载仓库列表用于批量下载
    async loadRegistriesForBatchDownload() {
        try {
            const response = await fetch('/api/registries');
            if (response.ok) {
                const registries = await response.json();
                const select = document.getElementById('target-registry-select');
                
                // 添加仓库选项
                registries.forEach(registry => {
                    if (registry.type !== 'local_file') {  // 排除本地文件类型
                        const option = document.createElement('option');
                        option.value = registry.url;
                        option.textContent = `${registry.name} (${registry.url})`;
                        select.appendChild(option);
                    }
                });
                
                // 添加自定义选项
                const customOption = document.createElement('option');
                customOption.value = 'custom';
                customOption.textContent = '-- 自定义仓库地址 --';
                select.appendChild(customOption);
                
                // 监听选择变化
                select.addEventListener('change', function() {
                    const customSection = document.getElementById('custom-registry-section');
                    if (this.value === 'custom') {
                        customSection.style.display = 'block';
                    } else {
                        customSection.style.display = 'none';
                    }
                });
                
            } else {
                console.error('获取仓库列表失败');
            }
        } catch (error) {
            console.error('加载仓库列表失败:', error);
        }
    }

    // 批量下载确认函数
    confirmBatchDownload() {
        const targetRegistrySelect = document.getElementById('target-registry-select');
        const customRegistryInput = document.getElementById('custom-registry-url');
        
        let targetRegistry = '';
        if (targetRegistrySelect.value === 'custom') {
            targetRegistry = customRegistryInput.value.trim();
        } else if (targetRegistrySelect.value) {
            targetRegistry = targetRegistrySelect.value;
        }
        
        // 关闭配置对话框
        const modal = bootstrap.Modal.getInstance(document.getElementById('targetRegistryModal'));
        if (modal) modal.hide();
        
        // 开始批量下载处理
        this.startBatchDownloadProcess(window.batchDownloadFilenames, targetRegistry);
    }
    
    // 开始批量下载处理
    startBatchDownloadProcess(filenames, targetRegistry) {
        // 显示处理进度模态框
        const downloadModal = this.createBatchDownloadProgressModal(filenames, targetRegistry);
        const modal = new bootstrap.Modal(downloadModal);
        modal.show();
        
        // 调用后端API创建zip文件和脚本
        this.createAndDownloadZipWithScript(filenames, targetRegistry);
    }
    
    // 创建批量下载进度模态框
    createBatchDownloadProgressModal(filenames, targetRegistry) {
        const modalHtml = `
            <div class="modal fade" id="batchDownloadProgressModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-download me-2"></i>批量下载进度 (${filenames.length} 个文件)
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="batch-download-status" class="alert alert-info">
                                <i class="fas fa-spinner fa-spin"></i>
                                正在打包文件${targetRegistry ? '并生成推送脚本' : ''}，请稍候...
                            </div>
                            
                            <div class="progress mb-3" style="display: none;">
                                <div id="batch-progress" class="progress-bar progress-bar-striped progress-bar-animated" 
                                     role="progressbar" style="width: 100%">打包中...</div>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <h6><i class="fas fa-list"></i> 文件列表：</h6>
                                    <div class="list-group list-group-flush small" style="max-height: 200px; overflow-y: auto;">
                                        ${filenames.map(filename => `
                                            <div class="list-group-item py-1">
                                                <i class="fas fa-file-archive text-primary"></i> ${filename}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <h6><i class="fas fa-cogs"></i> 配置信息：</h6>
                                    <div class="list-group list-group-flush small">
                                        <div class="list-group-item py-1">
                                            <strong>文件数量：</strong> ${filenames.length} 个
                                        </div>
                                        <div class="list-group-item py-1">
                                            <strong>目标仓库：</strong> ${targetRegistry || '未指定'}
                                        </div>
                                        <div class="list-group-item py-1">
                                            <strong>推送脚本：</strong> ${targetRegistry ? '将生成' : '不生成'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                            <div id="download-buttons" style="display: none;">
                                <button id="download-zip-btn" class="btn btn-success" disabled>
                                    <i class="fas fa-download"></i> 下载压缩包
                                </button>
                                <button id="download-script-btn" class="btn btn-info" disabled style="display: none;">
                                    <i class="fas fa-file-code"></i> 下载推送脚本
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除已存在的模态框
        const existingModal = document.getElementById('batchDownloadProgressModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 添加新模态框
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 模态框关闭时移除DOM
        const modal = document.getElementById('batchDownloadProgressModal');
        modal.addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
        
        return modal;
    }
    
    // 创建并下载zip文件和脚本
    async createAndDownloadZipWithScript(filenames, targetRegistry) {
        try {
            const requestData = {
                filenames: filenames
            };
            
            if (targetRegistry) {
                requestData.target_registry = targetRegistry;
            }
            
            const response = await fetch('/api/files/batch-download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || '创建压缩包失败');
            }
            
            const result = await response.json();
            
            // 更新状态为成功
            const statusDiv = document.getElementById('batch-download-status');
            const downloadButtons = document.getElementById('download-buttons');
            const downloadZipBtn = document.getElementById('download-zip-btn');
            const downloadScriptBtn = document.getElementById('download-script-btn');
            
            if (statusDiv) {
                let message = `<i class="fas fa-check-circle"></i> 压缩包创建成功！包含 ${result.file_count} 个文件`;
                
                if (result.script && result.script.target_registry) {
                    message += `<br><i class="fas fa-file-code text-success"></i> 推送脚本已生成 (目标: ${result.script.target_registry})`;
                }
                
                if (result.missing_files && result.missing_files.length > 0) {
                    message += `<br><small class="text-warning">⚠️ ${result.warning}</small>`;
                }
                
                statusDiv.className = 'alert alert-success';
                statusDiv.innerHTML = message;
            }
            
            // 显示下载按钮
            if (downloadButtons) {
                downloadButtons.style.display = 'block';
                
                // 配置zip下载按钮
                if (downloadZipBtn) {
                    downloadZipBtn.disabled = false;
                    downloadZipBtn.onclick = () => {
                        this.downloadFile(result.download_url, result.zip_filename, downloadZipBtn);
                    };
                }
                
                // 配置脚本下载按钮（如果有）
                if (result.script && downloadScriptBtn) {
                    downloadScriptBtn.style.display = 'inline-block';
                    downloadScriptBtn.disabled = false;
                    downloadScriptBtn.onclick = () => {
                        this.downloadFile(result.script.download_url, result.script.filename, downloadScriptBtn);
                    };
                }
            }
            
        } catch (error) {
            console.error('批量下载失败:', error);
            
            // 更新状态为失败
            const statusDiv = document.getElementById('batch-download-status');
            if (statusDiv) {
                statusDiv.className = 'alert alert-danger';
                statusDiv.innerHTML = `
                    <i class="fas fa-exclamation-circle"></i>
                    创建压缩包失败: ${error.message}
                `;
            }
        }
    }
    
    // 通用下载文件函数
    downloadFile(url, filename, button) {
        // 创建下载链接
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // 更新按钮状态
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i> 已开始下载';
        button.disabled = true;
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        }, 3000);
    }
    
    // 自动清理函数
    async autoCleanupFiles() {
        // 显示清理配置对话框
        const modalHtml = `
            <div class="modal fade" id="autoCleanupModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-clock me-2"></i>自动清理配置
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                系统当前每6小时自动清理超过1天的文件。您可以手动触发清理或查看清理状态。
                            </div>
                            
                            <div class="mb-3">
                                <h6>当前清理策略：</h6>
                                <ul class="small">
                                    <li><strong>保留时间：</strong>1天 (24小时)</li>
                                    <li><strong>清理频率：</strong>每6小时自动执行</li>
                                    <li><strong>清理范围：</strong>tar文件和相关脚本</li>
                                </ul>
                            </div>
                            
                            <div class="mb-3">
                                <h6>手动清理选项：</h6>
                                <div class="d-grid gap-2">
                                    <button type="button" class="btn btn-outline-warning" onclick="triggerManualCleanup()">
                                        <i class="fas fa-broom"></i> 立即执行清理
                                    </button>
                                    <button type="button" class="btn btn-outline-info" onclick="previewCleanupFiles()">
                                        <i class="fas fa-eye"></i> 预览将被清理的文件
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除已存在的模态框
        const existingModal = document.getElementById('autoCleanupModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 添加新模态框
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('autoCleanupModal'));
        modal.show();
        
        // 模态框关闭时移除DOM
        document.getElementById('autoCleanupModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    // 删除选中的文件
    async deleteSelectedFiles() {
        const selectedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
        
        if (selectedCheckboxes.length === 0) {
            alert('请选择要删除的文件');
            return;
        }
        
        const filenames = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-filename'));
        
        if (!confirm(`确定要删除选中的 ${filenames.length} 个文件吗？\n\n${filenames.join('\n')}`)) {
            return;
        }
        
        let successCount = 0;
        let failCount = 0;
        
        for (const filename of filenames) {
            try {
                const response = await fetch(`/api/files/${encodeURIComponent(filename)}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    successCount++;
                } else {
                    failCount++;
                    console.error(`删除文件 ${filename} 失败`);
                }
            } catch (error) {
                failCount++;
                console.error(`删除文件 ${filename} 异常:`, error);
            }
        }
        
        // 显示结果
        if (failCount === 0) {
            alert(`成功删除 ${successCount} 个文件`);
        } else {
            alert(`删除完成：成功 ${successCount} 个，失败 ${failCount} 个`);
        }
        
        // 重新加载文件列表
        this.loadFilesList();
    }

    // 添加文件行悬停效果
    addFileRowInteractions() {
        const rows = document.querySelectorAll('.file-row');
        rows.forEach(row => {
            row.addEventListener('mouseenter', () => {
                row.classList.add('bg-light');
            });
            row.addEventListener('mouseleave', () => {
                row.classList.remove('bg-light');
            });
        });
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', async () => {
    // 首先初始化用户认证
    userAuth = new UserAuth();
    
    // 等待用户认证初始化完成
    await userAuth.init();
    
    // 如果用户认证成功，再初始化主应用
    if (userAuth.currentUser) {
        window.dockerSyncApp = new DockerSyncApp();
        console.log('Docker镜像同步工具已初始化');
        
        // 加载文件列表
        dockerSyncApp.loadFilesList();
    }
    
    // 添加一些有用的全局函数
    window.addSampleImages = function() {
        const textarea = document.getElementById('images-input');
        const sampleImages = [
            '# 常用基础镜像',
            'nginx:latest',
            'nginx:1.21-alpine',
            '',
            '# 数据库镜像',
            'redis:6.2-alpine',
            'mysql:8.0',
            'postgres:13-alpine',
            '',
            '# 开发环境镜像',
            'node:16-alpine',
            'python:3.9-slim',
            'openjdk:11-jre-slim',
            '',
            '# 其他常用镜像',
            'ubuntu:20.04',
            'alpine:latest',
            'busybox:latest'
        ];
        textarea.value = sampleImages.join('\n');
        // 格式化镜像列表
        if (window.dockerSyncApp) {
            dockerSyncApp.formatImagesList();
        }
    };

    window.clearImagesList = function() {
        document.getElementById('images-input').value = '';
    };

    window.showReplaceLevelHelp = function() {
        const helpModal = document.getElementById('replaceLevelHelpModal');
        if (window.bootstrap && window.bootstrap.Modal) {
            const modal = new bootstrap.Modal(helpModal);
            modal.show();
        } else if (window.$ && window.$.fn.modal) {
            $(helpModal).modal('show');
        }
    };

    // 文件管理相关全局函数
    window.deleteFile = function(filename) {
        if (window.dockerSyncApp) {
            dockerSyncApp.deleteFile(filename);
        }
    };

    window.copyLoadCommand = function(filename) {
        const command = `docker load < ${filename}`;
        copyToClipboard(command, event.target, '导入命令已复制');
    };

    window.copyTagCommand = function(scriptName) {
        const command = `bash ${scriptName}`;
        copyToClipboard(command, event.target, '执行命令已复制');
    };

    // 复制到剪贴板的通用函数
    function copyToClipboard(text, buttonElement, successMessage) {
        // 方法1: 尝试使用现代 Clipboard API (HTTPS环境)
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                showCopySuccess(buttonElement, successMessage);
            }).catch(err => {
                console.warn('Clipboard API失败，尝试备用方案:', err);
                fallbackCopyMethod(text, buttonElement, successMessage);
            });
        } else {
            // 方法2: HTTP环境或不支持Clipboard API时的备用方案
            fallbackCopyMethod(text, buttonElement, successMessage);
        }
    }
    
    // 备用复制方法
    function fallbackCopyMethod(text, buttonElement, successMessage) {
        try {
            // 方法2A: 使用document.execCommand (已废弃但仍广泛支持)
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            
            if (successful) {
                showCopySuccess(buttonElement, successMessage);
            } else {
                // 方法2B: 手动选择文本提示用户复制
                showManualCopyDialog(text, buttonElement);
            }
        } catch (err) {
            console.warn('execCommand复制失败:', err);
            // 方法2B: 手动选择文本提示用户复制
            showManualCopyDialog(text, buttonElement);
        }
    }
    
    // 显示复制成功反馈
    function showCopySuccess(buttonElement, successMessage) {
        const button = buttonElement.closest('button');
        if (!button) return;
        
        const originalText = button.innerHTML;
        const originalClasses = Array.from(button.classList);
        
        // 显示成功状态
        button.innerHTML = '<i class="fas fa-check"></i> 已复制';
        button.className = 'btn btn-success btn-sm';
        
        // 2秒后恢复原状
        setTimeout(() => {
            button.innerHTML = originalText;
            button.className = originalClasses.join(' ');
        }, 2000);
    }
    
    // 显示手动复制对话框
    function showManualCopyDialog(text, buttonElement) {
        // 创建模态框
        const modalHtml = `
            <div class="modal fade" id="manualCopyModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="fas fa-copy me-2"></i>手动复制命令
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                由于浏览器安全限制（HTTP环境），无法自动复制到剪贴板。<br>
                                请手动选择并复制以下命令：
                            </div>
                            <div class="form-group">
                                <label class="form-label">命令内容：</label>
                                <textarea class="form-control" id="manual-copy-text" rows="3" readonly>${text}</textarea>
                            </div>
                            <div class="mt-2">
                                <button type="button" class="btn btn-primary btn-sm" onclick="selectManualCopyText()">
                                    <i class="fas fa-mouse-pointer"></i> 全选文本
                                </button>
                                <small class="text-muted ms-2">选择后按 Ctrl+C (Windows) 或 Cmd+C (Mac) 复制</small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除已存在的模态框
        const existingModal = document.getElementById('manualCopyModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 添加新模态框
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('manualCopyModal'));
        modal.show();
        
        // 自动选择文本
        setTimeout(() => {
            const textarea = document.getElementById('manual-copy-text');
            if (textarea) {
                textarea.focus();
                textarea.select();
            }
        }, 500);
        
        // 模态框关闭时移除DOM
        document.getElementById('manualCopyModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
        
        // 更新按钮状态
        const button = buttonElement.closest('button');
        if (button) {
            const originalText = button.innerHTML;
            const originalClasses = Array.from(button.classList);
            
            button.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 需手动复制';
            button.className = 'btn btn-warning btn-sm';
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.className = originalClasses.join(' ');
            }, 3000);
        }
    }
    
    // 全选手动复制文本
    function selectManualCopyText() {
        const textarea = document.getElementById('manual-copy-text');
        if (textarea) {
            textarea.focus();
            textarea.select();
            
            // 尝试再次复制
            try {
                const successful = document.execCommand('copy');
                if (successful) {
                    // 显示成功提示
                    const button = event.target.closest('button');
                    if (button) {
                        const originalText = button.innerHTML;
                        button.innerHTML = '<i class="fas fa-check"></i> 已复制';
                        button.className = 'btn btn-success btn-sm';
                        
                        setTimeout(() => {
                            button.innerHTML = originalText;
                            button.className = 'btn btn-primary btn-sm';
                        }, 2000);
                    }
                }
            } catch (err) {
                console.warn('手动复制仍然失败:', err);
            }
        }
    }

    // 保持向后兼容
    window.copyDownloadCommand = window.copyLoadCommand;
    
    // 添加全局函数
    window.selectManualCopyText = selectManualCopyText;

    // 手动触发清理
    async function triggerManualCleanup() {
        try {
            if (confirm('确定要立即执行清理吗？这将删除1天前创建的所有文件。')) {
                const response = await fetch('/api/files/auto-cleanup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || '清理失败');
                }
                
                const result = await response.json();
                alert(result.message);
                
                // 关闭模态框并重新加载文件列表
                const modal = bootstrap.Modal.getInstance(document.getElementById('autoCleanupModal'));
                if (modal) modal.hide();
                
                // 重新加载文件列表
                if (window.dockerSyncApp) {
                    window.dockerSyncApp.loadFilesList();
                }
            }
        } catch (error) {
            console.error('手动清理失败:', error);
            alert(`清理失败: ${error.message}`);
        }
    }

    // 预览将被清理的文件
    async function previewCleanupFiles() {
        try {
            const response = await fetch('/api/files');
            if (!response.ok) {
                throw new Error('获取文件列表失败');
            }
            
            const files = await response.json();
            const currentTime = new Date().getTime();
            const oneDayAgo = currentTime - (24 * 60 * 60 * 1000); // 24小时前
            
            const filesToCleanup = files.filter(file => {
                const fileTime = new Date(file.created_time).getTime();
                return fileTime < oneDayAgo;
            });
            
            // 显示预览对话框
            const previewHtml = `
                <div class="modal fade" id="previewCleanupModal" tabindex="-1">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">
                                    <i class="fas fa-eye me-2"></i>清理预览
                                </h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                ${filesToCleanup.length === 0 ? `
                                    <div class="text-center text-success p-4">
                                        <i class="fas fa-check-circle fa-3x mb-3"></i>
                                        <h5>没有需要清理的文件</h5>
                                        <p class="text-muted">所有文件都在保留期内</p>
                                    </div>
                                ` : `
                                    <div class="alert alert-warning">
                                        <i class="fas fa-exclamation-triangle"></i>
                                        以下 ${filesToCleanup.length} 个文件将被清理（创建时间超过1天）：
                                    </div>
                                    <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                                        <table class="table table-sm">
                                            <thead class="table-light">
                                                <tr>
                                                    <th>文件名</th>
                                                    <th>大小</th>
                                                    <th>创建时间</th>
                                                    <th>天数</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                ${filesToCleanup.map(file => {
                                                    const fileTime = new Date(file.created_time);
                                                    const daysOld = Math.floor((currentTime - fileTime.getTime()) / (24 * 60 * 60 * 1000));
                                                    return `
                                                        <tr>
                                                            <td>
                                                                <i class="fas fa-file-archive text-muted"></i>
                                                                ${file.name}
                                                            </td>
                                                            <td>${file.size_mb} MB</td>
                                                            <td>${fileTime.toLocaleString('zh-CN')}</td>
                                                            <td>
                                                                <span class="badge bg-warning">${daysOld} 天前</span>
                                                            </td>
                                                        </tr>
                                                    `;
                                                }).join('')}
                                            </tbody>
                                        </table>
                                    </div>
                                    <div class="mt-3">
                                        <strong>总计：</strong>
                                        ${filesToCleanup.length} 个文件，
                                        ${filesToCleanup.reduce((sum, file) => sum + file.size_mb, 0).toFixed(2)} MB
                                    </div>
                                `}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                                ${filesToCleanup.length > 0 ? `
                                    <button type="button" class="btn btn-warning" onclick="confirmPreviewCleanup()">
                                        <i class="fas fa-broom"></i> 立即清理这些文件
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // 移除已存在的预览模态框
            const existingPreviewModal = document.getElementById('previewCleanupModal');
            if (existingPreviewModal) {
                existingPreviewModal.remove();
            }
            
            // 添加预览模态框
            document.body.insertAdjacentHTML('beforeend', previewHtml);
            
            // 显示预览模态框
            const previewModal = new bootstrap.Modal(document.getElementById('previewCleanupModal'));
            previewModal.show();
            
            // 模态框关闭时移除DOM
            document.getElementById('previewCleanupModal').addEventListener('hidden.bs.modal', function() {
                this.remove();
            });
            
        } catch (error) {
            console.error('预览清理文件失败:', error);
            alert(`预览失败: ${error.message}`);
        }
    }

    // 确认预览清理
    async function confirmPreviewCleanup() {
        // 关闭预览模态框
        const previewModal = bootstrap.Modal.getInstance(document.getElementById('previewCleanupModal'));
        if (previewModal) previewModal.hide();
        
        // 执行清理
        await triggerManualCleanup();
    }

    // 添加全局函数到window对象
    window.triggerManualCleanup = triggerManualCleanup;
    window.previewCleanupFiles = previewCleanupFiles;
    window.confirmPreviewCleanup = confirmPreviewCleanup;

    // 文件搜索和过滤功能
    function filterFiles() {
        const searchTerm = document.getElementById('file-search').value.toLowerCase();
        const sizeFilter = document.getElementById('size-filter').value;
        const dateFilter = document.getElementById('date-filter').value;
        
        const rows = document.querySelectorAll('.file-row');
        let visibleCount = 0;
        
        rows.forEach(row => {
            const filename = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const sizeText = row.querySelector('.badge.bg-info').textContent;
            const sizeMB = parseFloat(sizeText.replace(' MB', ''));
            const dateText = row.querySelector('td:nth-child(4) small').textContent;
            const fileDate = new Date(dateText);
            
            let showRow = true;
            
            // 文件名搜索
            if (searchTerm && !filename.includes(searchTerm)) {
                showRow = false;
            }
            
            // 大小过滤
            if (sizeFilter) {
                switch (sizeFilter) {
                    case 'small':
                        if (sizeMB >= 50) showRow = false;
                        break;
                    case 'medium':
                        if (sizeMB < 50 || sizeMB > 200) showRow = false;
                        break;
                    case 'large':
                        if (sizeMB <= 200) showRow = false;
                        break;
                }
            }
            
            // 日期过滤
            if (dateFilter) {
                const now = new Date();
                const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
                const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
                
                switch (dateFilter) {
                    case 'today':
                        if (fileDate < today) showRow = false;
                        break;
                    case 'week':
                        if (fileDate < weekAgo) showRow = false;
                        break;
                    case 'month':
                        if (fileDate < monthAgo) showRow = false;
                        break;
                }
            }
            
            if (showRow) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
                // 取消选中隐藏的文件
                const checkbox = row.querySelector('.file-checkbox');
                if (checkbox && checkbox.checked) {
                    checkbox.checked = false;
                }
            }
        });
        
        // 更新显示的文件计数
        updateFilteredFileCount(visibleCount);
        
        // 更新选中计数
        if (window.dockerSyncApp) {
            window.dockerSyncApp.updateSelectedCount();
        }
    }

    // 清除搜索
    function clearFileSearch() {
        document.getElementById('file-search').value = '';
        document.getElementById('size-filter').value = '';
        document.getElementById('date-filter').value = '';
        filterFiles();
    }

    // 更新过滤后的文件计数显示
    function updateFilteredFileCount(visibleCount) {
        const totalFiles = document.querySelectorAll('.file-row').length;
        const fileCountBadge = document.querySelector('.badge.bg-info');
        
        if (fileCountBadge) {
            if (visibleCount === totalFiles) {
                fileCountBadge.innerHTML = `<i class="fas fa-file-archive"></i> ${totalFiles} 个文件`;
            } else {
                fileCountBadge.innerHTML = `<i class="fas fa-file-archive"></i> ${visibleCount}/${totalFiles} 个文件`;
                fileCountBadge.classList.remove('bg-info');
                fileCountBadge.classList.add('bg-warning');
            }
        }
    }

    // 添加到全局
    window.filterFiles = filterFiles;
    window.clearFileSearch = clearFileSearch;
});

// 控制私有认证区域的显示/隐藏
function togglePrivateAuth() {
    const checkbox = document.getElementById('use-private-auth');
    const authSection = document.getElementById('private-auth-section');
    
    if (checkbox.checked) {
        authSection.style.display = 'block';
        // 聚焦到用户名输入框
        setTimeout(() => {
            document.getElementById('source-username').focus();
        }, 100);
    } else {
        authSection.style.display = 'none';
        // 清空输入框
        document.getElementById('source-username').value = '';
        document.getElementById('source-password').value = '';
    }
}

// 控制代理配置区域的显示/隐藏
function toggleProxy() {
    const checkbox = document.getElementById('use-proxy');
    const proxySection = document.getElementById('proxy-section');
    
    if (checkbox.checked) {
        proxySection.style.display = 'block';
        // 聚焦到HTTP代理输入框
        setTimeout(() => {
            document.getElementById('proxy-http').focus();
        }, 100);
    } else {
        proxySection.style.display = 'none';
        // 清空输入框
        document.getElementById('proxy-http').value = '';
        document.getElementById('proxy-https').value = '';
        document.getElementById('proxy-no-proxy').value = '';
    }
} 