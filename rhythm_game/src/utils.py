import json
import os
from pathlib import Path
import time


class ScoreCalculator:
    """分數計算器"""
    
    def __init__(self):
        self.score_values = {
            'perfect': 1000,
            'great': 700,
            'good': 300,
            'miss': 0
        }
        self.combo_bonus_threshold = 10
        self.max_combo_bonus = 2.0
        
    def calculate_note_score(self, judgment, combo):
        """
        計算單個音符的分數
        
        Args:
            judgment (str): 判定結果
            combo (int): 當前 combo
            
        Returns:
            int: 該音符的分數
        """
        base_score = self.score_values.get(judgment, 0)
        
        # Combo 加成
        if combo >= self.combo_bonus_threshold:
            combo_multiplier = min(
                self.max_combo_bonus,
                1.0 + (combo - self.combo_bonus_threshold) * 0.1
            )
            base_score = int(base_score * combo_multiplier)
        
        return base_score
    
    def calculate_accuracy(self, judgments):
        """
        計算準確度
        
        Args:
            judgments (dict): 各判定的次數統計
            
        Returns:
            float: 準確度百分比 (0-100)
        """
        total_notes = sum(judgments.values())
        if total_notes == 0:
            return 0.0
        
        weighted_score = (
            judgments.get('perfect', 0) * 1.0 +
            judgments.get('great', 0) * 0.8 +
            judgments.get('good', 0) * 0.5 +
            judgments.get('miss', 0) * 0.0
        )
        
        return (weighted_score / total_notes) * 100
    
    def get_grade(self, accuracy):
        """
        根據準確度計算等級
        
        Args:
            accuracy (float): 準確度百分比
            
        Returns:
            str: 等級 (SS, S, A, B, C, D)
        """
        if accuracy >= 95:
            return 'SS'
        elif accuracy >= 90:
            return 'S'
        elif accuracy >= 80:
            return 'A'
        elif accuracy >= 70:
            return 'B'
        elif accuracy >= 60:
            return 'C'
        else:
            return 'D'


class GameStats:
    """遊戲統計數據管理"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置統計數據"""
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.judgments = {
            'perfect': 0,
            'great': 0,
            'good': 0,
            'miss': 0
        }
        self.start_time = None
        self.end_time = None
        
    def add_judgment(self, judgment):
        """添加判定結果"""
        if judgment in self.judgments:
            self.judgments[judgment] += 1
            
            if judgment != 'miss':
                self.combo += 1
                self.max_combo = max(self.max_combo, self.combo)
            else:
                self.combo = 0
    
    def add_score(self, points):
        """添加分數"""
        self.score += points
    
    def start_game(self):
        """開始遊戲計時"""
        self.start_time = time.time()
    
    def end_game(self):
        """結束遊戲計時"""
        self.end_time = time.time()
    
    def get_play_time(self):
        """取得遊戲時間（秒）"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    def to_dict(self):
        """轉換為字典格式"""
        calculator = ScoreCalculator()
        accuracy = calculator.calculate_accuracy(self.judgments)
        grade = calculator.get_grade(accuracy)
        
        return {
            'score': self.score,
            'max_combo': self.max_combo,
            'accuracy': accuracy,
            'grade': grade,
            'judgments': self.judgments.copy(),
            'play_time': self.get_play_time(),
            'total_notes': sum(self.judgments.values())
        }


class ChartManager:
    """譜面管理器"""
    
    def __init__(self, charts_dir="rhythm_game/charts"):
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
    
    def load_chart(self, chart_path):
        """
        載入譜面檔案
        
        Args:
            chart_path (str): 譜面檔案路徑
            
        Returns:
            dict or None: 譜面資料
        """
        try:
            with open(chart_path, 'r', encoding='utf-8') as f:
                chart_data = json.load(f)
            return chart_data
        except Exception as e:
            print(f"載入譜面失敗: {e}")
            return None
    
    def get_available_charts(self):
        """取得可用的譜面清單"""
        charts = []
        for json_file in self.charts_dir.glob("*.json"):
            try:
                chart_data = self.load_chart(json_file)
                if chart_data:
                    charts.append({
                        # 使用 as_posix() 以確保跨平台一致的路徑格式
                        'path': json_file.as_posix(),
                        'file': json_file.as_posix(),  # 保留 'file' 字段以防其他地方使用
                        'title': chart_data.get('song_title', json_file.stem),
                        'bpm': chart_data.get('bpm', 0),
                        'duration': chart_data.get('duration', 0),
                        'note_count': chart_data.get('note_count', 0),
                        'difficulty': chart_data.get('difficulty', '未知')  # 添加难度字段
                    })
            except Exception as e:
                print(f"無法讀取譜面 {json_file}: {e}")
        
        return charts
    
    def validate_chart(self, chart_data):
        """
        驗證譜面數據格式
        
        Args:
            chart_data (dict): 譜面資料
            
        Returns:
            bool: 是否有效
        """
        required_fields = ['song_title', 'audio_file', 'notes', 'lanes']
        
        # 檢查必要欄位
        for field in required_fields:
            if field not in chart_data:
                print(f"譜面缺少必要欄位: {field}")
                return False
        
        # 檢查音符格式
        notes = chart_data['notes']
        if not isinstance(notes, list):
            print("notes 必須是列表格式")
            return False
        
        for i, note in enumerate(notes):
            if not isinstance(note, dict):
                print(f"第 {i} 個音符格式錯誤")
                return False
            
            if 'time' not in note or 'lane' not in note:
                print(f"第 {i} 個音符缺少 time 或 lane")
                return False
            
            if not isinstance(note['time'], (int, float)):
                print(f"第 {i} 個音符的 time 必須是數字")
                return False
            
            if not isinstance(note['lane'], int) or note['lane'] < 0:
                print(f"第 {i} 個音符的 lane 必須是非負整數")
                return False
        
        return True


class ConfigManager:
    """設定管理器"""
    
    def __init__(self, config_file="rhythm_game/config.json"):
        self.config_file = Path(config_file)
        self.default_config = {
            'screen_width': 800,
            'screen_height': 600,
            'fps': 60,
            'master_volume': 0.7,
            'music_volume': 0.8,
            'sfx_volume': 0.5,
            'key_bindings': {
                'lane_0': 'd',
                'lane_1': 'f', 
                'lane_2': 'j',
                'lane_3': 'k',
                'pause': 'space',
                'restart': 'r',
                'quit': 'escape'
            },
            'note_speed': 300,
            'judgment_tolerances': {
                'perfect': 0.05,
                'great': 0.1,
                'good': 0.15
            },
            'auto_download': True,
            'debug_mode': False
        }
        self.config = self.load_config()
    
    def load_config(self):
        """載入設定檔"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合併預設設定（以防新增設定項目）
                for key, value in self.default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            else:
                return self.default_config.copy()
        except Exception as e:
            print(f"載入設定檔失敗，使用預設設定: {e}")
            return self.default_config.copy()
    
    def save_config(self):
        """儲存設定檔"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"儲存設定檔失敗: {e}")
            return False
    
    def get(self, key, default=None):
        """取得設定值"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """設定值"""
        self.config[key] = value
    
    def get_key_binding(self, action):
        """取得按鍵綁定"""
        return self.config['key_bindings'].get(action)


def format_time(seconds):
    """格式化時間顯示"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"


def format_score(score):
    """格式化分數顯示（加入千分位符號）"""
    return f"{score:,}"


def clamp(value, min_value, max_value):
    """限制數值範圍"""
    return max(min_value, min(value, max_value))


def lerp(a, b, t):
    """線性插值"""
    return a + (b - a) * t


def ease_out_cubic(t):
    """三次方緩出動畫函數"""
    return 1 - pow(1 - t, 3)


def ease_in_out_quad(t):
    """二次方緩進緩出動畫函數"""
    return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2


if __name__ == "__main__":
    # 測試功能
    print("測試工具函數...")
    
    # 測試分數計算
    calculator = ScoreCalculator()
    print(f"Perfect (combo 0): {calculator.calculate_note_score('perfect', 0)}")
    print(f"Perfect (combo 20): {calculator.calculate_note_score('perfect', 20)}")
    
    # 測試統計
    stats = GameStats()
    stats.add_judgment('perfect')
    stats.add_judgment('great')
    stats.add_judgment('miss')
    print(f"統計: {stats.to_dict()}")
    
    # 測試設定管理
    config = ConfigManager()
    print(f"螢幕寬度: {config.get('screen_width')}")
    print(f"Lane 0 按鍵: {config.get_key_binding('lane_0')}")
    
    print("工具函數測試完成！") 