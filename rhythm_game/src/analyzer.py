import librosa
import numpy as np
import json
import matplotlib.pyplot as plt
from pathlib import Path
import soundfile as sf
import random


class AudioAnalyzer:
    def __init__(self, debug=False):
        self.debug = debug
        self.sr = 22050  # 取樣率
        self.hop_length = 512
        self.charts_dir = Path("rhythm_game/charts")
        self.charts_dir.mkdir(parents=True, exist_ok=True)
    
    def load_audio(self, audio_path):
        """載入音訊檔案"""
        try:
            y, sr = librosa.load(audio_path, sr=self.sr)
            self.audio_data = y
            self.original_sr = sr
            print(f"音訊載入成功: {audio_path}")
            print(f"長度: {len(y)/sr:.2f} 秒")
            return True
        except Exception as e:
            print(f"音訊載入失敗: {e}")
            return False
    
    def detect_onsets(self, y=None, method='complex'):
        """
        檢測音訊的 onset 點（音符開始點）
        
        Args:
            y: 音訊資料，如果 None 則使用已載入的資料
            method: 檢測方法 ('complex', 'energy', 'spectral')
        
        Returns:
            list: onset 時間點列表
        """
        if y is None:
            y = self.audio_data
        
        # 使用不同的 onset 檢測方法
        if method == 'complex':
            # 複雜頻譜方法 - 對大多數音樂效果好
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=self.sr, 
                units='time',
                hop_length=self.hop_length,
                pre_max=20,
                post_max=20,
                pre_avg=100,
                post_avg=100,
                delta=0.1,
                wait=50
            )
        elif method == 'energy':
            # 簡化的能量檢測方法
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=self.sr,
                units='time',
                hop_length=self.hop_length,
                delta=0.15,
                wait=30
            )
        elif method == 'spectral':
            # 頻譜流量方法
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=self.sr,
                units='time',
                hop_length=self.hop_length,
                onset_envelope=librosa.onset.onset_strength(
                    y=y, sr=self.sr, feature=librosa.feature.spectral_centroid
                )
            )
        
        return onset_frames
    
    def detect_beats(self, y=None):
        """檢測節拍"""
        if y is None:
            y = self.audio_data
            
        tempo, beats = librosa.beat.beat_track(
            y=y, sr=self.sr, hop_length=self.hop_length, units='time'
        )
        
        if self.debug:
            print(f"檢測到的 BPM: {float(tempo):.2f}")
            print(f"節拍數量: {len(beats)}")
        
        return float(tempo), beats
    
    def filter_close_onsets(self, onsets, min_interval=0.15):
        """過濾過於接近的 onset 點"""
        if len(onsets) <= 1:
            return onsets
        
        filtered = [onsets[0]]
        for onset in onsets[1:]:
            if onset - filtered[-1] >= min_interval:
                filtered.append(onset)
        
        return np.array(filtered)
    
    def combine_detection_methods(self, y=None):
        """結合多種檢測方法獲得更好的結果"""
        if y is None:
            y = self.audio_data
        
        print("開始檢測 onset 和節拍...")
        
        # 使用多種方法檢測 onset
        onsets_complex = self.detect_onsets(y, 'complex')
        onsets_energy = self.detect_onsets(y, 'energy')
        
        # 檢測節拍
        tempo, beats = self.detect_beats(y)
        
        # 合併所有檢測點
        all_onsets = np.concatenate([onsets_complex, onsets_energy, beats])
        all_onsets = np.unique(all_onsets)  # 移除重複
        all_onsets = np.sort(all_onsets)
        
        # 過濾過於接近的點
        filtered_onsets = self.filter_close_onsets(all_onsets, min_interval=0.12)
        
        # 如果檢測到的 onset 太少，使用更寬鬆的參數重新檢測
        if len(filtered_onsets) < 20:
            print(f"檢測到的 onset 過少 ({len(filtered_onsets)})，嘗試使用更寬鬆的參數...")
            
            # 使用更寬鬆的參數重新檢測
            loose_onsets = librosa.onset.onset_detect(
                y=y, sr=self.sr,
                units='time',
                hop_length=self.hop_length,
                delta=0.05,  # 降低閾值
                wait=20      # 減少等待時間
            )
            
            # 再次合併
            all_onsets = np.concatenate([filtered_onsets, loose_onsets, beats])
            all_onsets = np.unique(all_onsets)
            all_onsets = np.sort(all_onsets)
            filtered_onsets = self.filter_close_onsets(all_onsets, min_interval=0.1)
        
        # 如果還是太少，使用節拍網格填充
        if len(filtered_onsets) < 10:
            print(f"檢測結果仍然過少 ({len(filtered_onsets)})，使用節拍網格填充...")
            
            # 基於 BPM 創建規律的節拍網格
            beat_interval = 60.0 / max(tempo, 60)  # 確保 BPM 不會太低
            duration = len(y) / self.sr
            
            # 創建節拍網格（每拍一個音符）
            grid_beats = np.arange(0, duration, beat_interval)
            
            # 合併檢測到的 onset 和節拍網格
            all_onsets = np.concatenate([filtered_onsets, grid_beats])
            all_onsets = np.unique(all_onsets)
            all_onsets = np.sort(all_onsets)
            filtered_onsets = self.filter_close_onsets(all_onsets, min_interval=0.1)
        
        if self.debug:
            print(f"Complex onsets: {len(onsets_complex)}")
            print(f"Energy onsets: {len(onsets_energy)}")
            print(f"Beats: {len(beats)}")
            print(f"合併後: {len(all_onsets)}")
            print(f"最終過濾後: {len(filtered_onsets)}")
            print(f"時間範圍: {filtered_onsets[0]:.2f}s - {filtered_onsets[-1]:.2f}s")
        
        return filtered_onsets, tempo
    
    def assign_lanes(self, onsets, num_lanes=4, method='energy'):
        """
        將 onset 點分配到不同的 lane
        
        Args:
            onsets: onset 時間點列表
            num_lanes: lane 數量
            method: 分配方法 ('energy', 'balanced_beat')
        
        Returns:
            list: [(time, lane), ...]
        """
        notes = []
        
        if method == 'balanced_beat':
            # 新的平衡分配方法，基於累積數量和拍點對齊
            y = self.audio_data
            print(f"Processing {len(onsets)} onsets with balanced beat method...")
            
            # 檢測節拍資訊
            tempo, beats = self.detect_beats(y)
            beat_interval = 60.0 / max(tempo, 80)  # 節拍間隔
            print(f"Detected BPM: {tempo:.2f}, Beat interval: {beat_interval:.3f}s")
            
            # 統計每個lane的累積使用次數
            lane_counts = [0] * num_lanes
            
            for i, time in enumerate(onsets):
                # 檢查是否靠近節拍點
                nearest_beat_distance = float('inf')
                for beat in beats:
                    distance = abs(time - beat)
                    if distance < nearest_beat_distance:
                        nearest_beat_distance = distance
                
                is_on_beat = nearest_beat_distance < 0.1  # 100ms內算作在節拍上
                
                # 找出累積數量最小的lane(s)
                min_count = min(lane_counts)
                min_count_lanes = [j for j in range(num_lanes) if lane_counts[j] == min_count]
                
                # 如果在拍點上，優先使用累積數量最小的lane
                if is_on_beat:
                    # 在拍點上，直接選擇累積數量最小的lane
                    if len(min_count_lanes) == 1:
                        lane = min_count_lanes[0]
                        selection_reason = "beat_sync_single"
                    else:
                        # 如果有多個相同最小累積數量的lane，隨機選擇
                        lane = random.choice(min_count_lanes)
                        selection_reason = "beat_sync_random"
                else:
                    # 不在拍點上，也使用累積數量最小的策略，但可以考慮其他因素
                    if len(min_count_lanes) == 1:
                        lane = min_count_lanes[0]
                        selection_reason = "balance_single"
                    else:
                        # 多個相同最小累積數量時，隨機選擇
                        lane = random.choice(min_count_lanes)
                        selection_reason = "balance_random"
                
                # 記錄音符
                notes.append({"time": float(time), "lane": int(lane)})
                lane_counts[lane] += 1
                
                if self.debug:
                    beat_status = "ON_BEAT" if is_on_beat else "off_beat"
                    print(f"Time {time:.2f}s: {beat_status}, lane_counts: {lane_counts}, "
                          f"selected lane {lane} ({selection_reason}), "
                          f"nearest_beat_dist: {nearest_beat_distance:.3f}s")
        
        elif method == 'energy' or method == 'energy_analysis':
            # 改進的能量分配算法，包含平衡分配和節拍同步
            y = self.audio_data
            print(f"Processing {len(onsets)} onsets with improved energy analysis...")
            
            # 檢測節拍資訊以便同步
            tempo, beats = self.detect_beats(y)
            beat_interval = 60.0 / max(tempo, 80)  # 節拍間隔
            
            # 統計每個lane的使用次數，用於平衡分配
            lane_counts = [0] * num_lanes
            last_lane = -1
            consecutive_count = 0
            
            for i, time in enumerate(onsets):
                # 計算該時間點周圍的頻譜能量分布
                frame_idx = int(time * self.sr)
                window_size = 512  # 增加窗口大小以獲得更好的頻率分辨率
                start_idx = max(0, frame_idx - window_size // 2)
                end_idx = min(len(y), frame_idx + window_size // 2)
                
                if end_idx > start_idx and (end_idx - start_idx) >= 512:  # 確保有足夠的樣本
                    segment = y[start_idx:end_idx]
                    
                    # 使用 FFT 分析頻率分布
                    try:
                        # 應用窗函數以減少頻譜洩漏
                        windowed_segment = segment * np.hanning(len(segment))
                        fft = np.fft.fft(windowed_segment)
                        freqs = np.fft.fftfreq(len(fft), 1/self.sr)
                        magnitude = np.abs(fft)
                        
                        # 只取正頻率部分
                        positive_freq_mask = freqs >= 0
                        freqs = freqs[positive_freq_mask]
                        magnitude = magnitude[positive_freq_mask]
                        
                        # 將頻率範圍分成 4 個區間（基於音樂的頻率特性）
                        freq_bands = [
                            (60, 250),    # 低頻 (bass) - lane 0
                            (250, 1000),  # 低中頻 (low-mid) - lane 1  
                            (1000, 4000), # 高中頻 (high-mid) - lane 2
                            (4000, 12000) # 高頻 (treble) - lane 3
                        ]
                        
                        band_energies = []
                        for low, high in freq_bands:
                            mask = (freqs >= low) & (freqs <= high)
                            if np.any(mask):
                                energy = np.sum(magnitude[mask] ** 2)  # 使用能量而非振幅
                            else:
                                energy = 0
                            band_energies.append(energy)
                        
                        # 避免所有能量都為0的情況
                        total_energy = sum(band_energies)
                        if total_energy > 0:
                            # 獲得能量最高的幾個候選lane
                            energy_array = np.array(band_energies)
                            # 獲得能量排序
                            sorted_indices = np.argsort(energy_array)[::-1]
                            
                            # 檢查是否靠近節拍點（增強節拍同步）
                            nearest_beat_distance = min([abs(time - beat) for beat in beats])
                            is_on_beat = nearest_beat_distance < 0.1  # 100ms內算作在節拍上
                            
                            # 平衡分配邏輯
                            lane = sorted_indices[0]  # 預設使用能量最高的lane
                            
                            # 避免連續太多相同lane（超過2次）
                            if last_lane == lane and consecutive_count >= 2:
                                # 嘗試使用第二高能量的lane
                                if len(sorted_indices) > 1:
                                    second_choice = sorted_indices[1]
                                    # 如果第二選擇的能量不會太低（至少是最高的30%）
                                    if energy_array[second_choice] >= energy_array[lane] * 0.3:
                                        lane = second_choice
                                        if self.debug:
                                            print(f"Time {time:.2f}s: Avoided consecutive, using 2nd choice lane {lane}")
                                    else:
                                        # 能量差距太大時，使用平衡分配
                                        min_count = min(lane_counts)
                                        balance_candidates = [j for j in range(num_lanes) 
                                                            if lane_counts[j] == min_count and j != last_lane]
                                        if balance_candidates:
                                            lane = random.choice(balance_candidates)
                                            if self.debug:
                                                print(f"Time {time:.2f}s: Used balance distribution, lane {lane}")
                            
                            # 在節拍點上，稍微偏好使用較少使用的lane（增加變化）
                            if is_on_beat:
                                min_count = min(lane_counts)
                                underused_lanes = [j for j in range(num_lanes) if lane_counts[j] == min_count]
                                
                                # 如果當前選擇的lane使用過多，而且有能量相近的少用lane
                                if lane_counts[lane] > min_count + 2 and len(underused_lanes) > 0:
                                    for underused_lane in underused_lanes:
                                        if underused_lane in sorted_indices[:2] and underused_lane != last_lane:
                                            lane = underused_lane
                                            if self.debug:
                                                print(f"Time {time:.2f}s: Beat sync - used underused lane {lane}")
                                            break
                            
                            # 更新連續計數
                            if lane == last_lane:
                                consecutive_count += 1
                            else:
                                consecutive_count = 0
                                
                        else:
                            # 如果沒有明顯的頻率特徵，使用平衡分配
                            min_count = min(lane_counts)
                            candidates = [j for j in range(num_lanes) 
                                        if lane_counts[j] == min_count and j != last_lane]
                            
                            if not candidates:
                                candidates = [j for j in range(num_lanes) if lane_counts[j] == min_count]
                            
                            lane = random.choice(candidates)
                            consecutive_count = 0
                        
                        if self.debug:
                            print(f"Time {time:.2f}s: Band energies {[f'{e:.0f}' for e in band_energies]} -> Lane {lane} (counts: {lane_counts})")
                            
                    except Exception as e:
                        if self.debug:
                            print(f"Error in FFT analysis for time {time:.2f}s: {e}")
                        # 發生錯誤時使用平衡分配
                        min_count = min(lane_counts)
                        candidates = [j for j in range(num_lanes) 
                                    if lane_counts[j] == min_count and j != last_lane]
                        if not candidates:
                            candidates = [j for j in range(num_lanes) if lane_counts[j] == min_count]
                        lane = random.choice(candidates)
                        consecutive_count = 0
                else:
                    # 如果窗口太小，使用平衡分配
                    min_count = min(lane_counts)
                    candidates = [j for j in range(num_lanes) 
                                if lane_counts[j] == min_count and j != last_lane]
                    if not candidates:
                        candidates = [j for j in range(num_lanes) if lane_counts[j] == min_count]
                    lane = random.choice(candidates)
                    consecutive_count = 0
                    if self.debug:
                        print(f"Time {time:.2f}s: Window too small, using balance -> Lane {lane}")
                
                notes.append({"time": float(time), "lane": int(lane)})
                lane_counts[lane] += 1
                last_lane = lane
        
        else:
            # 如果方法不支援，預設使用平衡節拍方法
            print(f"不支援的方法 '{method}'，使用平衡節拍方法")
            return self.assign_lanes(onsets, num_lanes, 'balanced_beat')
        
        if self.debug:
            print(f"最終lane分配統計: {dict(enumerate(lane_counts))}")
            total_notes = sum(lane_counts)
            if total_notes > 0:
                percentages = [count/total_notes*100 for count in lane_counts]
                print(f"分配百分比: {[f'{p:.1f}%' for p in percentages]}")
        
        return notes
    
    def generate_chart(self, audio_path, song_title=None, method='balanced_beat'):
        """
        生成完整的譜面
        
        Args:
            audio_path: 音訊檔案路徑
            song_title: 歌曲標題
            method: lane 分配方法 ('energy', 'balanced_beat')
                   - 'energy': 基於頻率能量分析分配lane
                   - 'balanced_beat': 基於累積數量平衡和拍點對齊分配lane (推薦)
        
        Returns:
            dict: 譜面資料
        """
        print(f"開始生成譜面: {audio_path}")
        print(f"使用方法: {method}")
        
        if not self.load_audio(audio_path):
            print("音訊載入失敗")
            return None
        
        print("正在分析音訊...")
        
        try:
            # 檢測 onset 和節拍
            onsets, tempo = self.combine_detection_methods()
            print(f"檢測完成，找到 {len(onsets)} 個 onset 點")

            # 增加開頭延遲，避免音符過早出現
            start_delay = 0.5  # 秒
            if len(onsets) > 0:
                original_onset_count = len(onsets)
                onsets = onsets[onsets >= start_delay]
                
                if self.debug and len(onsets) < original_onset_count:
                    removed_count = original_onset_count - len(onsets)
                    print(f"為提供反應時間，移除了 {removed_count} 個在 {start_delay}s 前的音符")
            
            if len(onsets) == 0:
                print("警告: 沒有檢測到任何 onset 點")
                return None
            
            # 分配 lane
            print(f"開始分配 lane，使用方法: {method}")
            notes = self.assign_lanes(onsets, method=method)
            print(f"Lane 分配完成，生成了 {len(notes)} 個音符")
            
            if len(notes) == 0:
                print("警告: 沒有生成任何音符")
                return None
            
            # 建立譜面資料結構
            chart_data = {
                "song_title": song_title or Path(audio_path).stem,
                "audio_file": str(Path(audio_path).name),
                "bpm": float(tempo),
                "duration": float(len(self.audio_data) / self.sr),
                "notes": notes,
                "note_count": int(len(notes)),
                "lanes": 4,
                "created_method": method
            }
            
            if self.debug:
                print(f"生成譜面完成:")
                print(f"- 歌曲: {chart_data['song_title']}")
                print(f"- BPM: {chart_data['bpm']:.2f}")
                print(f"- 時長: {chart_data['duration']:.2f} 秒")
                print(f"- 音符數: {chart_data['note_count']}")
                print(f"- 使用方法: {chart_data['created_method']}")
                
                # 顯示前幾個音符作為測試
                print("前5個音符:")
                for i, note in enumerate(notes[:5]):
                    print(f"  {i+1}. 時間: {note['time']:.2f}s, Lane: {note['lane']}")
            
            return chart_data
            
        except Exception as e:
            print(f"生成譜面時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_chart(self, chart_data, filename=None):
        """儲存譜面到 JSON 檔案"""
        if filename is None:
            filename = f"{chart_data['song_title']}.json"
        
        chart_path = self.charts_dir / filename
        
        try:
            with open(chart_path, 'w', encoding='utf-8') as f:
                json.dump(chart_data, f, indent=2, ensure_ascii=False)
            
            print(f"譜面已儲存: {chart_path}")
            # 確保前端收到的路徑在任何作業系統均保持 POSIX 風格，避免分隔符差異
            return chart_path.as_posix()
        except Exception as e:
            print(f"儲存譜面失敗: {e}")
            return None
    
    def visualize_analysis(self, audio_path, save_plot=False):
        """視覺化分析結果（DEBUG 用）"""
        if not hasattr(self, 'audio_data'):
            self.load_audio(audio_path)
        
        y = self.audio_data
        
        # 檢測各種特徵
        onsets_complex = self.detect_onsets(y, 'complex')
        onsets_energy = self.detect_onsets(y, 'energy')
        tempo, beats = self.detect_beats(y)
        
        # 計算 onset strength
        onset_strength = librosa.onset.onset_strength(y=y, sr=self.sr)
        times = librosa.frames_to_time(range(len(onset_strength)), sr=self.sr)
        
        # 繪圖
        plt.figure(figsize=(15, 10))
        
        # 子圖1: 波形
        plt.subplot(3, 1, 1)
        time_axis = np.linspace(0, len(y)/self.sr, len(y))
        plt.plot(time_axis, y, alpha=0.6, color='blue')
        plt.title('音訊波形')
        plt.xlabel('時間 (秒)')
        plt.ylabel('振幅')
        
        # 子圖2: Onset Strength
        plt.subplot(3, 1, 2)
        plt.plot(times, onset_strength, color='green', alpha=0.8)
        plt.vlines(onsets_complex, 0, onset_strength.max(), color='red', alpha=0.7, label='Complex Onsets')
        plt.vlines(onsets_energy, 0, onset_strength.max(), color='orange', alpha=0.7, label='Energy Onsets')
        plt.vlines(beats, 0, onset_strength.max(), color='purple', alpha=0.7, label='Beats')
        plt.title('Onset Strength 與檢測點')
        plt.xlabel('時間 (秒)')
        plt.ylabel('強度')
        plt.legend()
        
        # 子圖3: 頻譜圖
        plt.subplot(3, 1, 3)
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, y_axis='hz', x_axis='time', sr=self.sr)
        plt.colorbar(format='%+2.0f dB')
        plt.title('頻譜圖')
        
        plt.tight_layout()
        
        if save_plot:
            plot_path = self.charts_dir / 'analysis_debug.png'
            plt.savefig(plot_path, dpi=150, bbox_inches='tight')
            print(f"分析圖表已儲存: {plot_path}")
        
        plt.show()


if __name__ == "__main__":
    # 測試用
    analyzer = AudioAnalyzer(debug=True)
    
    # 假設有音訊檔案
    audio_file = "rhythm_game/assets/test.wav"
    if Path(audio_file).exists():
        # 測試新的平衡節拍方法
        print("=== 測試平衡節拍方法 ===")
        chart_data = analyzer.generate_chart(audio_file, method='balanced_beat')
        if chart_data:
            analyzer.save_chart(chart_data, f"test_balanced_beat.json")
            
        # 也可以測試舊的能量方法做比較
        print("\n=== 測試能量分析方法 ===")
        chart_data_energy = analyzer.generate_chart(audio_file, method='energy')
        if chart_data_energy:
            analyzer.save_chart(chart_data_energy, f"test_energy.json")
            
        analyzer.visualize_analysis(audio_file, save_plot=True)
    else:
        print(f"找不到音訊檔案: {audio_file}")
        print("請先使用 downloader.py 下載音樂") 