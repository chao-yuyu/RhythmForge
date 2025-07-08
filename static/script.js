// 節奏遊戲 Web 應用 JavaScript
// Rhythm Game Web Application JavaScript

class RhythmGameApp {
    constructor() {
        this.currentPage = 'download';
        this.socket = null;
        this.config = null;
        this.selectedCharts = new Set(); // 追蹤選取的譜面
        this.selectedAudioFiles = new Set(); // 追蹤選取的音樂檔案
        this.init();
    }
    
    init() {
        this.initSocket();
        this.initNavigation();
        this.initEventListeners();
        this.loadConfig();
        this.showPage('download');
    }
    
    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
        });
        
        this.socket.on('download_progress', (data) => {
            this.handleDownloadProgress(data);
        });
        
        this.socket.on('chart_progress', (data) => {
            this.handleChartProgress(data);
        });
    }

    initNavigation() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = e.target.closest('.nav-btn').dataset.page;
                this.showPage(page);
            });
        });
    }
    
    showPage(pageName) {
        // 隱藏所有頁面
        document.querySelectorAll('.page').forEach(page => {
            page.classList.remove('active');
        });
        
        // 更新導航按鈕狀態
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.page === pageName) {
                btn.classList.add('active');
            }
        });
        
        // 顯示目標頁面
        const targetPage = document.getElementById(`${pageName}-page`);
        if (targetPage) {
            targetPage.classList.add('active');
            this.currentPage = pageName;
            
            // 頁面特定初始化
            switch (pageName) {
                case 'generate':
                    this.loadAudioFiles();
                    break;
                case 'charts':
                    this.loadCharts();
                    break;
                case 'settings':
                    this.loadSettings();
                    break;
            }
        }
    }
    
    initEventListeners() {
        // 下載按鈕
        document.getElementById('download-btn').addEventListener('click', () => {
            this.downloadMusic();
        });
        
        // 重新整理音樂檔案
        document.getElementById('refresh-audio-btn').addEventListener('click', () => {
            this.loadAudioFiles();
        });
        
        // 音樂檔案選取相關按鈕
        document.getElementById('toggle-select-audio-btn').addEventListener('click', () => {
            this.toggleSelectAllAudioFiles();
        });
        
        document.getElementById('delete-selected-audio-btn').addEventListener('click', () => {
            this.deleteSelectedAudioFiles();
        });

        // 重新整理譜面
        document.getElementById('refresh-charts-btn').addEventListener('click', () => {
            this.loadCharts();
        });
        
        // 譜面選取相關按鈕
        document.getElementById('toggle-select-charts-btn').addEventListener('click', () => {
            this.toggleSelectAllCharts();
        });
        
        document.getElementById('delete-selected-charts-btn').addEventListener('click', () => {
            this.deleteSelectedCharts();
        });
        
        // 設定相關
        document.getElementById('save-settings-btn').addEventListener('click', () => {
            this.saveSettings();
        });
        
        document.getElementById('reset-settings-btn').addEventListener('click', () => {
            this.resetSettings();
        });
        
        // 範圍輸入初始化
        this.initRangeInputs();
        
        // 生成方法選擇器
        this.initGenerationMethodSelector();
        
        // 上傳功能初始化
        this.initUploadFeatures();
    }
    
    initRangeInputs() {
        const rangeInputs = document.querySelectorAll('input[type="range"]');
        rangeInputs.forEach(input => {
            const valueSpan = document.getElementById(input.id + '-value');
            if (valueSpan) {
                const updateValue = () => {
                    let value = input.value;
                    if (input.step && parseFloat(input.step) < 1) {
                        value = parseFloat(value).toFixed(2);
                    }
                    if (input.id.includes('tolerance') || input.id.includes('delay') || input.id.includes('offset')) {
                        value += 's';
                    }
                    valueSpan.textContent = value;
                };

                input.addEventListener('input', updateValue);
                updateValue();
            }
        });
    }
    
    initGenerationMethodSelector() {
        const methodSelector = document.getElementById('generation-method');
        const methodDescription = document.getElementById('method-description');
        
        if (methodSelector && methodDescription) {
            const updateDescription = () => {
                const selectedMethod = methodSelector.value;
                let description = '';
                
                switch (selectedMethod) {
                    case 'balanced_beat':
                        description = '<h4>平衡節拍分配</h4><p>基於累積數量平衡各lane，並對齊音樂拍點，產生更平衡且符合節奏的譜面。適合大多數音樂類型。</p>';
                        break;
                    case 'energy':
                        description = '<h4>能量分析</h4><p>分析音樂的能量變化，在高能量區域放置更多音符，在低能量區域減少音符密度。適合動感音樂。</p>';
                        break;
                    default:
                        description = '<p>請選擇一種生成方法</p>';
                }
                
                methodDescription.innerHTML = description;
            };
            
            methodSelector.addEventListener('change', updateDescription);
            updateDescription();
        }
    }
    
    initUploadFeatures() {
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('music-file-input');
        
        // 拖放功能
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });
        
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileUpload(files[0]);
            }
        });
        
        // 檔案選擇
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileUpload(e.target.files[0]);
            }
        });
    }
    
    handleFileUpload(file) {
        // 檢查檔案類型
        const allowedTypes = ['audio/mp3', 'audio/mpeg', 'audio/wav'];
        const fileExtension = file.name.toLowerCase().split('.').pop();
        const allowedExtensions = ['mp3', 'wav'];
        
        if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
            this.showNotification('請選擇 MP3 或 WAV 格式的音樂檔案', 'error');
            return;
        }
        
        // 檢查檔案大小 (限制為 50MB)
        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
            this.showNotification('檔案大小不能超過 50MB', 'error');
            return;
        }
        
        // 開始上傳
        this.uploadMusicFile(file);
    }
    
    async uploadMusicFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // 顯示上傳進度
            this.showUploadProgress();
            
            const response = await fetch('/api/upload_music', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                this.handleUploadSuccess(data);
            } else {
                const error = await response.json();
                throw new Error(error.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.handleUploadError(error.message);
        }
    }
    
    showUploadProgress() {
        const progressContainer = document.getElementById('upload-progress');
        const progressText = progressContainer.querySelector('.progress-text');
        const resultContainer = document.getElementById('upload-result');
        
        progressContainer.style.display = 'block';
        progressText.textContent = '上傳中...';
        resultContainer.innerHTML = '';
    }
    
    handleUploadSuccess(data) {
        const progressContainer = document.getElementById('upload-progress');
        const resultContainer = document.getElementById('upload-result');
        
        progressContainer.style.display = 'none';
        
        resultContainer.innerHTML = `
            <div class="success-message">
                <h3><i class="fas fa-check-circle"></i> 上傳完成！</h3>
                <p><strong>檔案名稱:</strong> ${data.filename}</p>
                <p><strong>檔案大小:</strong> ${this.formatFileSize(data.size)}</p>
                <p><strong>時長:</strong> ${data.duration || '未知'}</p>
                <button class="btn-primary" onclick="app.generateChartFromUpload('${data.path}', '${data.title}')">
                    <i class="fas fa-waveform-lines"></i> 生成譜面
                </button>
            </div>
        `;
        
        this.showNotification('音樂檔案上傳完成！', 'success');
        
        // 清空檔案輸入
        document.getElementById('music-file-input').value = '';
        
        // 重新載入音樂檔案列表
        this.loadAudioFiles();
    }
    
    handleUploadError(errorMessage) {
        const progressContainer = document.getElementById('upload-progress');
        const resultContainer = document.getElementById('upload-result');
        
        progressContainer.style.display = 'none';
        
        resultContainer.innerHTML = `
            <div class="error-message">
                <h3><i class="fas fa-exclamation-triangle"></i> 上傳失敗</h3>
                <p>${errorMessage}</p>
                <button class="btn-secondary" onclick="app.resetUploadUI()">
                    <i class="fas fa-redo"></i> 重試
                </button>
            </div>
        `;
        
        this.showNotification(`上傳失敗: ${errorMessage}`, 'error');
    }
    
    resetUploadUI() {
        document.getElementById('upload-progress').style.display = 'none';
        document.getElementById('upload-result').innerHTML = '';
        document.getElementById('music-file-input').value = '';
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    generateChartFromUpload(audioPath, songTitle) {
        this.generateChart(audioPath, songTitle);
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            this.config = await response.json();
        } catch (error) {
            console.error('Error loading config:', error);
        }
    }

    loadSettings() {
        this.updateSettingsUI();
    }

    updateSettingsUI() {
        // 更新設定 UI
        const settings = {
            'note-speed': this.config.note_speed || 300,
            'perfect-tolerance': this.config.perfect_tolerance || 0.05,
            'great-tolerance': this.config.great_tolerance || 0.1,
            'good-tolerance': this.config.good_tolerance || 0.15,
            'debug-mode': this.config.debug_mode || false,
            'audio-delay': this.config.audio_delay || 0.15,
            'visual-offset': this.config.visual_offset || 0.0
        };

        Object.entries(settings).forEach(([key, value]) => {
            const element = document.getElementById(key);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = value;
                } else {
                    element.value = value;
                }
                
                // 觸發 input 事件來更新顯示值
                if (element.type === 'range') {
                    element.dispatchEvent(new Event('input'));
                }
            }
        });
    }
    
    async saveSettings() {
        const settings = {
            note_speed: parseInt(document.getElementById('note-speed').value),
            perfect_tolerance: parseFloat(document.getElementById('perfect-tolerance').value),
            great_tolerance: parseFloat(document.getElementById('great-tolerance').value),
            good_tolerance: parseFloat(document.getElementById('good-tolerance').value),
            debug_mode: document.getElementById('debug-mode').checked,
            audio_delay: parseFloat(document.getElementById('audio-delay').value),
            visual_offset: parseFloat(document.getElementById('visual-offset').value)
        };
        
        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            });
            
            if (response.ok) {
                this.config = settings;
                this.showNotification('設定已儲存', 'success');
            } else {
                throw new Error('Failed to save settings');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            this.showNotification('儲存設定失敗', 'error');
        }
    }
    
    resetSettings() {
        const defaultSettings = {
            'note-speed': 300,
            'perfect-tolerance': 0.05,
            'great-tolerance': 0.1,
            'good-tolerance': 0.15,
            'debug-mode': false,
            'audio-delay': 0.15,
            'visual-offset': 0.0
        };

        Object.entries(defaultSettings).forEach(([key, value]) => {
            const element = document.getElementById(key);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = value;
                } else {
                    element.value = value;
                }
                
                if (element.type === 'range') {
                    element.dispatchEvent(new Event('input'));
                }
            }
        });

        this.showNotification('設定已重置為預設值', 'info');
    }

    async downloadMusic() {
        const url = document.getElementById('youtube-url').value.trim();
        
        if (!url) {
            this.showNotification('請輸入 YouTube 連結', 'error');
            return;
        }
        
        if (!this.isValidYouTubeUrl(url)) {
            this.showNotification('請輸入有效的 YouTube 連結', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url })
            });
            
            if (response.ok) {
            const data = await response.json();
            this.showNotification('開始下載...', 'info');
                this.showDownloadProgress();
            } else {
                const error = await response.json();
                throw new Error(error.error || 'Download failed');
            }
        } catch (error) {
            console.error('Download error:', error);
            this.showNotification(`下載失敗: ${error.message}`, 'error');
        }
    }
    
    handleDownloadProgress(data) {
        const progressContainer = document.getElementById('download-progress');
        const progressFill = progressContainer.querySelector('.progress-fill');
        const progressText = progressContainer.querySelector('.progress-text');
        const resultContainer = document.getElementById('download-result');
        
        if (data.status === 'downloading') {
            progressFill.style.width = `${data.progress}%`;
            progressText.textContent = `下載中... ${data.progress}%`;
        } else if (data.status === 'processing') {
            progressFill.style.width = '100%';
            progressText.textContent = '處理中...';
        } else if (data.status === 'completed') {
            progressContainer.style.display = 'none';
            
            resultContainer.innerHTML = `
                <div class="success-message">
                    <h3><i class="fas fa-check-circle"></i> 下載完成！</h3>
                    <p><strong>標題:</strong> ${data.title}</p>
                    <p><strong>時長:</strong> ${data.duration}</p>
                    <p><strong>檔案:</strong> ${data.filename}</p>
                    <button class="btn-primary" onclick="app.generateChartFromDownload('${data.audio_path}', '${data.title}')">
                        <i class="fas fa-waveform-lines"></i> 生成譜面
                    </button>
                </div>
            `;
            
            this.showNotification('音樂下載完成！', 'success');
            
            // 清空輸入框
            document.getElementById('youtube-url').value = '';
            
            // 重新載入音樂檔案列表
            this.loadAudioFiles();
        } else if (data.status === 'failed') {
            progressContainer.style.display = 'none';
            
            let errorMessage = data.error || '下載失敗';
            let suggestions = '';
            
            if (data.error && data.error.includes('Video unavailable')) {
                errorMessage = '影片無法存取';
                suggestions = `
                    <div class="error-suggestions">
                        <h4>可能的解決方案：</h4>
                        <ul>
                            <li>檢查影片是否為私人或已被刪除</li>
                            <li>確認影片連結是否正確</li>
                            <li>嘗試使用其他 YouTube 影片</li>
                        </ul>
                    </div>
                `;
            } else if (data.error && data.error.includes('network')) {
                errorMessage = '網路連線問題';
                suggestions = `
                    <div class="error-suggestions">
                        <h4>可能的解決方案：</h4>
                        <ul>
                            <li>檢查網路連線</li>
                            <li>稍後再試</li>
                            <li>嘗試重新載入頁面</li>
                        </ul>
                    </div>
                `;
            }
            
            resultContainer.innerHTML = `
                <div class="error-message">
                    <h3><i class="fas fa-exclamation-triangle"></i> 下載失敗</h3>
                    <p>${errorMessage}</p>
                    ${suggestions}
                    <button class="btn-secondary" onclick="app.retryDownload()">
                        <i class="fas fa-redo"></i> 重試
                    </button>
                </div>
            `;
            
            this.showNotification(`下載失敗: ${errorMessage}`, 'error');
        }
    }
    
    retryDownload() {
        this.resetDownloadUI();
            this.downloadMusic();
    }
    
    resetDownloadUI() {
        document.getElementById('download-progress').style.display = 'none';
        document.getElementById('download-result').innerHTML = '';
    }
    
    isValidYouTubeUrl(url) {
        const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/;
        return youtubeRegex.test(url);
    }

    showDownloadProgress() {
        const progressContainer = document.getElementById('download-progress');
        const progressFill = progressContainer.querySelector('.progress-fill');
        const progressText = progressContainer.querySelector('.progress-text');
        
        progressContainer.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = '準備下載...';
        
        // 清空之前的結果
        document.getElementById('download-result').innerHTML = '';
    }

    async loadAudioFiles() {
        try {
            const response = await fetch('/api/audio_files');
            const data = await response.json();
            
            if (data.success) {
                this.displayAudioFiles(data.files);
            } else {
                throw new Error(data.error || 'Failed to load audio files');
            }
        } catch (error) {
            console.error('Error loading audio files:', error);
            this.showNotification('載入音樂檔案失敗', 'error');
        }
    }
    
    displayAudioFiles(files) {
        const container = document.getElementById('audio-files');
        const toggleSelectBtn = document.getElementById('toggle-select-audio-btn');
        const deleteSelectedBtn = document.getElementById('delete-selected-audio-btn');
        
        // 清空選取狀態
        this.selectedAudioFiles.clear();
        
        if (files.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>沒有找到音樂檔案</p><p>請先下載一些音樂</p></div>';
            if (toggleSelectBtn) toggleSelectBtn.style.display = 'none';
            if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'none';
            return;
        }

        // 顯示控制按鈕並重置切換按鈕狀態
        if (toggleSelectBtn) {
            toggleSelectBtn.style.display = 'inline-flex';
            toggleSelectBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
        }
        if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'inline-flex';

        container.innerHTML = files.map(file => `
            <div class="file-card" data-path="${file.path}">
                <div class="chart-select">
                    <input type="checkbox" id="audio-${file.path}" onchange="app.toggleAudioFileSelection('${file.path}', this.checked)">
                    <label for="audio-${file.path}" class="select-label">選取</label>
                </div>
                <h4>${file.title}</h4>
                <p>檔案: ${file.filename}</p>
                <p>時長: ${file.duration || '未知'}</p>
                <div class="file-actions">
                    <button class="btn-primary" onclick="app.generateChart('${file.path}', '${file.title}')">
                        <i class="fas fa-waveform-lines"></i> 生成譜面
                    </button>
                    <button class="btn-danger" onclick="app.deleteAudioFile('${file.path}', '${file.title}')">
                        <i class="fas fa-trash-alt"></i> 刪除
                    </button>
                </div>
            </div>
        `).join('');
        
        this.updateSelectedAudioFilesCount();
    }
    
    async generateChart(audioPath, songTitle) {
        const method = document.getElementById('generation-method').value;
        
        try {
            this.showChartProgress();
            
            const response = await fetch('/api/generate_chart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio_path: audioPath,
                    song_title: songTitle,
                    method: method
                })
            });
            
            if (response.ok) {
                this.showNotification('開始生成譜面...', 'info');
            } else {
                const error = await response.json();
                throw new Error(error.error || 'Chart generation failed');
            }
        } catch (error) {
            console.error('Chart generation error:', error);
            this.showNotification(`生成譜面失敗: ${error.message}`, 'error');
            this.hideChartProgress();
        }
    }
    
    generateChartFromDownload(audioPath, songTitle) {
            this.generateChart(audioPath, songTitle);
    }
    
    showChartProgress() {
        const progressContainer = document.getElementById('chart-progress');
        progressContainer.style.display = 'block';
        progressContainer.querySelector('.progress-text').textContent = '分析中...';
    }

    hideChartProgress() {
        document.getElementById('chart-progress').style.display = 'none';
    }
    
    handleChartProgress(data) {
        const progressContainer = document.getElementById('chart-progress');
        const progressFill = progressContainer.querySelector('.progress-fill');
        const progressText = progressContainer.querySelector('.progress-text');
        
        if (data.status === 'analyzing') {
            progressFill.style.width = `${data.progress || 50}%`;
            progressText.textContent = data.message || '分析中...';
        } else if (data.status === 'generating') {
            progressFill.style.width = `${data.progress || 75}%`;
            progressText.textContent = data.message || '生成譜面中...';
        } else if (data.status === 'completed') {
            progressContainer.style.display = 'none';
            this.showNotification('譜面生成完成！', 'success');
            
            // 重新載入譜面列表
            this.loadCharts();
        } else if (data.status === 'failed') {
            progressContainer.style.display = 'none';
            this.showNotification(`生成譜面失敗: ${data.error}`, 'error');
        }
    }
    
    async loadCharts() {
        try {
            const response = await fetch('/api/charts');
            const data = await response.json();
            
            if (data.success) {
                this.displayCharts(data.charts, 'charts-list');
            } else {
                throw new Error(data.error || 'Failed to load charts');
            }
        } catch (error) {
            console.error('Error loading charts:', error);
            this.showNotification('載入譜面失敗', 'error');
        }
    }
    
    displayCharts(charts, containerId) {
        const container = document.getElementById(containerId);
        const toggleSelectBtn = document.getElementById('toggle-select-charts-btn');
        const deleteSelectedBtn = document.getElementById('delete-selected-charts-btn');
        
        // 清空選取狀態
        this.selectedCharts.clear();
        
        if (charts.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>沒有找到譜面</p><p>請先生成一些譜面</p></div>';
            if (toggleSelectBtn) toggleSelectBtn.style.display = 'none';
            if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'none';
            return;
        }
        
        // 顯示控制按鈕並重置切換按鈕狀態
        if (toggleSelectBtn) {
            toggleSelectBtn.style.display = 'inline-flex';
            toggleSelectBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
        }
        if (deleteSelectedBtn) deleteSelectedBtn.style.display = 'inline-flex';
        
        container.innerHTML = charts.map(chart => `
            <div class="chart-card" data-path="${chart.path}">
                <div class="chart-select">
                    <input type="checkbox" id="chart-${chart.path}" onchange="app.toggleChartSelection('${chart.path}', this.checked)">
                    <label for="chart-${chart.path}" class="select-label">選取</label>
                </div>
                <h4>${chart.title}</h4>
                <p>BPM: ${chart.bpm || '未知'}</p>
                <p>音符數: ${chart.note_count || '未知'}</p>
                <p>難度: ${chart.difficulty || '未知'}</p>
                <div class="chart-actions">
                    <button class="btn-primary" onclick="app.playChart('${chart.path}')">
                        <i class="fas fa-play"></i> 開始遊戲
                    </button>
                    <button class="btn-danger" onclick="app.deleteChart('${chart.path}', '${chart.title}')">
                        <i class="fas fa-trash-alt"></i> 刪除
                    </button>
                </div>
            </div>
        `).join('');
        
        this.updateSelectedChartsCount();
    }
    
    // 切換單個譜面的選取狀態
    toggleChartSelection(chartPath, isSelected) {
        if (isSelected) {
            this.selectedCharts.add(chartPath);
        } else {
            this.selectedCharts.delete(chartPath);
        }
        
        // 更新卡片樣式
        const chartCard = document.querySelector(`.chart-card[data-path="${chartPath}"]`);
        if (chartCard) {
            if (isSelected) {
                chartCard.classList.add('selected');
            } else {
                chartCard.classList.remove('selected');
            }
        }
        
        this.updateSelectedChartsCount();
    }
    
    // 切換單個音樂檔案的選取狀態
    toggleAudioFileSelection(audioPath, isSelected) {
        if (isSelected) {
            this.selectedAudioFiles.add(audioPath);
        } else {
            this.selectedAudioFiles.delete(audioPath);
        }
        
        // 更新卡片樣式
        const audioCard = document.querySelector(`.file-card[data-path="${audioPath}"]`);
        if (audioCard) {
            if (isSelected) {
                audioCard.classList.add('selected');
            } else {
                audioCard.classList.remove('selected');
            }
        }
        
        this.updateSelectedAudioFilesCount();
    }
    
    playChart(chartFile) {
        console.log('Playing chart:', chartFile);
        // 跳转到独立的游戏页面
        window.location.href = `/play.html?chart=${encodeURIComponent(chartFile)}`;
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        const container = document.getElementById('notifications');
        container.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    showLoading(text = '載入中...') {
        const loading = document.getElementById('loading');
        const loadingText = loading.querySelector('.loading-text');
        loadingText.textContent = text;
        loading.style.display = 'flex';
    }
    
    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }
    
    // 刪除單個音樂檔案
    async deleteAudioFile(audioPath, songTitle) {
        if (!confirm(`確定要刪除音樂「${songTitle}」嗎？\n\n注意：這也會刪除相關的譜面檔案。`)) {
            return;
        }
        
        try {
            const response = await fetch('/api/delete_audio', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ audio_path: audioPath })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`已刪除音樂「${songTitle}」`, 'success');
                this.loadAudioFiles(); // 重新載入音樂列表
                this.loadCharts(); // 重新載入譜面列表（因為相關譜面也被刪除了）
            } else {
                const error = await response.json();
                throw new Error(error.error || '刪除失敗');
            }
        } catch (error) {
            console.error('Delete audio error:', error);
            this.showNotification(`刪除失敗: ${error.message}`, 'error');
        }
    }
    
    // 刪除單個譜面
    async deleteChart(chartPath, chartTitle) {
        if (!confirm(`確定要刪除譜面「${chartTitle}」嗎？`)) {
            return;
        }
        
        try {
            const response = await fetch('/api/delete_chart', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ chart_path: chartPath })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`已刪除譜面「${chartTitle}」`, 'success');
                this.loadCharts(); // 重新載入譜面列表
            } else {
                const error = await response.json();
                throw new Error(error.error || '刪除失敗');
            }
        } catch (error) {
            console.error('Delete chart error:', error);
            this.showNotification(`刪除失敗: ${error.message}`, 'error');
        }
    }
    
    // 選取所有譜面
    selectAllCharts() {
        const chartCards = document.querySelectorAll('.chart-card');
        chartCards.forEach(card => {
            const checkbox = card.querySelector('input[type="checkbox"]');
            const chartPath = card.dataset.path;
            if (checkbox && chartPath) {
                checkbox.checked = true;
                card.classList.add('selected');
                this.selectedCharts.add(chartPath);
            }
        });
        this.updateSelectedChartsCount();
    }

    // 取消選取所有譜面
    deselectAllCharts() {
        const chartCards = document.querySelectorAll('.chart-card');
        chartCards.forEach(card => {
            const checkbox = card.querySelector('input[type="checkbox"]');
            if (checkbox) {
                checkbox.checked = false;
                card.classList.remove('selected');
            }
        });
        this.selectedCharts.clear();
        this.updateSelectedChartsCount();
    }

    // 切換全選/取消全選
    toggleSelectAllCharts() {
        const chartCards = document.querySelectorAll('.chart-card');
        const toggleBtn = document.getElementById('toggle-select-charts-btn');
        
        // 檢查是否已經全選
        const isAllSelected = chartCards.length > 0 && this.selectedCharts.size === chartCards.length;
        
        if (isAllSelected) {
            // 如果已經全選，則取消全選
            this.deselectAllCharts();
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
            }
        } else {
            // 如果沒有全選，則全選
            this.selectAllCharts();
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fas fa-square"></i> 取消全選';
            }
        }
    }

    // 刪除選取的譜面
    async deleteSelectedCharts() {
        if (this.selectedCharts.size === 0) {
            this.showNotification('請先選取要刪除的譜面', 'warning');
            return;
        }

        if (!confirm(`確定要刪除選取的 ${this.selectedCharts.size} 個譜面嗎？\n\n注意：此操作無法復原！`)) {
            return;
        }

        try {
            const chartPathsToDelete = Array.from(this.selectedCharts);
            const response = await fetch('/api/delete_charts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ chart_paths: chartPathsToDelete })
            });

            if (response.ok) {
                const data = await response.json();
                this.showNotification(`已刪除 ${data.deleted_count} 個譜面`, 'success');
                this.loadCharts();
                this.selectedCharts.clear();
                this.updateSelectedChartsCount();
            } else {
                const error = await response.json();
                throw new Error(error.error || '刪除失敗');
            }
        } catch (error) {
            console.error('Delete selected charts error:', error);
            this.showNotification(`刪除失敗: ${error.message}`, 'error');
        }
    }

    // 更新選取計數器
    updateSelectedChartsCount() {
        const count = this.selectedCharts.size;
        const countDisplay = document.getElementById('selected-count-display');
        const countSpan = document.getElementById('selected-charts-count');
        const deleteBtn = document.getElementById('delete-selected-charts-btn');
        const toggleBtn = document.getElementById('toggle-select-charts-btn');
        
        if (countSpan) {
            countSpan.textContent = count;
        }
        
        if (countDisplay) {
            countDisplay.style.display = count > 0 ? 'inline-flex' : 'none';
        }
        
        if (deleteBtn) {
            deleteBtn.style.display = count > 0 ? 'inline-flex' : 'none';
        }
        
        // 更新切換按鈕的狀態
        if (toggleBtn) {
            const chartCards = document.querySelectorAll('.chart-card');
            const isAllSelected = chartCards.length > 0 && this.selectedCharts.size === chartCards.length;
            
            if (isAllSelected) {
                toggleBtn.innerHTML = '<i class="fas fa-square"></i> 取消全選';
            } else {
                toggleBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
            }
        }
    }
    
    // 更新音樂檔案選取計數器
    updateSelectedAudioFilesCount() {
        const count = this.selectedAudioFiles.size;
        const countDisplay = document.getElementById('selected-audio-count-display');
        const countSpan = document.getElementById('selected-audio-count');
        const deleteBtn = document.getElementById('delete-selected-audio-btn');
        const toggleBtn = document.getElementById('toggle-select-audio-btn');
        
        if (countSpan) {
            countSpan.textContent = count;
        }
        
        if (countDisplay) {
            countDisplay.style.display = count > 0 ? 'inline-flex' : 'none';
        }
        
        if (deleteBtn) {
            deleteBtn.style.display = count > 0 ? 'inline-flex' : 'none';
        }
        
        // 更新切換按鈕的狀態
        if (toggleBtn) {
            const audioCards = document.querySelectorAll('.file-card');
            const isAllSelected = audioCards.length > 0 && this.selectedAudioFiles.size === audioCards.length;
            
            if (isAllSelected) {
                toggleBtn.innerHTML = '<i class="fas fa-square"></i> 取消全選';
            } else {
                toggleBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
            }
        }
    }
    
    // 全選音樂檔案
    selectAllAudioFiles() {
        const audioCards = document.querySelectorAll('.file-card');
        audioCards.forEach(card => {
            const audioPath = card.dataset.path;
            const checkbox = card.querySelector('input[type="checkbox"]');
            if (checkbox && !checkbox.checked) {
                checkbox.checked = true;
                this.selectedAudioFiles.add(audioPath);
                card.classList.add('selected');
            }
        });
        this.updateSelectedAudioFilesCount();
    }
    
    // 取消全選音樂檔案
    deselectAllAudioFiles() {
        const audioCards = document.querySelectorAll('.file-card');
        audioCards.forEach(card => {
            const audioPath = card.dataset.path;
            const checkbox = card.querySelector('input[type="checkbox"]');
            if (checkbox && checkbox.checked) {
                checkbox.checked = false;
                this.selectedAudioFiles.delete(audioPath);
                card.classList.remove('selected');
            }
        });
        this.updateSelectedAudioFilesCount();
    }
    
    // 切換全選/取消全選音樂檔案
    toggleSelectAllAudioFiles() {
        const audioCards = document.querySelectorAll('.file-card');
        const toggleBtn = document.getElementById('toggle-select-audio-btn');
        
        // 檢查是否已經全選
        const isAllSelected = audioCards.length > 0 && this.selectedAudioFiles.size === audioCards.length;
        
        if (isAllSelected) {
            // 如果已經全選，則取消全選
            this.deselectAllAudioFiles();
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fas fa-check-square"></i> 全選';
            }
        } else {
            // 如果沒有全選，則全選
            this.selectAllAudioFiles();
            if (toggleBtn) {
                toggleBtn.innerHTML = '<i class="fas fa-square"></i> 取消全選';
            }
        }
    }
    
    // 刪除選取的音樂檔案
    async deleteSelectedAudioFiles() {
        if (this.selectedAudioFiles.size === 0) {
            this.showNotification('請先選取要刪除的音樂檔案', 'warning');
            return;
        }

        if (!confirm(`確定要刪除選取的 ${this.selectedAudioFiles.size} 個音樂檔案嗎？\n\n注意：這也會刪除相關的譜面檔案，此操作無法復原！`)) {
            return;
        }

        try {
            const audioPathsToDelete = Array.from(this.selectedAudioFiles);
            const response = await fetch('/api/delete_audio_files', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ audio_paths: audioPathsToDelete })
            });

            if (response.ok) {
                const data = await response.json();
                this.showNotification(`已刪除 ${data.deleted_count} 個音樂檔案`, 'success');
                this.loadAudioFiles();
                this.loadCharts(); // 重新載入譜面，因為相關譜面也被刪除了
                this.selectedAudioFiles.clear();
                this.updateSelectedAudioFilesCount();
            } else {
                const error = await response.json();
                throw new Error(error.error || '刪除失敗');
            }
        } catch (error) {
            console.error('Delete selected audio files error:', error);
            this.showNotification(`刪除失敗: ${error.message}`, 'error');
        }
    }
}

// 初始化應用
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new RhythmGameApp();
}); 