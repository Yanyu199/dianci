import json
import os
import re

import numpy as np
import torch
from scipy.interpolate import interp1d

from .net import TEM_Seq2Seq_Net


class TEMInversionEngine:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = TEM_Seq2Seq_Net(input_dim=30, output_dim=9).to(self.device)

        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "../models/best_tem_model.pt")
        scaler_path = os.path.join(base_path, "../models/data_scaler.json")

        checkpoint = torch.load(model_path, map_location=self.device)
        if isinstance(checkpoint, dict):
            if "model_state" in checkpoint:
                checkpoint = checkpoint["model_state"]
            elif "state_dict" in checkpoint:
                checkpoint = checkpoint["state_dict"]
        self.model.load_state_dict(checkpoint)
        self.model.eval()

        with open(scaler_path, "r") as f:
            scaler = json.load(f)
            self.x_min = np.array(scaler["x_min"])
            self.x_max = np.array(scaler["x_max"])
            self.y_min = np.array(scaler["y_min"])
            self.y_max = np.array(scaler["y_max"])
            self.input_dim = int(self.x_min.shape[0])

    def parse_txt(self, file_content: str):
        """Parse legacy TEM matrices or field DAT rows, then resample to the trained gate count."""
        rows = []
        for line in file_content.strip().splitlines():
            parts = [p for p in re.split(r"[\s,]+", line.strip()) if p]
            try:
                values = [float(x) for x in parts]
            except ValueError:
                continue
            if len(values) >= 2:
                rows.append(values)

        if not rows:
            raise ValueError("Z分量文件没有解析到有效数值行，请检查文件分隔符或内容。")

        arr = np.array(rows, dtype=float)
        point_count = len(np.unique(arr[:, 0].astype(int)))
        is_field_dat = arr.shape[1] >= 6 and point_count > 1 and point_count < arr.shape[0] * 0.8

        if is_field_dat:
            return self._parse_field_dat(arr)

        times = arr[:, 0]
        raw_matrix = np.abs(arr[:, 1:].T)
        return self._resample_matrix(times, raw_matrix)

    def _parse_field_dat(self, arr: np.ndarray):
        station_ids = sorted(int(v) for v in np.unique(arr[:, 0].astype(int)))
        reference_times = None

        for station in station_ids:
            block = arr[arr[:, 0].astype(int) == station]
            block = block[np.argsort(block[:, 3])]
            if reference_times is None or len(block) > len(reference_times):
                reference_times = block[:, 3]

        if reference_times is None or len(reference_times) == 0:
            raise ValueError("Z分量行式 DAT 没有有效时间道。")

        curves = []
        for station in station_ids:
            block = arr[arr[:, 0].astype(int) == station]
            block = block[np.argsort(block[:, 3])]
            times = block[:, 3]
            voltage = np.abs(block[:, 4])
            curves.append(np.interp(reference_times, times, voltage))

        return self._resample_matrix(reference_times, np.array(curves, dtype=float))

    def _resample_matrix(self, times: np.ndarray, raw_matrix: np.ndarray):
        times = np.asarray(times, dtype=float)
        raw_matrix = np.asarray(raw_matrix, dtype=float)

        valid = np.isfinite(times) & (times > 0)
        times = times[valid]
        raw_matrix = raw_matrix[:, valid]

        order = np.argsort(times)
        times = times[order]
        raw_matrix = raw_matrix[:, order]

        times, unique_indices = np.unique(times, return_index=True)
        raw_matrix = raw_matrix[:, unique_indices]

        if len(times) == 0 or raw_matrix.shape[1] == 0:
            raise ValueError("Z分量有效时间道为空，无法进行模型插值。")

        if len(times) == 1:
            return np.repeat(raw_matrix[:, :1], self.input_dim, axis=1)

        target_times = np.logspace(np.log10(times[0]), np.log10(times[-1]), self.input_dim)
        resampled_data = []
        for i in range(raw_matrix.shape[0]):
            f_interp = interp1d(times, raw_matrix[i], kind="linear", fill_value="extrapolate")
            resampled_data.append(f_interp(target_times))

        return np.array(resampled_data)

    def batch_invert(self, data_matrix: np.ndarray):
        X_scaled = (data_matrix - self.x_min) / (self.x_max - self.x_min + 1e-8)
        input_tensor = torch.Tensor(X_scaled).to(self.device)

        with torch.no_grad():
            preds_scaled = self.model(input_tensor).numpy()

        real_preds = preds_scaled * (self.y_max - self.y_min + 1e-8) + self.y_min

        results = []
        for i in range(real_preds.shape[0]):
            res = real_preds[i, :5].tolist()
            thk = real_preds[i, 5:].tolist()

            depths = [0.0]
            curr_d = 0.0
            for t in thk:
                curr_d += t
                depths.append(curr_d)

            results.append(
                {
                    "station": i + 1,
                    "resistivities": [round(r, 2) for r in res],
                    "depths": [round(d, 2) for d in depths],
                }
            )

        return results


tem_engine = TEMInversionEngine()
