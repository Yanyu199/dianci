import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class ParsedTEMData:
    stations: List[int]
    times: np.ndarray
    responses: np.ndarray
    aux_values: np.ndarray
    angle_cols: np.ndarray
    metadata: Dict = field(default_factory=dict)


def decode_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "gb2312"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def split_numeric_line(line: str) -> List[str]:
    return [part for part in re.split(r"[\s,;\t]+", line.strip()) if part]


def read_numeric_rows(text: str) -> Tuple[np.ndarray, Optional[List[str]]]:
    rows: List[List[float]] = []
    header: Optional[List[str]] = None
    for raw_line in io.StringIO(text):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = split_numeric_line(line)
        if len(parts) < 2:
            continue
        try:
            rows.append([float(part) for part in parts])
        except ValueError:
            header = parts
    if not rows:
        raise ValueError("DAT 文件没有解析到有效数值行。")
    return np.asarray(rows, dtype=float), header


def normalize_time_units(raw_times: np.ndarray) -> Tuple[np.ndarray, str]:
    raw_times = np.asarray(raw_times, dtype=float)
    if raw_times.size == 0 or not np.all(np.isfinite(raw_times)):
        raise ValueError("时间道包含空值、NaN 或 Inf。")
    max_time = float(np.nanmax(raw_times))
    if max_time > 10:
        return raw_times * 1e-6, "microsecond"
    if max_time > 0.1:
        return raw_times * 1e-3, "millisecond"
    return raw_times, "second"


def _is_regular_long_dat(arr: np.ndarray) -> bool:
    if arr.ndim != 2 or arr.shape[1] < 5:
        return False
    station_count = len(np.unique(arr[:, 0].astype(int)))
    time_count = len(np.unique(arr[:, 3]))
    return station_count > 1 and time_count > 1 and arr.shape[0] >= station_count * time_count * 0.95


def parse_tem_text(text: str, component_name: str = "TEM") -> ParsedTEMData:
    arr, header = read_numeric_rows(text)
    if arr.ndim != 2:
        raise ValueError(f"{component_name} 文件没有形成二维数值表。")
    if np.any(~np.isfinite(arr[:, : min(arr.shape[1], 6)])):
        raise ValueError(f"{component_name} 文件关键列存在 NaN/Inf。")
    if _is_regular_long_dat(arr):
        return _parse_long_dat(arr, component_name)
    return _parse_wide_table(arr, header, component_name)


def parse_tem_bytes(payload: bytes, component_name: str = "TEM") -> ParsedTEMData:
    return parse_tem_text(decode_bytes(payload), component_name=component_name)


def _parse_long_dat(arr: np.ndarray, component_name: str) -> ParsedTEMData:
    stations = sorted(int(v) for v in np.unique(arr[:, 0].astype(int)))
    raw_times = np.unique(arr[:, 3])
    times, unit = normalize_time_units(raw_times)
    order = np.argsort(times)
    times = times[order]
    raw_times = raw_times[order]

    responses = []
    aux_values = []
    angle_rows = []
    for station in stations:
        block = arr[arr[:, 0].astype(int) == station]
        lookup = {float(row[3]): row for row in block}
        station_response = []
        station_aux = []
        station_angles = []
        for raw_time in raw_times:
            row = lookup.get(float(raw_time))
            if row is None:
                station_response.append(np.nan)
                station_aux.append(np.nan)
                station_angles.append([np.nan, np.nan])
                continue
            station_response.append(float(row[4]))
            station_aux.append(float(row[5]) if arr.shape[1] >= 6 else np.nan)
            if arr.shape[1] >= 9:
                station_angles.append([float(row[7]), float(row[8])])
            elif arr.shape[1] >= 8:
                station_angles.append([float(row[7]), np.nan])
            else:
                station_angles.append([np.nan, np.nan])
        responses.append(station_response)
        aux_values.append(station_aux)
        angle_rows.append(station_angles)

    responses_arr = np.asarray(responses, dtype=float)
    aux_arr = np.asarray(aux_values, dtype=float)
    angle_arr = np.asarray(angle_rows, dtype=float)
    if not np.all(np.isfinite(responses_arr)):
        raise ValueError(f"{component_name} 文件存在缺失时间道或非有限响应值。")

    return ParsedTEMData(
        stations=stations,
        times=times,
        responses=responses_arr,
        aux_values=aux_arr,
        angle_cols=angle_arr,
        metadata={
            "format": "long_dat",
            "component": component_name,
            "raw_column_count": int(arr.shape[1]),
            "station_count": int(len(stations)),
            "time_count": int(len(times)),
            "time_unit_inferred": unit,
            "raw_time_min": float(np.min(raw_times)),
            "raw_time_max": float(np.max(raw_times)),
            "time_min": float(times[0]),
            "time_max": float(times[-1]),
            "columns": {
                "station": 1,
                "time": 4,
                "response": 5,
                "aux": 6 if arr.shape[1] >= 6 else None,
                "angle_cols": [8, 9] if arr.shape[1] >= 9 else [],
            },
        },
    )


def _parse_wide_table(arr: np.ndarray, header: Optional[List[str]], component_name: str) -> ParsedTEMData:
    if arr.shape[1] < 2:
        raise ValueError(f"{component_name} 宽表格式至少需要 time + 一个测点响应列。")
    raw_times = arr[:, 0]
    times, unit = normalize_time_units(raw_times)
    order = np.argsort(times)
    times = times[order]
    responses = arr[:, 1:].T.astype(float)[:, order]
    stations = list(range(1, responses.shape[0] + 1))
    aux_values = np.zeros_like(responses)
    angle_cols = np.full((responses.shape[0], responses.shape[1], 2), np.nan, dtype=float)
    if header and len(header) == arr.shape[1]:
        station_names = header[1:]
    else:
        station_names = [str(station) for station in stations]
    return ParsedTEMData(
        stations=stations,
        times=times,
        responses=responses,
        aux_values=aux_values,
        angle_cols=angle_cols,
        metadata={
            "format": "wide_table",
            "component": component_name,
            "station_count": int(len(stations)),
            "time_count": int(len(times)),
            "time_unit_inferred": unit,
            "raw_time_min": float(np.min(raw_times)),
            "raw_time_max": float(np.max(raw_times)),
            "time_min": float(times[0]),
            "time_max": float(times[-1]),
            "station_names": station_names,
        },
    )


def validate_component(component: ParsedTEMData, label: str) -> Dict:
    responses = np.asarray(component.responses, dtype=float)
    finite = np.isfinite(responses)
    finite_ratio = float(np.mean(finite)) if responses.size else 0.0
    abs_values = np.abs(responses[finite])
    zero_like_ratio = float(np.mean(abs_values <= 1e-30)) if abs_values.size else 1.0
    if responses.size == 0:
        raise ValueError(f"{label} 文件响应矩阵为空。")
    if finite_ratio < 0.98:
        raise ValueError(f"{label} 文件 NaN/Inf 比例过高：{1 - finite_ratio:.2%}。")
    if zero_like_ratio > 0.95:
        raise ValueError(f"{label} 文件响应值几乎全为 0，无法成像。")
    if not np.all(np.diff(component.times) > 0):
        raise ValueError(f"{label} 文件时间道不是严格递增。")
    if component.responses.shape[1] != len(component.times):
        raise ValueError(f"{label} 文件测点响应列数与时间道数不一致。")
    return {
        "label": label,
        "station_count": int(len(component.stations)),
        "time_count": int(len(component.times)),
        "finite_ratio": finite_ratio,
        "zero_like_ratio": zero_like_ratio,
        "response_min": float(np.nanmin(responses)),
        "response_max": float(np.nanmax(responses)),
        "time_min": float(component.times[0]),
        "time_max": float(component.times[-1]),
        "metadata": component.metadata,
    }


def validate_three_components(x: ParsedTEMData, y: ParsedTEMData, z: ParsedTEMData) -> Dict:
    reports = {
        "x": validate_component(x, "X"),
        "y": validate_component(y, "Y"),
        "z": validate_component(z, "Z"),
    }
    station_sets = [x.stations, y.stations, z.stations]
    if not (station_sets[0] == station_sets[1] == station_sets[2]):
        raise ValueError(
            "X/Y/Z 测点号不一致："
            f"X={len(x.stations)} 个，Y={len(y.stations)} 个，Z={len(z.stations)} 个。"
        )
    if not (len(x.times) == len(y.times) == len(z.times)):
        raise ValueError(
            "X/Y/Z 时间道数量不一致："
            f"X={len(x.times)}，Y={len(y.times)}，Z={len(z.times)}。"
        )
    if not (np.allclose(x.times, y.times, rtol=1e-5, atol=1e-12) and np.allclose(x.times, z.times, rtol=1e-5, atol=1e-12)):
        raise ValueError("X/Y/Z 时间道范围或时间道值不一致，无法直接融合。")
    reports["summary"] = {
        "station_count": int(len(x.stations)),
        "time_count": int(len(x.times)),
        "time_min": float(x.times[0]),
        "time_max": float(x.times[-1]),
    }
    return reports


def resample_log_time(times: np.ndarray, responses: np.ndarray, target_times: Sequence[float]) -> np.ndarray:
    times = np.asarray(times, dtype=float)
    target = np.asarray(target_times, dtype=float)
    if times.shape == target.shape and np.allclose(times, target):
        return np.asarray(responses, dtype=float).copy()
    if np.any(times <= 0) or np.any(target <= 0):
        raise ValueError("对数时间重采样要求时间道全部为正数。")
    log_t = np.log10(times)
    log_target = np.log10(target)
    out = []
    for row in np.asarray(responses, dtype=float):
        dominant_sign = -1.0 if np.sum(row < 0) > np.sum(row > 0) else 1.0
        log_y = np.log10(np.abs(row) + 1e-30)
        interp = np.interp(log_target, log_t, log_y, left=log_y[0], right=log_y[-1])
        out.append(dominant_sign * (10 ** interp))
    return np.asarray(out, dtype=float)
