import math
import os
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .tem_data_parser import ParsedTEMData


DEFAULT_PARAMS = {
    "x_range": (-30.0, 30.0),
    "y_range": (-30.0, 30.0),
    "grid_size": 3.0,
    "radius_scale": 30.0,
    "direction_base": 0.7,
    "direction_gain": 0.3,
}


def generate_result_points(
    x_component: ParsedTEMData,
    y_component: ParsedTEMData,
    z_component: ParsedTEMData,
    inversion_results: List[dict],
    params: Optional[dict] = None,
) -> Tuple[List[List[float]], Dict]:
    cfg = dict(DEFAULT_PARAMS)
    if params:
        cfg.update({k: v for k, v in params.items() if v is not None})

    x_values = _axis_values(cfg["x_range"], float(cfg["grid_size"]))
    y_values = _axis_values(cfg["y_range"], float(cfg["grid_size"]))
    radius_limit = float(
        cfg.get(
            "radius_limit",
            min(
                max(abs(float(v)) for v in x_values),
                max(abs(float(v)) for v in y_values),
            ),
        )
    )
    depth_map = cfg.get("depth_map") or _default_depth_map(z_component.stations)
    inversion_by_station = _map_inversion(z_component.stations, inversion_results)
    background = _background_resistivity(inversion_by_station)
    directions = _station_direction_profiles(x_component, y_component, z_component.stations)

    points: List[List[float]] = []
    for station in z_component.stations:
        inversion = inversion_by_station.get(station)
        if not inversion:
            continue
        layer_edges = _layer_edges(inversion["depths"], len(inversion["resistivities"]))
        depth = float(depth_map.get(station, station))
        direction = directions.get(station, {"angle": 0.0, "strength": 0.0})
        preferred_angle = float(direction["angle"])
        strength = float(direction["strength"])
        for x_offset in x_values:
            for y_offset in y_values:
                radius = math.hypot(float(x_offset), float(y_offset))
                if radius > radius_limit + 1e-9:
                    continue
                base = _resistivity_at_radius(radius, layer_edges, inversion["resistivities"])
                theta = math.atan2(float(y_offset), float(x_offset)) if radius > 1e-9 else preferred_angle
                direction_weight = float(cfg["direction_base"]) + float(cfg["direction_gain"]) * strength * max(
                    0.0, math.cos(theta - preferred_angle)
                )
                radial_weight = math.exp(-((radius / max(float(cfg["radius_scale"]), 1e-9)) ** 2))
                value = background + (float(base) - background) * direction_weight * radial_weight
                points.append([round(float(x_offset), 6), round(float(y_offset), 6), round(depth, 6), round(float(value), 6)])

    arr = np.asarray(points, dtype=float)
    metadata = {
        "station_count": int(len(z_component.stations)),
        "time_count": int(len(z_component.times)),
        "point_count": int(len(points)),
        "x_range": [float(x_values[0]), float(x_values[-1])] if len(x_values) else list(cfg["x_range"]),
        "y_range": [float(y_values[0]), float(y_values[-1])] if len(y_values) else list(cfg["y_range"]),
        "grid_size": float(cfg["grid_size"]),
        "radius_limit": radius_limit,
        "background_resistivity": float(background),
        "value_min": float(np.nanmin(arr[:, 3])) if arr.size else None,
        "value_max": float(np.nanmax(arr[:, 3])) if arr.size else None,
    }
    return points, metadata


def generate_sections(points: List[List[float]], grid_size: float = 3.0) -> Tuple[List[List[float]], List[List[float]]]:
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return [], []
    tol = max(float(grid_size) * 0.51, 1e-9)
    x_section = _section_at_axis(arr, axis="y", tolerance=tol)
    y_section = _section_at_axis(arr, axis="x", tolerance=tol)
    return x_section, y_section


def export_3d_result_dat(points: Iterable[Iterable[float]], output_path: str) -> str:
    _write_rows(points, output_path, column_count=4)
    return output_path


def export_section_dat(section: Iterable[Iterable[float]], output_path: str) -> str:
    _write_rows(section, output_path, column_count=3)
    return output_path


def _write_rows(rows: Iterable[Iterable[float]], output_path: str, column_count: int) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            values = list(row)
            if len(values) != column_count:
                raise ValueError(f"导出 DAT 需要 {column_count} 列，当前行是 {len(values)} 列。")
            f.write(" ".join(_format_value(v) for v in values) + "\n")


def _format_value(value: float) -> str:
    return f"{float(value):.8g}"


def _write_rows(rows: Iterable[Iterable[float]], output_path: str, column_count: int) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            values = list(row)
            if len(values) < column_count:
                raise ValueError(f"DAT export needs {column_count} columns, got {len(values)}.")
            f.write(" ".join(_format_value(v) for v in values[:column_count]) + "\n")


def _axis_values(value_range, grid_size: float) -> np.ndarray:
    start, end = float(value_range[0]), float(value_range[1])
    if grid_size <= 0:
        raise ValueError("grid_size 必须大于 0。")
    count = int(round((end - start) / grid_size))
    values = start + np.arange(count + 1, dtype=float) * grid_size
    if values[-1] < end - grid_size * 0.25:
        values = np.append(values, end)
    if start < 0 < end and not np.any(np.isclose(values, 0.0, atol=grid_size * 1e-6)):
        values = np.sort(np.append(values, 0.0))
    return values


def _default_depth_map(stations: List[int]) -> Dict[int, float]:
    return {int(station): float(station) for station in stations}


def _map_inversion(stations: List[int], inversion_results: List[dict]) -> Dict[int, dict]:
    mapped = {}
    for idx, result in enumerate(inversion_results):
        station = int(stations[idx]) if idx < len(stations) else int(result.get("station", idx + 1))
        resistivities = [abs(float(v)) for v in result.get("resistivities", []) if np.isfinite(float(v))]
        depths = [abs(float(v)) for v in result.get("depths", []) if np.isfinite(float(v))]
        if resistivities:
            mapped[station] = {"resistivities": resistivities, "depths": depths}
    return mapped


def _background_resistivity(inversion_by_station: Dict[int, dict]) -> float:
    values = [rho for item in inversion_by_station.values() for rho in item["resistivities"]]
    if not values:
        return 1.0
    arr = np.asarray(values, dtype=float)
    return float(np.nanmedian(arr[np.isfinite(arr)]))


def _layer_edges(depths: List[float], layer_count: int) -> List[float]:
    edges = sorted({abs(float(v)) for v in depths if np.isfinite(float(v))})
    if not edges or edges[0] > 1e-9:
        edges.insert(0, 0.0)
    if len(edges) > 1:
        steps = np.diff(np.asarray(edges, dtype=float))
        step = float(np.nanmedian(steps[steps > 1e-9])) if np.any(steps > 1e-9) else 1.0
    else:
        step = max(edges[-1] if edges else 0.0, 1.0)
    step = max(step, 1.0)
    while len(edges) < layer_count + 1:
        edges.append(edges[-1] + step)
    return edges[: layer_count + 1]


def _resistivity_at_radius(radius: float, layer_edges: List[float], resistivities: List[float]) -> float:
    for idx, rho in enumerate(resistivities):
        inner = layer_edges[idx] if idx < len(layer_edges) else 0.0
        outer = layer_edges[idx + 1] if idx + 1 < len(layer_edges) else float("inf")
        if inner <= radius <= outer:
            return float(rho)
    return float(resistivities[-1])


def _station_direction_profiles(
    x_component: ParsedTEMData,
    y_component: ParsedTEMData,
    stations: List[int],
) -> Dict[int, dict]:
    x_index = {int(station): idx for idx, station in enumerate(x_component.stations)}
    y_index = {int(station): idx for idx, station in enumerate(y_component.stations)}
    strengths = []
    raw_profiles = {}
    for station in stations:
        if station not in x_index or station not in y_index:
            continue
        x_row = np.nan_to_num(x_component.responses[x_index[station]], nan=0.0, posinf=0.0, neginf=0.0)
        y_row = np.nan_to_num(y_component.responses[y_index[station]], nan=0.0, posinf=0.0, neginf=0.0)
        strength_curve = np.sqrt(x_row * x_row + y_row * y_row)
        idx = int(np.nanargmax(strength_curve)) if strength_curve.size else 0
        vx = float(x_row[idx]) if x_row.size else 0.0
        vy = float(y_row[idx]) if y_row.size else 0.0
        strength = math.sqrt(vx * vx + vy * vy)
        raw_profiles[int(station)] = {"angle": math.atan2(vy, vx), "strength": strength}
        strengths.append(strength)

    scale = float(np.nanpercentile(strengths, 90)) if strengths else 1.0
    scale = max(scale, 1e-12)
    return {
        station: {
            "angle": profile["angle"],
            "strength": float(np.clip(profile["strength"] / scale, 0.0, 1.0)),
        }
        for station, profile in raw_profiles.items()
    }


def _section_at_axis(arr: np.ndarray, axis: str, tolerance: float) -> List[List[float]]:
    # arr columns: x_offset, y_offset, depth, value.
    axis_col = 1 if axis == "y" else 0
    offset_col = 0 if axis == "y" else 1
    exact = arr[np.abs(arr[:, axis_col]) <= tolerance]
    if exact.size:
        out = exact[:, [2, offset_col, 3]]
        order = np.lexsort((out[:, 1], out[:, 0]))
        return np.round(out[order], 6).tolist()

    rows = []
    other_offsets = np.unique(arr[:, offset_col])
    depths = np.unique(arr[:, 2])
    for depth in depths:
        depth_rows = arr[np.isclose(arr[:, 2], depth)]
        for offset in other_offsets:
            line = depth_rows[np.isclose(depth_rows[:, offset_col], offset)]
            if line.shape[0] < 2:
                continue
            order = np.argsort(line[:, axis_col])
            coords = line[order, axis_col]
            values = line[order, 3]
            if coords[0] <= 0 <= coords[-1]:
                rows.append([float(depth), float(offset), float(np.interp(0.0, coords, values))])
    return np.round(np.asarray(rows, dtype=float), 6).tolist() if rows else []
