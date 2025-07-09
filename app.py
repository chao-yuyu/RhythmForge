#!/usr/bin/env python3
"""
節奏遊戲 Web 應用
Rhythm Game Web Application

Flask 後端 API 伺服器
"""

import os
import json
import time
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging
import re
from werkzeug.utils import secure_filename

# 導入遊戲核心模組
from rhythm_game.src.downloader import YouTubeDownloader
from rhythm_game.src.analyzer import AudioAnalyzer
from rhythm_game.src.utils import ChartManager, ConfigManager, ScoreCalculator, GameStats

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 創建 Flask 應用
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = 'rhythm_game_secret_key_2024'

# 啟用 CORS 和 SocketIO
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 初始化遊戲組件
downloader = YouTubeDownloader()
analyzer = AudioAnalyzer(debug=True)
chart_manager = ChartManager()
config_manager = ConfigManager()

# 全域遊戲狀態
game_sessions = {}

class WebGameSession:
    """Web 遊戲會話管理"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.chart_data = None
        self.game_stats = GameStats()
        self.score_calculator = ScoreCalculator()
        self.start_time = None
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0
        
    def load_chart(self, chart_path):
        """載入譜面"""
        self.chart_data = chart_manager.load_chart(chart_path)
        return self.chart_data is not None
        
    def start_game(self):
        """開始遊戲"""
        self.game_stats.reset()
        self.game_stats.start_game()
        self.start_time = time.time()
        self.is_playing = True
        self.is_paused = False
        
    def pause_game(self):
        """暫停遊戲"""
        self.is_paused = True
        
    def resume_game(self):
        """恢復遊戲"""
        self.is_paused = False
        
    def end_game(self):
        """結束遊戲"""
        self.is_playing = False
        self.game_stats.end_game()
        
    def get_current_time(self):
        """獲取目前遊戲時間"""
        if not self.is_playing or self.start_time is None:
            return 0
        return time.time() - self.start_time
        
    def hit_note(self, lane, hit_time):
        """處理音符擊中"""
        current_time = self.get_current_time()
        
        # 尋找對應的音符
        best_note = None
        best_judgment = None
        best_time_diff = float('inf')
        
        # 更寬鬆的判定容差，適合 Web 環境
        tolerances = config_manager.get('judgment_tolerances', {})
        tolerance_perfect = tolerances.get('perfect', 0.08)  # 增加到 80ms
        tolerance_great = tolerances.get('great', 0.15)     # 增加到 150ms
        tolerance_good = tolerances.get('good', 0.25)       # 增加到 250ms
        
        # 尋找該 lane 中最適合的音符
        for note in self.chart_data['notes']:
            if note['lane'] == lane and not note.get('hit', False):
                # 計算時間差 - 使用目前時間而不是 hit_time 以提高準確性
                time_diff = abs(current_time - note['time'])
                
                # 判定邏輯
                judgment = None
                if time_diff <= tolerance_perfect:
                    judgment = 'perfect'
                elif time_diff <= tolerance_great:
                    judgment = 'great'
                elif time_diff <= tolerance_good:
                    judgment = 'good'
                    
                # 選擇最接近的音符
                if judgment and time_diff < best_time_diff:
                    best_note = note
                    best_judgment = judgment
                    best_time_diff = time_diff
        
        # 處理擊中
        if best_note and best_judgment:
            best_note['hit'] = True
            best_note['judgment'] = best_judgment
            self.game_stats.add_judgment(best_judgment)
            
            # 計算分數
            score = self.score_calculator.calculate_note_score(
                best_judgment, self.game_stats.combo
            )
            self.game_stats.add_score(score)
            
            logger.info(f"Hit note: lane {lane}, judgment {best_judgment}, time_diff {best_time_diff:.3f}s")
            
            return {
                'success': True,
                'judgment': best_judgment,
                'score': score,
                'combo': self.game_stats.combo,
                'time_diff': best_time_diff
            }
        
        # 如果沒有擊中任何音符，記錄為miss
        logger.info(f"Miss: lane {lane}, current_time {current_time:.3f}s")
        
        # 記錄miss判定
        self.game_stats.add_judgment('miss')
        
        return {
            'success': False, 
            'judgment': 'miss',
            'combo': self.game_stats.combo,  # 返回更新後的combo (應該是0)
            'score': self.game_stats.score   # 返回目前分數
        }

# API 路由

@app.route('/')
def index():
    """主頁面"""
    return send_from_directory('static', 'index.html')

@app.route('/play.html')
def play():
    """遊戲頁面"""
    return send_from_directory('static', 'play.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """獲取遊戲設定"""
    config = config_manager.config.copy()
    
    # 確保有預設的時間校準設定
    if 'audio_delay' not in config:
        config['audio_delay'] = 0.15
    if 'visual_offset' not in config:
        config['visual_offset'] = 0.0
    
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新遊戲設定"""
    try:
        data = request.get_json()
        for key, value in data.items():
            config_manager.set(key, value)
        config_manager.save_config()
        return jsonify({'success': True, 'message': '設定已更新'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/download', methods=['POST'])
def download_music():
    """下載音樂"""
    try:
        data = request.get_json()
        youtube_url = data.get('url')
        
        if not youtube_url:
            return jsonify({'success': False, 'error': '缺少 YouTube URL'}), 400
        
        # 驗證 URL 格式
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/[\w-]+',
        ]
        
        if not any(re.match(pattern, youtube_url) for pattern in youtube_patterns):
            return jsonify({'success': False, 'error': '請輸入有效的 YouTube 連結'}), 400
            
        # 開始下載任務
        def download_task():
            try:
                # 發送開始下載的進度更新
                socketio.emit('download_progress', {
                    'status': 'progress',
                    'progress': 0,
                    'message': '正在準備下載...'
                })
                
                # 定義進度回調函數
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        # 計算下載進度
                        if 'total_bytes' in d and d['total_bytes']:
                            percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                            percent = min(percent, 90)  # 最多顯示90%，留10%給後處理
                        elif 'total_bytes_estimate' in d and d['total_bytes_estimate']:
                            percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                            percent = min(percent, 90)
                        else:
                            # 如果沒有總大小資訊，使用下載速度作為進度指示
                            percent = min(d.get('downloaded_bytes', 0) / (1024 * 1024) * 10, 90)
                        
                        # 格式化下載速度
                        speed = d.get('speed', 0)
                        if speed:
                            if speed > 1024 * 1024:
                                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
                            elif speed > 1024:
                                speed_str = f"{speed / 1024:.1f} KB/s"
                            else:
                                speed_str = f"{speed:.0f} B/s"
                        else:
                            speed_str = "計算中..."
                        
                        # 發送進度更新
                        socketio.emit('download_progress', {
                            'status': 'progress',
                            'progress': int(percent),
                            'message': f'下載中... {int(percent)}% ({speed_str})'
                        })
                        
                    elif d['status'] == 'finished':
                        # 下載完成，開始後處理
                        socketio.emit('download_progress', {
                            'status': 'progress',
                            'progress': 95,
                            'message': '下載完成，正在轉換音頻格式...'
                        })
                
                # 測試連接
                logger.info(f"Testing connection before download: {youtube_url}")
                if not downloader.test_connection():
                    socketio.emit('download_progress', {
                        'status': 'failed',
                        'error': '無法連接到 YouTube，請檢查網路連接'
                    })
                    return
                
                # 發送分析進度
                socketio.emit('download_progress', {
                    'status': 'progress',
                    'progress': 5,
                    'message': '正在分析影片資訊...'
                })
                
                # 執行下載，傳入進度回調
                audio_path, title = downloader.download_audio(youtube_url, progress_hook)
                
                if audio_path:
                    # 發送完成進度
                    socketio.emit('download_progress', {
                        'status': 'progress',
                        'progress': 98,
                        'message': '正在驗證檔案...'
                    })
                    
                    # 驗證檔案
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                        # 獲取音訊時長
                        duration = None
                        try:
                            import librosa
                            y, sr = librosa.load(audio_path, sr=None)
                            duration_seconds = len(y) / sr
                            duration = f"{int(duration_seconds//60)}:{int(duration_seconds%60):02d}"
                        except:
                            duration = None
                        
                        socketio.emit('download_progress', {
                            'status': 'completed',
                            'title': title,
                            'path': audio_path,
                            'audio_path': audio_path,  # 添加 audio_path 字段
                            'filename': os.path.basename(audio_path),  # 添加 filename 字段
                            'duration': duration,  # 添加 duration 字段
                            'progress': 100
                        })
                        logger.info(f"Download completed successfully: {title} -> {audio_path}")
                    else:
                        socketio.emit('download_progress', {
                            'status': 'failed',
                            'error': '下載的檔案無效或損壞'
                        })
                else:
                    socketio.emit('download_progress', {
                        'status': 'failed',
                        'error': '下載失敗，請檢查 YouTube 連結是否正確'
                    })
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Download error: {error_msg}")
                
                # 根據錯誤類型提供更詳細的錯誤資訊
                if 'HTTP Error 403' in error_msg or 'Forbidden' in error_msg:
                    user_error = '無法存取該影片，可能是私人影片或地區限制'
                elif 'HTTP Error 404' in error_msg:
                    user_error = '找不到該影片，請檢查連結是否正確'
                elif 'blocked' in error_msg.lower() or 'restricted' in error_msg.lower():
                    user_error = '該影片在您的地區被封鎖或受到限制'
                elif 'timeout' in error_msg.lower() or 'connection' in error_msg.lower():
                    user_error = '網路連接問題，請檢查網路狀態後重試'
                elif 'unavailable' in error_msg.lower():
                    user_error = '該影片目前無法使用'
                else:
                    user_error = f'下載失敗: {error_msg}'
                
                socketio.emit('download_progress', {
                    'status': 'failed',
                    'error': user_error
                })
        
        thread = threading.Thread(target=download_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': '開始下載，請稍候...'})
        
    except Exception as e:
        logger.error(f"Download API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload_music', methods=['POST'])
def upload_music():
    """上傳音樂檔案"""
    try:
        # 檢查是否有檔案上傳
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '沒有選擇檔案'}), 400
        
        file = request.files['file']
        
        # 檢查檔案名稱
        if file.filename == '':
            return jsonify({'success': False, 'error': '沒有選擇檔案'}), 400
        
        # 檢查檔案類型
        allowed_extensions = {'mp3', 'wav'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({'success': False, 'error': '只支援 MP3 和 WAV 格式'}), 400
        
        # 檢查檔案大小 (50MB 限制)
        file.seek(0, 2)  # 移動到檔案末尾
        file_size = file.tell()
        file.seek(0)  # 重置檔案指標
        
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return jsonify({'success': False, 'error': '檔案大小不能超過 50MB'}), 400
        
        # 確保上傳目錄存在
        upload_dir = Path("rhythm_game/assets")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成安全的檔案名稱
        original_filename = secure_filename(file.filename)
        filename = original_filename
        
        # 如果檔案已存在，添加數字後綴
        counter = 1
        while (upload_dir / filename).exists():
            name, ext = original_filename.rsplit('.', 1)
            filename = f"{name}_{counter}.{ext}"
            counter += 1
        
        # 儲存檔案
        file_path = upload_dir / filename
        file.save(str(file_path))
        
        # 驗證檔案是否成功儲存
        if not file_path.exists() or file_path.stat().st_size == 0:
            return jsonify({'success': False, 'error': '檔案儲存失敗'}), 500
        
        # 嘗試獲取音訊資訊
        duration = None
        try:
            import librosa
            y, sr = librosa.load(str(file_path), sr=None)
            duration_seconds = len(y) / sr
            duration = f"{int(duration_seconds//60)}:{int(duration_seconds%60):02d}"
        except Exception as e:
            logger.warning(f"無法獲取音訊時長: {e}")
            duration = None
        
        # 生成標題（去除副檔名）
        title = file_path.stem
        
        logger.info(f"File uploaded successfully: {filename} -> {file_path}")
        
        return jsonify({
            'success': True,
            'message': '檔案上傳成功',
            'filename': filename,
            'title': title,
            'path': file_path.as_posix(),
            'size': file_size,
            'duration': duration
        })
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': f'上傳失敗: {str(e)}'}), 500

@app.route('/api/audio_files', methods=['GET'])
def get_audio_files():
    """獲取音訊檔案清單"""
    try:
        audio_files = downloader.get_downloaded_files()
        files_info = []
        
        for file_path in audio_files:
            # 獲取檔案資訊
            file_size = file_path.stat().st_size if file_path.exists() else 0
            
            # 嘗試獲取音訊時長
            duration = None
            try:
                import librosa
                y, sr = librosa.load(str(file_path), sr=None)
                duration = len(y) / sr
            except:
                duration = None
            
            files_info.append({
                'title': file_path.stem,  # 使用檔案名稱作為標題
                'filename': file_path.name,  # 完整檔案名稱
                'path': file_path.as_posix(),  # 檔案路徑，使用 POSIX 風格
                'stem': file_path.stem,  # 檔案名稱（不含副檔名）
                'duration': f"{int(duration//60)}:{int(duration%60):02d}" if duration else None,  # 格式化時長
                'size': file_size
            })
            
        return jsonify({'success': True, 'files': files_info})
        
    except Exception as e:
        logger.error(f"Error getting audio files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate_chart', methods=['POST'])
def generate_chart():
    """產生譜面"""
    try:
        data = request.get_json()
        audio_path = data.get('audio_path')
        song_title = data.get('song_title')
        method = data.get('method', 'balanced_beat')  # 預設使用新的平衡節拍方法
        
        if not audio_path:
            return jsonify({'success': False, 'error': '缺少音訊檔案路徑'}), 400
            
        # 驗證方法是否支援
        supported_methods = ['balanced_beat', 'energy', 'energy_analysis']
        if method not in supported_methods:
            logger.warning(f"Unsupported method '{method}', using default 'balanced_beat'")
            method = 'balanced_beat'
            
        def generate_task():
            try:
                socketio.emit('chart_progress', {'status': 'analyzing', 'message': f'正在使用 {method} 方法分析音訊...'})
                
                chart_data = analyzer.generate_chart(
                    audio_path,
                    song_title=song_title,
                    method=method
                )
                
                if chart_data:
                    chart_path = analyzer.save_chart(chart_data)
                    socketio.emit('chart_progress', {
                        'status': 'completed',
                        'chart_data': chart_data,
                        'chart_path': chart_path,
                        'method_used': method
                    })
                else:
                    socketio.emit('chart_progress', {
                        'status': 'failed',
                        'error': '譜面產生失敗'
                    })
                    
            except Exception as e:
                logger.error(f"Chart generation error: {str(e)}")
                socketio.emit('chart_progress', {
                    'status': 'failed',
                    'error': str(e)
                })
        
        thread = threading.Thread(target=generate_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': f'開始使用 {method} 方法產生譜面...'})
        
    except Exception as e:
        logger.error(f"Generate chart error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/charts', methods=['GET'])
def get_charts():
    """獲取可用譜面清單"""
    try:
        charts = chart_manager.get_available_charts()
        return jsonify({'success': True, 'charts': charts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chart/<path:chart_id>', methods=['GET'])
def get_chart(chart_id):
    """獲取特定譜面資料"""
    try:
        # 如果傳入的是完整路徑，直接使用；否則建構路徑
        if chart_id.startswith('rhythm_game/charts/'):
            chart_path = chart_id
        else:
            chart_path = f"rhythm_game/charts/{chart_id}"
        
        logger.info(f"Loading chart from path: {chart_path}")
        chart_data = chart_manager.load_chart(chart_path)
        
        if chart_data:
            return jsonify({'success': True, 'chart': chart_data})
        else:
            logger.error(f"Chart not found: {chart_path}")
            return jsonify({'success': False, 'error': '譜面不存在'}), 404
            
    except Exception as e:
        logger.error(f"Error loading chart: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/audio/<path:filename>')
def serve_audio(filename):
    """提供音樂檔案"""
    try:
        audio_dir = Path("rhythm_game/assets")
        return send_from_directory(audio_dir, filename)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/delete_audio', methods=['DELETE'])
def delete_audio():
    """刪除音樂檔案及其相關譜面"""
    try:
        data = request.get_json()
        audio_path = data.get('audio_path')
        
        if not audio_path:
            return jsonify({'error': 'Audio path is required'}), 400
        
        # 確保路徑安全
        audio_path = os.path.normpath(audio_path)
        music_dir = Path("rhythm_game/assets")
        full_audio_path = music_dir / os.path.basename(audio_path)
        
        if not full_audio_path.exists():
            return jsonify({'error': 'Audio file not found'}), 404
        
        # 刪除音樂檔案
        full_audio_path.unlink()
        
        # 查找並刪除相關的譜面檔案
        audio_filename = os.path.splitext(os.path.basename(audio_path))[0]
        charts_deleted = 0
        charts_dir = Path("rhythm_game/charts")
        
        if charts_dir.exists():
            for chart_file in charts_dir.glob("*.json"):
                if chart_file.stem.startswith(audio_filename):
                    try:
                        chart_file.unlink()
                        charts_deleted += 1
                    except OSError:
                        pass
        
        return jsonify({
            'success': True,
            'message': f'已刪除音樂檔案及 {charts_deleted} 個相關譜面'
        })
        
    except Exception as e:
        print(f"Delete audio error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_all_audio', methods=['DELETE'])
def delete_all_audio():
    """刪除所有音樂檔案及其相關譜面"""
    try:
        deleted_count = 0
        charts_deleted = 0
        
        music_dir = Path("rhythm_game/assets")
        charts_dir = Path("rhythm_game/charts")
        
        # 刪除所有音樂檔案
        if music_dir.exists():
            for audio_file in music_dir.glob("*"):
                if audio_file.suffix.lower() in ['.mp3', '.wav', '.m4a', '.webm']:
                    try:
                        audio_file.unlink()
                        deleted_count += 1
                    except OSError:
                        pass
        
        # 刪除所有譜面檔案
        if charts_dir.exists():
            for chart_file in charts_dir.glob("*.json"):
                try:
                    chart_file.unlink()
                    charts_deleted += 1
                except OSError:
                    pass
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'charts_deleted': charts_deleted,
            'message': f'已刪除 {deleted_count} 個音樂檔案和 {charts_deleted} 個譜面檔案'
        })
        
    except Exception as e:
        print(f"Delete all audio error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_audio_files', methods=['POST'])
def delete_audio_files():
    """批量刪除選取的音樂檔案及其相關譜面"""
    try:
        data = request.get_json()
        audio_paths = data.get('audio_paths', [])
        
        if not audio_paths:
            return jsonify({'error': 'No audio paths provided'}), 400
        
        deleted_count = 0
        charts_deleted = 0
        music_dir = Path("rhythm_game/assets")
        charts_dir = Path("rhythm_game/charts")
        
        for audio_path in audio_paths:
            try:
                # 確保路徑安全
                audio_path = os.path.normpath(audio_path)
                full_audio_path = music_dir / os.path.basename(audio_path)
                
                if full_audio_path.exists():
                    # 刪除音樂檔案
                    full_audio_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted audio file: {full_audio_path}")
                    
                    # 查找並刪除相關的譜面檔案
                    audio_filename = os.path.splitext(os.path.basename(audio_path))[0]
                    
                    if charts_dir.exists():
                        for chart_file in charts_dir.glob("*.json"):
                            if chart_file.stem.startswith(audio_filename):
                                try:
                                    chart_file.unlink()
                                    charts_deleted += 1
                                    logger.info(f"Deleted related chart: {chart_file}")
                                except OSError:
                                    pass
                else:
                    logger.warning(f"Audio file not found: {full_audio_path}")
                    
            except Exception as e:
                logger.error(f"Error deleting audio file {audio_path}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'charts_deleted': charts_deleted,
            'message': f'成功刪除 {deleted_count} 個音樂檔案和 {charts_deleted} 個相關譜面檔案'
        })
        
    except Exception as e:
        logger.error(f"Batch delete audio files error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_charts', methods=['POST'])
def delete_charts():
    """批量刪除選取的譜面檔案"""
    try:
        data = request.get_json()
        chart_paths = data.get('chart_paths', [])
        
        if not chart_paths:
            return jsonify({'error': 'No chart paths provided'}), 400
        
        deleted_count = 0
        charts_dir = Path("rhythm_game/charts")
        
        for chart_path in chart_paths:
            try:
                # 確保路徑安全
                chart_path = os.path.normpath(chart_path)
                full_chart_path = Path(chart_path)
                
                # 如果是相對路徑，轉換為絕對路徑
                if not full_chart_path.is_absolute():
                    full_chart_path = charts_dir / os.path.basename(chart_path)
                
                if full_chart_path.exists():
                    full_chart_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted chart: {full_chart_path}")
                else:
                    logger.warning(f"Chart file not found: {full_chart_path}")
                    
            except Exception as e:
                logger.error(f"Error deleting chart {chart_path}: {e}")
                continue
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'成功刪除 {deleted_count} 個譜面檔案'
        })
        
    except Exception as e:
        logger.error(f"Batch delete charts error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_chart', methods=['DELETE'])
def delete_chart():
    """刪除單個譜面檔案"""
    try:
        data = request.get_json()
        chart_path = data.get('chart_path')
        
        if not chart_path:
            return jsonify({'error': 'Chart path is required'}), 400
        
        # 確保路徑安全
        chart_path = os.path.normpath(chart_path)
        charts_dir = Path("rhythm_game/charts")
        full_chart_path = charts_dir / os.path.basename(chart_path)
        
        if not full_chart_path.exists():
            return jsonify({'error': 'Chart file not found'}), 404
        
        # 刪除譜面檔案
        full_chart_path.unlink()
        
        return jsonify({
            'success': True,
            'message': '譜面檔案已刪除'
        })
        
    except Exception as e:
        print(f"Delete chart error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_all_charts', methods=['DELETE'])
def delete_all_charts():
    """刪除所有譜面檔案"""
    try:
        deleted_count = 0
        charts_dir = Path("rhythm_game/charts")
        
        if charts_dir.exists():
            for chart_file in charts_dir.glob("*.json"):
                try:
                    chart_file.unlink()
                    deleted_count += 1
                except OSError:
                    pass
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'已刪除 {deleted_count} 個譜面檔案'
        })
        
    except Exception as e:
        print(f"Delete all charts error: {e}")
        return jsonify({'error': str(e)}), 500

# SocketIO 事件處理

@socketio.on('connect')
def handle_connect():
    """客戶端連接"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': '連接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    """客戶端斷開連接"""
    logger.info(f"Client disconnected: {request.sid}")
    
    # 清理遊戲會話
    if request.sid in game_sessions:
        del game_sessions[request.sid]

@socketio.on('start_game')
def handle_start_game(data):
    """開始遊戲"""
    try:
        chart_path = data.get('chart_path')
        
        logger.info(f"Received start_game request with chart_path: {chart_path}")
        
        if not chart_path:
            logger.error("No chart_path provided")
            emit('game_error', {'error': '缺少譜面路徑'})
            return
        
        # 創建遊戲會話
        session = WebGameSession(request.sid)
        
        logger.info(f"Created session for {request.sid}")
        
        if session.load_chart(chart_path):
            logger.info(f"Chart loaded successfully: {session.chart_data['song_title']} with {len(session.chart_data['notes'])} notes")
            
            game_sessions[request.sid] = session
            session.start_game()
            
            emit('game_started', {
                'chart_data': session.chart_data,
                'start_time': session.start_time
            })
            
            logger.info(f"Game started successfully for session {request.sid}")
        else:
            logger.error(f"Failed to load chart: {chart_path}")
            emit('game_error', {'error': '載入譜面失敗'})
            
    except Exception as e:
        logger.error(f"Error starting game: {str(e)}")
        emit('game_error', {'error': str(e)})

@socketio.on('hit_note')
def handle_hit_note(data):
    """處理音符擊中"""
    try:
        session = game_sessions.get(request.sid)
        if not session:
            emit('game_error', {'error': '遊戲會話不存在'})
            return
            
        lane = data.get('lane')
        hit_time = data.get('time')
        
        result = session.hit_note(lane, hit_time)
        
        # 獲取目前統計資訊
        stats = session.game_stats.to_dict()
        
        # 發送判定結果 - 修復combo資料格式
        emit('note_judgment', {
            'lane': lane,
            'judgment': result.get('judgment', 'miss'),
            'hit': result.get('success', False),
            'score': stats['score'],
            'combo': session.game_stats.combo,  # 使用目前 combo 而不是 max_combo
            'max_combo': stats['max_combo'],  # 單獨發送 max_combo
            'accuracy': stats['accuracy'],
            'judgments': stats['judgments'],
            'note_time': data.get('note_time', hit_time)  # 添加 note_time 字段
        })
        
    except Exception as e:
        logger.error(f"Error in handle_hit_note: {str(e)}")
        emit('game_error', {'error': str(e)})

# ------------------------------
# 新增：自動 Miss 事件處理
# ------------------------------


@socketio.on('auto_miss')
def handle_auto_miss(data):
    """處理自動 MISS（音符未擊中）"""
    try:
        session = game_sessions.get(request.sid)
        if not session:
            emit('game_error', {'error': '遊戲會話不存在'})
            return

        lane = data.get('lane')
        note_time = data.get('note_time')

        # 標記對應的音符為 miss，避免之後還能被判定
        target_note = None
        if session.chart_data and 'notes' in session.chart_data:
            for note in session.chart_data['notes']:
                if note['lane'] == lane and abs(note['time'] - note_time) < 1e-3 and not note.get('hit', False):
                    target_note = note
                    break

        if target_note is not None:
            target_note['hit'] = True  # 標記已處理
            target_note['judgment'] = 'miss'

        # 更新統計資料
        session.game_stats.add_judgment('miss')

        # 取得最新統計
        stats = session.game_stats.to_dict()

        emit('note_judgment', {
            'lane': lane,
            'judgment': 'miss',
            'hit': False,
            'score': stats['score'],
            'combo': session.game_stats.combo,
            'max_combo': stats['max_combo'],
            'accuracy': stats['accuracy'],
            'judgments': stats['judgments'],
            'note_time': note_time
        })

    except Exception as e:
        logger.error(f"Error in handle_auto_miss: {str(e)}")
        emit('game_error', {'error': str(e)})

@socketio.on('pause_game')
def handle_pause_game():
    """暫停遊戲"""
    session = game_sessions.get(request.sid)
    if session:
        session.pause_game()
        emit('game_paused')

@socketio.on('resume_game')
def handle_resume_game():
    """恢復遊戲"""
    session = game_sessions.get(request.sid)
    if session:
        session.resume_game()
        emit('game_resumed')

@socketio.on('end_game')
def handle_end_game():
    """結束遊戲"""
    session = game_sessions.get(request.sid)
    if session:
        session.end_game()
        results = session.game_stats.to_dict()
        emit('game_ended', {'results': results})

@socketio.on('get_game_state')
def handle_get_game_state():
    """獲取遊戲狀態"""
    session = game_sessions.get(request.sid)
    if session:
        emit('game_state', {
            'is_playing': session.is_playing,
            'is_paused': session.is_paused,
            'current_time': session.get_current_time(),
            'stats': session.game_stats.to_dict() if session.game_stats else None
        })

if __name__ == '__main__':
    # 確保必要目錄存在
    Path("rhythm_game/assets").mkdir(parents=True, exist_ok=True)
    Path("rhythm_game/charts").mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(parents=True, exist_ok=True)
    
    # 啟動開發伺服器
    logger.info("🎵 啟動RhythmeForge Web 伺服器...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000) 