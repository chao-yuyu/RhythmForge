import os
import yt_dlp
import re
from pathlib import Path
import time
import random


class YouTubeDownloader:
    def __init__(self, download_dir="rhythm_game/assets"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def sanitize_filename(self, filename):
        """清理檔案名稱，移除非法字符"""
        # 移除或替換非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制長度
        if len(filename) > 100:
            filename = filename[:100]
        return filename
    
    def get_ydl_opts(self, output_template):
        """獲取 yt-dlp 配置選項"""
        # 隨機選擇 User-Agent 以避免被封鎖
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        
        return {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'extractaudio': True,
            'audioformat': 'wav',
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'ignoreerrors': False,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'prefer_insecure': False,
            'http_headers': {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web'],
                    'player_skip': ['dash'],
                    'skip': ['hls'],
                    'comment_sort': ['top'],
                    'max_comments': [0],
                }
            },
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
            'keep_fragments': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'socket_timeout': 30,
            'retries': 10,
            'file_access_retries': 3,
            'extract_flat': False,
            'proxy': None,
            'age_limit': None,
            'cookiefile': None,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            'sleep_interval_requests': 1,
            'sleep_interval_subtitles': 1,
        }
    
    def download_audio(self, youtube_url):
        """
        下載 YouTube 音樂為 wav 格式
        
        Args:
            youtube_url (str): YouTube 影片連結
            
        Returns:
            tuple: (下載成功的檔案路徑, 歌曲標題) 或 (None, None) 如果失敗
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"嘗試下載 (第 {attempt + 1} 次): {youtube_url}")
                
                # 先獲取影片資訊
                info_opts = self.get_ydl_opts('%(title)s.%(ext)s')
                info_opts['quiet'] = True
                
                with yt_dlp.YoutubeDL(info_opts) as ydl:
                    try:
                        # 取得影片資訊但不下載
                        info = ydl.extract_info(youtube_url, download=False)
                        title = info.get('title', 'unknown')
                        duration = info.get('duration', 0)
                        
                        # 檢查影片長度（避免下載過長的影片）
                        if duration > 600:  # 10分鐘
                            print(f"警告: 影片長度 {duration//60}:{duration%60:02d}，可能較長")
                        
                        clean_title = self.sanitize_filename(title)
                        print(f"影片標題: {title}")
                        print(f"清理後檔名: {clean_title}")
                        
                    except Exception as e:
                        print(f"獲取影片資訊失敗: {str(e)}")
                        if attempt < max_retries - 1:
                            print(f"等待 {retry_delay} 秒後重試...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            return None, None
                
                # 設定下載選項
                download_template = str(self.download_dir / f'{clean_title}.%(ext)s')
                download_opts = self.get_ydl_opts(download_template)
                
                print(f"開始下載音頻...")
                
                # 執行下載
                with yt_dlp.YoutubeDL(download_opts) as ydl:
                    ydl.download([youtube_url])
                
                # 檢查下載的檔案
                possible_extensions = ['wav', 'mp3', 'm4a', 'webm', 'mp4']
                audio_file = None
                
                for ext in possible_extensions:
                    candidate_file = self.download_dir / f"{clean_title}.{ext}"
                    if candidate_file.exists():
                        audio_file = candidate_file
                        break
                
                if audio_file and audio_file.exists():
                    print(f"下載完成: {audio_file}")
                    return str(audio_file), clean_title
                else:
                    print(f"找不到下載檔案，檢查目錄: {self.download_dir}")
                    # 列出目錄中的所有檔案以便調試
                    files = list(self.download_dir.glob(f"{clean_title}*"))
                    if files:
                        print(f"找到相關檔案: {files}")
                        # 使用找到的第一個檔案
                        audio_file = files[0]
                        print(f"使用檔案: {audio_file}")
                        return str(audio_file), clean_title
                    else:
                        print("沒有找到任何相關檔案")
                        if attempt < max_retries - 1:
                            print(f"等待 {retry_delay} 秒後重試...")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            return None, None
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"下載錯誤: {error_msg}")
                
                # 檢查是否是地區限制或版權問題
                if any(keyword in error_msg.lower() for keyword in ['blocked', 'restricted', 'unavailable', 'private']):
                    print("影片可能被封鎖、限制或為私人影片")
                    return None, None
                
                # 檢查是否是網路問題
                if any(keyword in error_msg.lower() for keyword in ['403', 'forbidden', 'timeout', 'connection']):
                    if attempt < max_retries - 1:
                        print(f"網路問題，等待 {retry_delay} 秒後重試...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        print("多次重試後仍然失敗")
                        return None, None
                
                # 其他錯誤
                if attempt < max_retries - 1:
                    print(f"未知錯誤，等待 {retry_delay} 秒後重試...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return None, None
                    
            except Exception as e:
                print(f"意外錯誤: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"等待 {retry_delay} 秒後重試...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return None, None
        
        print("所有重試都失敗了")
        return None, None
    
    def get_downloaded_files(self):
        """取得已下載的音樂檔案清單"""
        audio_files = []
        for ext in ['*.wav', '*.mp3', '*.m4a', '*.webm']:
            audio_files.extend(self.download_dir.glob(ext))
        return audio_files
    
    def test_connection(self):
        """測試 YouTube 連接"""
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - 應該總是可用
        
        try:
            info_opts = self.get_ydl_opts('%(title)s.%(ext)s')
            info_opts['quiet'] = True
            
            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                title = info.get('title', 'unknown')
                print(f"連接測試成功，測試影片: {title}")
                return True
                
        except Exception as e:
            print(f"連接測試失敗: {str(e)}")
            return False


if __name__ == "__main__":
    # 測試用
    downloader = YouTubeDownloader()
    
    # 先測試連接
    print("測試 YouTube 連接...")
    if downloader.test_connection():
        print("連接正常，可以開始下載")
    else:
        print("連接有問題，請檢查網路或稍後再試")
    
    url = input("請輸入 YouTube 連結: ")
    if url.strip():
        file_path, title = downloader.download_audio(url)
        if file_path:
            print(f"成功下載: {title} -> {file_path}")
        else:
            print("下載失敗")
    else:
        print("未輸入 URL") 