// 節奏遊戲 - 遊戲頁面 JavaScript
// Rhythm Game - Play Page JavaScript

class RhythmGame {
    constructor() {
        this.socket = null;
        this.gameState = {
            isPlaying: false,
            isPaused: false,
            isWaitingForStart: false,
            isCountingDown: false,
            chartData: null,
            currentTime: 0,
            notes: [],
            stats: {
                score: 0,
                combo: 0,
                maxCombo: 0,
                accuracy: 100,
                judgments: { perfect: 0, great: 0, good: 0, miss: 0 }
            }
        };
        this.gameCanvas = null;
        this.gameCtx = null;
        this.gameAnimationId = null;
        this.audio = null;
        this.keyStates = { d: false, f: false, j: false, k: false };
        this.config = {};
        this.gameStartTime = 0;
        this.lastDebugSecond = 0;
        this.countdownTimer = null;
        this.chartPath = null;
        this.countdownStartTime = 0; // 新增：倒計時開始時間
        
        this.init();
    }

    init() {
        this.initSocket();
        this.initDOMReferences();
        this.initEventListeners();
        this.initGamePage();
        this.loadConfig();
        this.getChartFromURL();
    }

    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
        });

        this.socket.on('game_started', (data) => {
            this.handleGameStarted(data);
        });

        this.socket.on('note_judgment', (data) => {
            this.handleNoteJudgment(data);
        });

        this.socket.on('game_paused', () => {
            this.handleGamePaused();
        });

        this.socket.on('game_resumed', () => {
            this.handleGameResumed();
        });

        this.socket.on('game_ended', (data) => {
            this.handleGameEnded(data);
        });

        this.socket.on('game_error', (data) => {
            console.error('Game error:', data);
            this.showNotification(data.error || '遊戲錯誤', 'error');
        });

        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.showNotification('連接伺服器失敗', 'error');
        });
    }

    initDOMReferences() {
        // Game elements
        this.gameCanvas = document.getElementById('game-canvas');
        this.gameCtx = this.gameCanvas.getContext('2d');
        
        // UI elements
        this.scoreElement = document.getElementById('game-score');
        this.comboElement = document.getElementById('game-combo');
        this.accuracyElement = document.getElementById('game-accuracy');
        this.songTitleElement = document.getElementById('song-title');
        this.songBpmElement = document.getElementById('song-bpm');
        this.gameTimeElement = document.getElementById('game-time');
        this.gameProgressElement = document.getElementById('game-progress');
        
        // Control buttons
        this.pauseBtn = document.getElementById('pause-btn');
        this.restartBtn = document.getElementById('restart-btn');
        this.quitBtn = document.getElementById('quit-btn');
        
        // Game state overlays
        this.gameResults = document.getElementById('game-results');
        this.gamePause = document.getElementById('game-pause');
        
        // Judgment display
        this.judgmentDisplay = document.getElementById('judgment-display');
        this.judgmentText = document.getElementById('judgment-text');
        this.comboDisplay = document.getElementById('combo-display');
        
        // Key hints
        this.keyHints = document.querySelectorAll('.key-hint');
        
        // Result elements
        this.finalGrade = document.getElementById('final-grade');
        this.finalScore = document.getElementById('final-score');
        this.finalCombo = document.getElementById('final-combo');
        this.finalAccuracy = document.getElementById('final-accuracy');
        this.perfectCount = document.getElementById('perfect-count');
        this.greatCount = document.getElementById('great-count');
        this.goodCount = document.getElementById('good-count');
        this.missCount = document.getElementById('miss-count');
        
        // Result buttons
        this.restartGameBtn = document.getElementById('restart-game-btn');
        this.backToChartsBtn = document.getElementById('back-to-charts-btn');
        
        // Pause buttons
        this.resumeBtn = document.getElementById('resume-btn');
        this.restartPauseBtn = document.getElementById('restart-pause-btn');
        this.quitPauseBtn = document.getElementById('quit-pause-btn');
    }

    initEventListeners() {
        // Window events
        window.addEventListener('resize', () => this.resizeCanvas());
        window.addEventListener('keydown', (e) => this.handleKeyDown(e));
        window.addEventListener('keyup', (e) => this.handleKeyUp(e));
        window.addEventListener('beforeunload', () => {
            if (this.gameState.isPlaying) {
                this.socket.emit('end_game');
            }
        });

        // Game control buttons
        this.pauseBtn.addEventListener('click', () => this.togglePause());
        this.restartBtn.addEventListener('click', () => this.restartGame());
        this.quitBtn.addEventListener('click', () => this.quitGame());

        // Result buttons
        this.restartGameBtn.addEventListener('click', () => this.restartGame());
        this.backToChartsBtn.addEventListener('click', () => this.backToChartSelection());

        // Pause buttons
        this.resumeBtn.addEventListener('click', () => this.resumeGame());
        this.restartPauseBtn.addEventListener('click', () => this.restartGame());
        this.quitPauseBtn.addEventListener('click', () => this.quitGame());
    }

    initGamePage() {
        this.resizeCanvas();
        this.resetGameState();
        this.resetKeyHints();
        this.resetJudgmentDisplay();
    }

    resizeCanvas() {
        if (!this.gameCanvas) return;
        
        const container = this.gameCanvas.parentElement;
        const rect = container.getBoundingClientRect();
        
        // 限制遊戲區域寬度，使軌道更窄
        const maxGameWidth = 400;
        const gameWidth = Math.min(rect.width, maxGameWidth);
        const gameHeight = rect.height;
        
        this.gameCanvas.width = gameWidth;
        this.gameCanvas.height = gameHeight;
        
        // Set canvas style to match container but centered
        this.gameCanvas.style.width = gameWidth + 'px';
        this.gameCanvas.style.height = gameHeight + 'px';
        
        // 儲存遊戲區域尺寸供渲染使用
        this.gameArea = {
            width: gameWidth,
            height: gameHeight,
            laneWidth: gameWidth / 4,
            judgmentY: gameHeight - 120
        };
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            this.config = await response.json();
            console.log('Loaded config:', this.config);
        } catch (error) {
            console.error('Error loading config:', error);
            // Use default config
            this.config = {
                note_speed: 300,
                perfect_tolerance: 0.05,
                great_tolerance: 0.1,
                good_tolerance: 0.15,
                debug_mode: false,  // Turn off debug mode
                audio_delay: 0.15,
                visual_offset: 0.0
            };
        }
    }

    getChartFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        this.chartPath = urlParams.get('chart');
        
        if (this.chartPath) {
            this.startGame(this.chartPath);
        } else {
            this.showNotification('未指定譜面檔案', 'error');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        }
    }

    async startGame(chartPath) {
        try {
            this.showLoading('載入譜面中...');
            
            // Load chart data
            // 這裡不要再次編碼，避免 %2F 造成伺服器無法識別路徑
            const response = await fetch(`/api/chart/${chartPath}`);
            if (!response.ok) {
                throw new Error('Failed to load chart');
            }
            
            const responseData = await response.json();
            if (!responseData.success) {
                throw new Error(responseData.error || 'Failed to load chart');
            }
            
            const chartData = responseData.chart;
            this.gameState.chartData = chartData;
            
            // 載入音符資料到遊戲狀態中（提前載入）
            if (chartData && chartData.notes) {
                this.gameState.notes = chartData.notes.slice(); // Make a copy
                console.log(`Loaded ${this.gameState.notes.length} notes for preview`);
            }
            
            // Update UI with chart info
            this.songTitleElement.textContent = chartData.song_title || '未知歌曲';
            this.songBpmElement.textContent = `BPM: ${chartData.bpm || 120}`;
            
            // Load audio
            await this.loadGameAudio(chartData, false);
            
            this.hideLoading();
            
            this.gameState.isWaitingForStart = true;
            if (!this.gameAnimationId) {
                this.startGameLoop();
            }
            
        } catch (error) {
            console.error('Error starting game:', error);
            this.hideLoading();
            this.showNotification('載入譜面失敗', 'error');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        }
    }

    resetGameState() {
        this.gameState.isPlaying = false;
        this.gameState.isPaused = false;
        this.gameState.isWaitingForStart = false;
        this.gameState.isCountingDown = false;
        this.gameState.currentTime = 0;
        this.gameState.notes = [];
        this.gameState.stats = {
            score: 0,
            combo: 0,
            maxCombo: 0,
            accuracy: 100,
            judgments: { perfect: 0, great: 0, good: 0, miss: 0 }
        };
        
        if (this.gameAnimationId) {
            cancelAnimationFrame(this.gameAnimationId);
            this.gameAnimationId = null;
        }
        
        if (this.audio) {
            this.audio.pause();
            this.audio.currentTime = 0;
        }
        
        this.gameStartTime = 0;
        this.lastDebugSecond = 0;
        this.countdownStartTime = 0;
        
        // Reset UI
        this.updateGameUI();
        this.updateGameProgress();
        
        // Hide overlays
        this.gameResults.style.display = 'none';
        this.gamePause.style.display = 'none';
    }

    resetKeyHints() {
        this.keyHints.forEach(hint => {
            hint.classList.remove('active', 'hit-effect');
        });
    }

    resetJudgmentDisplay() {
        this.judgmentText.textContent = '';
        this.judgmentText.className = 'judgment-text';
        this.comboDisplay.textContent = '';
        this.comboDisplay.classList.remove('show');
    }

    handleGameStarted(data) {
        console.log('Game started:', data);
        this.gameState.isPlaying = true;
        this.gameState.isWaitingForStart = false;
        this.gameState.isCountingDown = false;
        
        // 音符已經在 startGame 時載入，這裡不需要重新載入
        // 但要確保資料同步
        if (data.chart_data && data.chart_data.notes && this.gameState.notes.length === 0) {
            this.gameState.notes = data.chart_data.notes.slice();
            console.log(`Backup loaded ${this.gameState.notes.length} notes from server`);
        }
        
        this.gameStartTime = Date.now();
        
        // Hide countdown overlay
        
        // Start audio
        if (this.audio) {
            this.audio.currentTime = 0;
            this.audio.play().catch(error => {
                console.error('Error playing audio:', error);
            });
        }
        
        // Game loop is already running from countdown, just continue
        if (!this.gameAnimationId) {
            this.startGameLoop();
        }
        
    }

    async loadGameAudio(chartData, play = true) {
        try {
            if (this.audio) {
                this.audio.pause();
                this.audio = null;
            }
            
            const audioUrl = `/api/audio/${encodeURIComponent(chartData.audio_file)}`;
            this.audio = new Audio(audioUrl);
            
            return new Promise((resolve, reject) => {
                this.audio.addEventListener('loadeddata', () => {
                    console.log('Audio loaded successfully');
                    if (play) {
                        this.audio.play().then(resolve).catch(reject);
                    } else {
                        resolve();
                    }
                });
                
                this.audio.addEventListener('error', (e) => {
                    console.error('Audio load error:', e);
                    reject(new Error('Failed to load audio'));
                });
                
                this.audio.addEventListener('ended', () => {
                    if (this.gameState.isPlaying) {
                        this.endGame();
                    }
                });
            });
        } catch (error) {
            console.error('Error loading audio:', error);
            throw error;
        }
    }

    startGameLoop() {
        const gameLoop = (timestamp) => {
            if (this.gameState.isPlaying && !this.gameState.isPaused) {
                this.updateGame();
                this.renderGame();
            } else if (this.gameState.isCountingDown || this.gameState.isWaitingForStart) {
                // 在倒計時期間也進行渲染
                this.updatePreviewGame();
                this.renderGame();
            }
            
            if (this.gameState.isPlaying || this.gameState.isCountingDown || this.gameState.isWaitingForStart) {
                this.gameAnimationId = requestAnimationFrame(gameLoop);
            }
        };
        
        this.gameAnimationId = requestAnimationFrame(gameLoop);
    }

    updateGame() {
        if (!this.gameState.isPlaying || this.gameState.isPaused) return;
        
        // Update current time
        if (this.audio) {
            this.gameState.currentTime = this.audio.currentTime;
        } else {
            this.gameState.currentTime = (Date.now() - this.gameStartTime) / 1000;
        }
        
        // Check for auto-miss notes
        this.checkAutoMiss();
        
        // Update UI
        this.updateGameUI();
        this.updateGameProgress();
        
        // Debug output
        if (this.config.debug_mode) {
            const currentSecond = Math.floor(this.gameState.currentTime);
            if (currentSecond !== this.lastDebugSecond) {
                console.log(`Game time: ${this.gameState.currentTime.toFixed(2)}s, Notes remaining: ${this.gameState.notes.length}`);
                
                // Show next few notes
                const upcomingNotes = this.gameState.notes
                    .filter(note => note.time > this.gameState.currentTime)
                    .slice(0, 5);
                console.log('Upcoming notes:', upcomingNotes);
                
                this.lastDebugSecond = currentSecond;
            }
        }
    }

    // 新增：預覽模式的遊戲更新
    updatePreviewGame() {
        const PREVIEW_DURATION = 5.0; // 5秒準備時間
        if (this.gameState.isCountingDown) {
            // 倒計時期間，時間從負數開始，慢慢接近0
            // 讓倒計時結束時，遊戲時間正好是0
            const elapsed = (Date.now() - this.countdownStartTime) / 1000;
            this.gameState.currentTime = -PREVIEW_DURATION + elapsed;
        } else if (this.gameState.isWaitingForStart) {
            // 等待開始時，固定顯示，讓玩家看到即將到來的音符
            this.gameState.currentTime = -PREVIEW_DURATION;
        }
        
        // 確保預覽時間不超過0（避免在真正開始前時間變成正數）
        if (this.gameState.currentTime > 0) {
            this.gameState.currentTime = 0;
        }
    }

    checkAutoMiss() {
        const currentTime = this.gameState.currentTime;
        const goodTolerance = this.config.good_tolerance || 0.15;
        const missThreshold = goodTolerance + 0.1; // Add extra buffer
        
        // Check for notes that should be auto-missed
        const notesToRemove = [];
        
        this.gameState.notes.forEach((note, index) => {
            const timeDiff = currentTime - note.time;
            
            if (timeDiff > missThreshold) {
                // Mark this note for removal
                notesToRemove.push(index);
                
                // Auto-miss this note (send to server for statistics)
                this.socket.emit('auto_miss', {
                    lane: note.lane,
                    note_time: note.time
                });
            }
        });
        
        // Remove auto-missed notes in reverse order to maintain correct indices
        notesToRemove.reverse().forEach(index => {
            this.gameState.notes.splice(index, 1);
        });
    }

    updateGameProgress() {
        if (!this.gameState.chartData || !this.audio) return;
        
        const duration = this.audio.duration || 0;
        const currentTime = this.gameState.currentTime;
        
        if (duration > 0) {
            const progress = (currentTime / duration) * 100;
            this.gameProgressElement.style.width = `${Math.min(progress, 100)}%`;
            
            const formatTime = (time) => {
                const minutes = Math.floor(time / 60);
                const seconds = Math.floor(time % 60);
                return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            };
            
            this.gameTimeElement.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
        }
    }

    renderGame() {
        if (!this.gameCtx || !this.gameArea) return;
        
        const canvas = this.gameCanvas;
        const ctx = this.gameCtx;
        const { width, height, laneWidth, judgmentY } = this.gameArea;
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        
        // 繪製背景漸變
        this.drawGameBackground(ctx, width, height);
        
        // Draw game elements
        this.drawLanes(ctx, width, height);
        this.drawJudgmentLine(ctx, width, height);
        this.drawNotes(ctx, width, height);
        
        // 在倒計時或等待狀態時不顯示準備覆蓋層（因為現在背景是半透明的）
        // Draw preparation overlay if waiting for start
        if (this.gameState.isWaitingForStart) {
            this.drawPreparationOverlay(ctx, width, height);
        }
    }

    drawGameBackground(ctx, width, height) {
        // 繪製遊戲背景
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, 'rgba(0, 0, 0, 0.9)');
        gradient.addColorStop(0.3, 'rgba(20, 20, 40, 0.8)');
        gradient.addColorStop(0.7, 'rgba(20, 20, 40, 0.8)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0.9)');
        
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
        
        // 添加一些細微的紋理效果
        ctx.fillStyle = 'rgba(100, 181, 246, 0.03)';
        for (let i = 0; i < height; i += 4) {
            ctx.fillRect(0, i, width, 1);
        }
    }

    drawLanes(ctx, width, height) {
        const laneWidth = this.gameArea.laneWidth;
        
        // Draw lane separators with glow effect
        ctx.strokeStyle = 'rgba(100, 181, 246, 0.4)';
        ctx.lineWidth = 2;
        ctx.shadowColor = 'rgba(100, 181, 246, 0.3)';
        ctx.shadowBlur = 5;
        
        for (let i = 1; i < 4; i++) {
            const x = i * laneWidth;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        
        // Reset shadow
        ctx.shadowBlur = 0;
        
        // Draw lane backgrounds when keys are pressed
        const keyStatesArray = [this.keyStates.d, this.keyStates.f, this.keyStates.j, this.keyStates.k];
        
        for (let i = 0; i < 4; i++) {
            if (keyStatesArray[i]) {
                const x = i * laneWidth;
                
                // Create gradient for pressed lane
                const gradient = ctx.createLinearGradient(x, 0, x + laneWidth, 0);
                gradient.addColorStop(0, 'rgba(100, 181, 246, 0.1)');
                gradient.addColorStop(0.5, 'rgba(100, 181, 246, 0.2)');
                gradient.addColorStop(1, 'rgba(100, 181, 246, 0.1)');
                
                ctx.fillStyle = gradient;
                ctx.fillRect(x, 0, laneWidth, height);
            }
        }
    }

    drawJudgmentLine(ctx, width, height) {
        const judgmentY = this.gameArea.judgmentY;
        
        // Main judgment line
        ctx.strokeStyle = '#64b5f6';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(0, judgmentY);
        ctx.lineTo(width, judgmentY);
        ctx.stroke();
        
        // Add glow effect
        ctx.shadowColor = '#64b5f6';
        ctx.shadowBlur = 15;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.shadowBlur = 0;
        
        // Add judgment zone indicator
        ctx.fillStyle = 'rgba(100, 181, 246, 0.1)';
        ctx.fillRect(0, judgmentY - 25, width, 50);
        
        // Add subtle border lines
        ctx.strokeStyle = 'rgba(100, 181, 246, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, judgmentY - 25);
        ctx.lineTo(width, judgmentY - 25);
        ctx.moveTo(0, judgmentY + 25);
        ctx.lineTo(width, judgmentY + 25);
        ctx.stroke();
    }

    drawNotes(ctx, width, height) {
        const laneWidth = this.gameArea.laneWidth;
        const noteHeight = 15; // 稍微縮小音符高度
        const noteWidth = laneWidth - 20; // 音符寬度，留出邊距
        const judgmentY = this.gameArea.judgmentY;
        const noteSpeed = this.config.note_speed || 300;
        const currentTime = this.gameState.currentTime;
        const visualOffset = this.config.visual_offset || 0.0;
        
        // 繪製音符
        this.gameState.notes.forEach(note => {
            const adjustedTime = note.time + visualOffset;
            const timeDiff = adjustedTime - currentTime;
            const noteY = judgmentY - (timeDiff * noteSpeed);
            
            // Only draw notes that are visible
            if (noteY > -noteHeight && noteY < height + noteHeight) {
                const noteX = note.lane * laneWidth + 10; // 添加邊距
                
                // 根據時間差決定音符顏色和效果
                let noteColor = '#64b5f6';
                let glowColor = '#64b5f6';
                let glowIntensity = 0.3;
                
                const perfectTolerance = this.config.perfect_tolerance || 0.05;
                const greatTolerance = this.config.great_tolerance || 0.1;
                const goodTolerance = this.config.good_tolerance || 0.15;
                
                if (Math.abs(timeDiff) <= perfectTolerance) {
                    noteColor = '#FFD700';
                    glowColor = '#FFD700';
                    glowIntensity = 0.8;
                } else if (Math.abs(timeDiff) <= greatTolerance) {
                    noteColor = '#4CAF50';
                    glowColor = '#4CAF50';
                    glowIntensity = 0.6;
                } else if (Math.abs(timeDiff) <= goodTolerance) {
                    noteColor = '#2196F3';
                    glowColor = '#2196F3';
                    glowIntensity = 0.4;
                }
                
                // 繪製音符陰影
                ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
                ctx.fillRect(noteX + 2, noteY + 2, noteWidth, noteHeight);
                
                // 繪製音符主體
                ctx.fillStyle = noteColor;
                ctx.fillRect(noteX, noteY, noteWidth, noteHeight);
                
                // 添加漸變效果
                const gradient = ctx.createLinearGradient(noteX, noteY, noteX, noteY + noteHeight);
                gradient.addColorStop(0, 'rgba(255, 255, 255, 0.3)');
                gradient.addColorStop(1, 'rgba(0, 0, 0, 0.2)');
                ctx.fillStyle = gradient;
                ctx.fillRect(noteX, noteY, noteWidth, noteHeight);
                
                // 添加邊框
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
                ctx.lineWidth = 1;
                ctx.strokeRect(noteX, noteY, noteWidth, noteHeight);
                
                // 添加發光效果
                if (glowIntensity > 0.3) {
                    ctx.shadowColor = glowColor;
                    ctx.shadowBlur = 10 * glowIntensity;
                    ctx.fillStyle = noteColor;
                    ctx.fillRect(noteX, noteY, noteWidth, noteHeight);
                    ctx.shadowBlur = 0;
                }
            }
        });
    }

    handleKeyDown(e) {
        if (e.repeat) return;
        
        const key = e.key.toLowerCase();
        
        // Handle special keys
        if (key === 'enter' && this.gameState.isWaitingForStart) {
            this.gameState.isWaitingForStart = false;
            this.gameState.isCountingDown = true;
            this.countdownStartTime = Date.now();
    
            setTimeout(() => {
                this.actuallyStartGame();
            }, 5000); // 5 seconds wait
    
            return;
        }
        
        if (key === 'escape') {
            if (this.gameState.isPlaying) {
                this.togglePause();
            }
            return;
        }
        
        if (key === 'r' || key === 'R') {
            // R key for restart
            this.restartGame();
            return;
        }
        
        // Handle game keys
        const lane = this.getKeyLane(key);
        if (lane !== -1) {
            this.keyStates[key] = true;
            this.updateKeyHint(key, true);
            
            if (this.gameState.isPlaying && !this.gameState.isPaused) {
                this.hitNote(lane);
            }
        }
    }

    handleKeyUp(e) {
        const key = e.key.toLowerCase();
        const lane = this.getKeyLane(key);
        if (lane !== -1) {
            this.keyStates[key] = false;
            this.updateKeyHint(key, false);
        }
    }

    getKeyLane(key) {
        const keyMap = { 'd': 0, 'f': 1, 'j': 2, 'k': 3 };
        return keyMap[key] !== undefined ? keyMap[key] : -1;
    }

    updateKeyHint(key, active) {
        const lane = this.getKeyLane(key);
        if (lane !== -1 && this.keyHints[lane]) {
            if (active) {
                this.keyHints[lane].classList.add('active');
            } else {
                this.keyHints[lane].classList.remove('active');
            }
        }
    }

    hitNote(lane) {
        const currentTime = this.gameState.currentTime;
        
        // Find the closest note in this lane
        let closestNote = null;
        let closestDistance = Infinity;
        
        this.gameState.notes.forEach(note => {
            if (note.lane === lane) {
                const distance = Math.abs(currentTime - note.time);
                if (distance < closestDistance) {
                    closestDistance = distance;
                    closestNote = note;
                }
            }
        });
        
        if (closestNote) {
            // Send hit to server
            this.socket.emit('hit_note', {
                lane: lane,
                time: currentTime,
                note_time: closestNote.time
            });
        }
    }

    handleNoteJudgment(data) {
        console.log('Note judgment:', data);
        
        // Update stats from the response
        if (data.score !== undefined) this.gameState.stats.score = data.score;
        if (data.combo !== undefined) {
            const oldCombo = this.gameState.stats.combo;
            this.gameState.stats.combo = data.combo;
            
            // Debug logging for combo changes
            if (data.judgment === 'miss' && data.combo === 0) {
                console.log(`Combo reset to 0 due to miss (was ${oldCombo})`);
            } else if (data.combo > oldCombo) {
                console.log(`Combo increased from ${oldCombo} to ${data.combo}`);
            }
        }
        if (data.accuracy !== undefined) this.gameState.stats.accuracy = data.accuracy;
        if (data.judgments !== undefined) this.gameState.stats.judgments = data.judgments;
        
        // Update max combo separately if provided
        if (data.max_combo !== undefined) {
            this.gameState.stats.maxCombo = data.max_combo;
        } else {
            // Fallback: update max combo based on current combo
            this.gameState.stats.maxCombo = Math.max(this.gameState.stats.maxCombo, data.combo || 0);
        }
        
        // Show judgment effect
        this.showJudgmentEffect(data.lane, data.judgment);
        this.showCentralJudgment(data.judgment);
        // Trigger lane hit visual only on successful hits
        if (data.hit) {
            this.showLaneHitEffect(data.lane);
        }
        
        // Remove the hit note from display if it was successfully hit
        if (data.hit && data.note_time !== undefined) {
            this.gameState.notes = this.gameState.notes.filter(note => {
                return !(note.lane === data.lane && Math.abs(note.time - data.note_time) < 0.001);
            });
        }
        
        // Update UI
        this.updateGameUI();
        this.updateComboDisplay();
    }

    showJudgmentEffect(lane, judgment) {
        // This could be enhanced with more visual effects
        console.log(`Lane ${lane}: ${judgment}`);
    }

    showCentralJudgment(judgment) {
        this.judgmentText.textContent = judgment.toUpperCase();
        this.judgmentText.className = `judgment-text ${judgment.toLowerCase()} show`;
        
        // Hide after animation
        setTimeout(() => {
            this.judgmentText.classList.remove('show');
        }, 600);
    }

    showLaneHitEffect(lane) {
        if (this.keyHints[lane]) {
            this.keyHints[lane].classList.add('hit-effect');
            setTimeout(() => {
                this.keyHints[lane].classList.remove('hit-effect');
            }, 300);
        }
    }

    updateComboDisplay() {
        const combo = this.gameState.stats.combo;
        
        if (combo > 0) {
            this.comboDisplay.textContent = `${combo} COMBO`;
            this.comboDisplay.classList.add('show');
        } else {
            // Hide combo display when combo is 0
            this.comboDisplay.classList.remove('show');
            this.comboDisplay.textContent = '';
        }
        
        // Debug logging
        if (this.config.debug_mode) {
            console.log(`Combo display updated: ${combo} (visible: ${combo > 0})`);
        }
    }

    updateGameUI() {
        this.scoreElement.textContent = this.formatScore(this.gameState.stats.score);
        this.comboElement.textContent = this.gameState.stats.combo;
        this.accuracyElement.textContent = `${this.gameState.stats.accuracy.toFixed(1)}%`;
    }

    formatScore(score) {
        return score.toLocaleString();
    }

    togglePause() {
        if (this.gameState.isPlaying) {
            if (this.gameState.isPaused) {
                this.resumeGame();
            } else {
                this.pauseGame();
            }
        }
    }

    pauseGame() {
        this.socket.emit('pause_game');
    }

    resumeGame() {
        this.socket.emit('resume_game');
    }

    restartGame() {
        // 简单重新载入页面来确保完全重置
        window.location.reload();
    }

    quitGame() {
        this.endGame();
        window.location.href = '/';
    }

    backToChartSelection() {
        this.endGame();
        window.location.href = '/';
    }

    handleGamePaused() {
        this.gameState.isPaused = true;
        if (this.audio) {
            this.audio.pause();
        }
        this.gamePause.style.display = 'flex';
    }

    handleGameResumed() {
        this.gameState.isPaused = false;
        if (this.audio) {
            this.audio.play();
        }
        this.gamePause.style.display = 'none';
    }

    handleGameEnded(data) {
        // Server emits an object in the form { results: { ... } }
        // but showGameResults expects the inner results object.
        // Fallback to the whole data if it already matches the expected shape.
        this.endGame();
        const results = data && data.results ? data.results : data;
        this.showGameResults(results);
    }

    endGame() {
        this.gameState.isPlaying = false;
        this.gameState.isPaused = false;
        
        if (this.gameAnimationId) {
            cancelAnimationFrame(this.gameAnimationId);
            this.gameAnimationId = null;
        }
        
        if (this.audio) {
            this.audio.pause();
        }
        
        this.socket.emit('end_game');
    }

    showGameResults(results) {
        // Update result display
        this.finalScore.textContent = this.formatScore(results.score);
        this.finalCombo.textContent = results.max_combo;
        this.finalAccuracy.textContent = `${results.accuracy.toFixed(1)}%`;
        
        // Update judgment counts
        this.perfectCount.textContent = results.judgments.perfect;
        this.greatCount.textContent = results.judgments.great;
        this.goodCount.textContent = results.judgments.good;
        this.missCount.textContent = results.judgments.miss;
        
        // Calculate and show grade
        const grade = this.calculateGrade(results.accuracy);
        this.finalGrade.textContent = grade;
        
        // Show results
        this.gameResults.style.display = 'flex';
    }

    calculateGrade(accuracy) {
        if (accuracy >= 95) return 'S';
        if (accuracy >= 90) return 'A';
        if (accuracy >= 80) return 'B';
        if (accuracy >= 70) return 'C';
        return 'D';
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
        const loading = document.getElementById('loading');
        loading.style.display = 'none';
    }

    actuallyStartGame() {
        // Start the game on server
        this.socket.emit('start_game', {
            chart_path: this.chartPath,
            config: this.config
        });
    }

    drawPreparationOverlay(ctx, width, height) {
        // Draw preparation text directly on canvas
        ctx.fillStyle = 'white';
        ctx.font = '30px Roboto';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
        ctx.shadowBlur = 6;
    
        ctx.fillText('按 Enter 開始遊戲', width / 2, height / 2);
        
        // Reset shadow and baseline
        ctx.shadowBlur = 0;
        ctx.textBaseline = 'alphabetic';
    }
}

// Initialize the game when page loads
document.addEventListener('DOMContentLoaded', () => {
    new RhythmGame();
}); 