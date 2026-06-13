import torch
import numpy as np
import json
import os
from scipy.interpolate import interp1d
from .net import TEM_Seq2Seq_Net


class TEMInversionEngine:
    def __init__(self):
        # 1. 初始化模型 (Web端使用 CPU 即可，1500条数据推理只需零点几秒)
        self.device = torch.device("cpu")
        self.model = TEM_Seq2Seq_Net(input_dim=30, output_dim=9).to(self.device)

        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "../models/best_tem_model.pt")
        scaler_path = os.path.join(base_path, "../models/data_scaler.json")

        # 加载权重并设置为评估模式(极其重要)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

        # 2. 加载数据归一化标尺
        with open(scaler_path, "r") as f:
            scaler = json.load(f)
            self.x_min = np.array(scaler["x_min"])
            self.x_max = np.array(scaler["x_max"])
            self.y_min = np.array(scaler["y_min"])
            self.y_max = np.array(scaler["y_max"])

    def parse_txt(self, file_content: str):
        """解析 dBzdt.txt，并将原始密集的 545 个时间道对数插值到模型所需的 30 道"""
        lines = file_content.strip().split('\n')
        times = []
        data = []

        for line in lines[1:]:  # 跳过第一行表头
            parts = line.strip().split()
            if len(parts) >= 2:
                times.append(float(parts[0]))
                data.append([abs(float(x)) for x in parts[1:]])

        times = np.array(times)
        raw_matrix = np.array(data).T  # 当前 shape: (9, 545)

        # 🌟 核心修复：计算模型训练时使用的 30 个对数时间点
        target_times = np.logspace(np.log10(times[0]), np.log10(times[-1]), 30)

        # 使用 Scipy 对每个测点进行一维曲线插值
        resampled_data = []
        for i in range(raw_matrix.shape[0]):
            f_interp = interp1d(times, raw_matrix[i], kind='linear', fill_value="extrapolate")
            resampled_data.append(f_interp(target_times))

        # 返回的 shape 是 (9, 30)，完美匹配归一化矩阵和神经网络！
        return np.array(resampled_data)

    def batch_invert(self, data_matrix: np.ndarray):
        """批量推理并解析地质结构"""
        # 1. 输入数据归一化 (使用训练时的尺子)
        X_scaled = (data_matrix - self.x_min) / (self.x_max - self.x_min + 1e-8)
        input_tensor = torch.Tensor(X_scaled).to(self.device)

        # 2. 神经网络一键批量推理
        with torch.no_grad():
            preds_scaled = self.model(input_tensor).numpy()

        # 3. 将 0~1 的预测值还原为真实的电阻率和厚度
        real_preds = preds_scaled * (self.y_max - self.y_min + 1e-8) + self.y_min

        results = []
        for i in range(real_preds.shape[0]):
            res = real_preds[i, :5].tolist()  # 前5个是电阻率
            thk = real_preds[i, 5:].tolist()  # 后4个是厚度

            # 将厚度转化为每一层的绝对深度 Z
            depths = [0.0]
            curr_d = 0.0
            for t in thk:
                curr_d += t
                depths.append(curr_d)

            results.append({
                "station": i + 1,
                "resistivities": [round(r, 2) for r in res],
                "depths": [round(d, 2) for d in depths]
            })

        return results


# 单例模式，保证服务器启动时只把模型加载进内存一次
tem_engine = TEMInversionEngine()