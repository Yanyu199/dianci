import json
import os

import numpy as np
import torch

from .net import TEM_Seq2Seq_Net
from .tem_data_parser import ParsedTEMData, parse_tem_text, resample_log_time


class TEMInversionEngine:
    def __init__(self):
        self.device = torch.device("cpu")
        base_path = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_path, "../models/best_tem_model.pt")
        scaler_path = os.path.join(base_path, "../models/data_scaler.json")

        with open(scaler_path, "r", encoding="utf-8") as f:
            raw_scaler = json.load(f)
        self.scaler = {
            key: np.asarray(value, dtype=float) if isinstance(value, list) else value
            for key, value in raw_scaler.items()
        }
        self.x_min = np.asarray(self.scaler["x_min"], dtype=float)
        self.x_max = np.asarray(self.scaler["x_max"], dtype=float)
        self.y_min = np.asarray(self.scaler["y_min"], dtype=float)
        self.y_max = np.asarray(self.scaler["y_max"], dtype=float)
        self.input_dim = int(self.x_min.shape[0])
        self.output_dim = int(self.y_min.shape[0])

        self.model = TEM_Seq2Seq_Net(input_dim=self.input_dim, output_dim=self.output_dim).to(self.device)
        checkpoint = torch.load(model_path, map_location=self.device)
        if isinstance(checkpoint, dict):
            if "model_state" in checkpoint:
                checkpoint = checkpoint["model_state"]
            elif "state_dict" in checkpoint:
                checkpoint = checkpoint["state_dict"]
        self.model.load_state_dict(checkpoint)
        self.model.eval()

    def parse_txt(self, file_content: str):
        component = parse_tem_text(file_content, component_name="Z")
        return self.prepare_component_matrix(component)

    def prepare_component_matrix(self, component: ParsedTEMData):
        target_times = self._target_times(component.times)
        return resample_log_time(component.times, component.responses, target_times)

    def invert_component(self, component: ParsedTEMData):
        return self.batch_invert(self.prepare_component_matrix(component))

    def batch_invert(self, data_matrix: np.ndarray):
        x_scaled = self.scale_inputs(data_matrix)
        input_tensor = torch.tensor(x_scaled, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            preds_scaled = self.model(input_tensor).cpu().numpy()
        physical = self.inverse_outputs(preds_scaled)

        results = []
        for i in range(physical.shape[0]):
            resistivities, thicknesses = self._split_model_outputs(physical[i])
            depths = [0.0]
            current_depth = 0.0
            for thickness in thicknesses:
                current_depth += max(float(thickness), 0.0)
                depths.append(current_depth)
            while len(depths) < len(resistivities):
                step = depths[-1] - depths[-2] if len(depths) > 1 else 1.0
                depths.append(depths[-1] + max(step, 1.0))
            results.append(
                {
                    "station": i + 1,
                    "resistivities": [round(float(v), 6) for v in resistivities],
                    "depths": [round(float(v), 6) for v in depths[: len(resistivities)]],
                }
            )
        return results

    def _target_times(self, source_times: np.ndarray) -> np.ndarray:
        if "target_times" in self.scaler:
            return np.asarray(self.scaler["target_times"], dtype=float)
        if {"time_min", "time_max", "time_channels"}.issubset(self.scaler):
            return np.logspace(
                np.log10(float(self.scaler["time_min"])),
                np.log10(float(self.scaler["time_max"])),
                int(self.scaler["time_channels"]),
            )
        source_times = np.asarray(source_times, dtype=float)
        return np.logspace(np.log10(source_times[0]), np.log10(source_times[-1]), self.input_dim)

    def _scaler_looks_log_space(self) -> bool:
        if self.scaler.get("space") == "log10" or "real_log_max" in self.scaler:
            return True
        return bool(np.nanmax(np.abs(self.x_max)) < 30 and np.nanmax(np.abs(self.x_min)) < 30)

    def scale_inputs(self, responses: np.ndarray) -> np.ndarray:
        responses = np.asarray(responses, dtype=float)
        if responses.ndim != 2:
            raise ValueError("Z 反演输入必须是二维矩阵：测点 x 时间道。")
        if responses.shape[1] != self.input_dim:
            raise ValueError(f"模型需要 {self.input_dim} 个时间道，当前为 {responses.shape[1]} 个。")
        if self._scaler_looks_log_space():
            x_values = np.log10(np.abs(responses) + 1e-12)
        else:
            x_values = np.abs(responses)
        if self.scaler.get("scaler_type") == "standard" and "x_mean" in self.scaler:
            return (x_values - self.scaler["x_mean"]) / (self.scaler["x_std"] + 1e-8)
        return (x_values - self.x_min) / (self.x_max - self.x_min + 1e-8)

    def inverse_outputs(self, outputs: np.ndarray) -> np.ndarray:
        y_scaled = np.asarray(outputs, dtype=float)
        if "output_plus" in self.scaler:
            y_scaled = y_scaled - float(self.scaler.get("output_plus", 10.0))
        if self.scaler.get("scaler_type") == "standard" and "y_mean" in self.scaler:
            y_values = y_scaled * (self.scaler["y_std"] + 1e-8) + self.scaler["y_mean"]
        else:
            y_values = y_scaled * (self.y_max - self.y_min + 1e-8) + self.y_min
        if self.scaler.get("target_transform") == "rho_log_thickness_linear":
            physical = y_values.copy()
            physical[:, ::2] = 10 ** physical[:, ::2]
            physical[:, 1::2] = np.maximum(physical[:, 1::2], 0.0)
            return physical
        return np.maximum(y_values, 0.0)

    def _split_model_outputs(self, row: np.ndarray):
        layer_num = int(self.scaler.get("layer_num", (len(row) + 1) // 2))
        if self.scaler.get("target_transform") == "rho_log_thickness_linear":
            resistivities = [float(row[i * 2]) for i in range(layer_num) if i * 2 < len(row)]
            thicknesses = [float(row[i * 2 + 1]) for i in range(layer_num - 1) if i * 2 + 1 < len(row)]
            return resistivities, thicknesses
        resistivity_count = (len(row) + 1) // 2
        return row[:resistivity_count].tolist(), row[resistivity_count:].tolist()


tem_engine = TEMInversionEngine()
