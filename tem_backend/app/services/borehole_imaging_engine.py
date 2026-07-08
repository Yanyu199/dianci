import io
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .inversion_engine import tem_engine
from .result_dat_generator import generate_result_points, generate_sections
from .tem_data_parser import ParsedTEMData, parse_tem_text, validate_three_components


@dataclass
class ComponentData:
    stations: List[int]
    times: np.ndarray
    voltage: np.ndarray
    apparent_resistivity: np.ndarray


class BoreholeImagingEngine:
    """Pure Python borehole TEM imaging based on trajectory, X/Y direction and Z inversion."""

    def decode_bytes(self, payload: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="ignore")

    def parse_component_text(self, text: str) -> ComponentData:
        return self._component_from_parsed(parse_tem_text(text))

    def _component_from_parsed(self, parsed: ParsedTEMData) -> ComponentData:
        return ComponentData(
            stations=parsed.stations,
            times=parsed.times,
            voltage=parsed.responses,
            apparent_resistivity=parsed.aux_values,
        )

    def _parse_field_rows(self, arr: np.ndarray) -> ComponentData:
        station_ids = sorted(int(v) for v in np.unique(arr[:, 0].astype(int)))
        grouped: Dict[int, np.ndarray] = {}
        common_times: Optional[np.ndarray] = None

        for station in station_ids:
            block = arr[arr[:, 0].astype(int) == station]
            order = np.argsort(block[:, 3])
            block = block[order]
            grouped[station] = block
            if common_times is None or len(block) > len(common_times):
                common_times = block[:, 3]

        if common_times is None or len(common_times) == 0:
            raise ValueError("The TEM field file does not contain valid time channels.")

        voltage_rows = []
        rho_rows = []
        for station in station_ids:
            block = grouped[station]
            time = block[:, 3]
            voltage = block[:, 4]
            rho = np.abs(block[:, 5]) if block.shape[1] > 5 else np.zeros_like(voltage)
            voltage_rows.append(np.interp(common_times, time, voltage))
            rho_rows.append(np.interp(common_times, time, rho))

        return ComponentData(
            stations=station_ids,
            times=common_times.astype(float),
            voltage=np.asarray(voltage_rows, dtype=float),
            apparent_resistivity=np.asarray(rho_rows, dtype=float),
        )

    def parse_trajectory_excel(self, payload: bytes) -> List[dict]:
        try:
            import pandas as pd
        except ImportError as exc:
            raise ValueError("Reading trajectory Excel files requires pandas/openpyxl on the backend.") from exc

        raw = pd.read_excel(io.BytesIO(payload), sheet_name=0, header=None)
        header_idx = None
        for idx in range(min(8, len(raw))):
            row_text = " ".join(str(v) for v in raw.iloc[idx].tolist())
            if "孔深" in row_text and "倾角" in row_text:
                header_idx = idx
                break
        if header_idx is None:
            header_idx = 1

        df = pd.read_excel(io.BytesIO(payload), sheet_name=0, header=header_idx)
        df = df.dropna(how="all")
        df.columns = [str(c).strip() for c in df.columns]

        def find_col(*keywords: str) -> str:
            fallback_index = getattr(find_col, "_fallback_index", 0)
            setattr(find_col, "_fallback_index", fallback_index + 1)
            for col in df.columns:
                if all(k in col for k in keywords):
                    return col
            if fallback_index < len(df.columns):
                return df.columns[fallback_index]
            raise ValueError(f"Trajectory Excel is missing column containing: {keywords}")

        md_col = find_col("孔深")
        inc_col = find_col("倾角")
        azi_col = find_col("方位")
        vertical_col = find_col("上下")
        forward_col = find_col("水平")
        lateral_col = find_col("左右")

        out = []
        for _, row in df.iterrows():
            try:
                md = float(row[md_col])
                inc = float(row[inc_col])
                azi = float(row[azi_col])
                vertical = float(row[vertical_col])
                forward = float(row[forward_col])
                lateral = float(row[lateral_col])
            except (TypeError, ValueError):
                continue
            if not np.isfinite([md, inc, azi, vertical, forward, lateral]).all():
                continue
            out.append(
                {
                    "md": md,
                    "inclination": inc,
                    "azimuth": azi,
                    # Scene axes follow the paper: X right, Y down, Z drilling direction.
                    "x": lateral,
                    "y": -vertical,
                    "z": forward,
                }
            )

        if len(out) < 2:
            raise ValueError("Trajectory Excel did not yield enough valid trajectory points.")
        out.sort(key=lambda p: p["md"])
        return out

    def generate_scene(
        self,
        x_payload: bytes,
        y_payload: bytes,
        z_payload: bytes,
        trajectory_payload: bytes,
        params: Optional[dict] = None,
    ) -> dict:
        params = params or {}
        x_text = self.decode_bytes(x_payload)
        y_text = self.decode_bytes(y_payload)
        z_text = self.decode_bytes(z_payload)
        parsed_x = parse_tem_text(x_text, component_name="X")
        parsed_y = parse_tem_text(y_text, component_name="Y")
        parsed_z = parse_tem_text(z_text, component_name="Z")
        qc_report = validate_three_components(parsed_x, parsed_y, parsed_z)
        comp_x = self._component_from_parsed(parsed_x)
        comp_y = self._component_from_parsed(parsed_y)
        comp_z = self._component_from_parsed(parsed_z)
        trajectory = self.parse_trajectory_excel(trajectory_payload)

        inversion_results = tem_engine.invert_component(parsed_z)
        inversion_by_station = self._map_inversion_to_station(comp_z.stations, inversion_results)

        stations = sorted(set(comp_x.stations) & set(comp_y.stations) & set(comp_z.stations) & set(inversion_by_station))
        if not stations:
            raise ValueError("X/Y/Z components and Z inversion results have no common station numbers.")

        xy_profiles = self._xy_direction_profiles(comp_x, comp_y, stations)
        rho_values = [
            self._display_resistivity(float(rho))
            for station in stations
            for rho in inversion_by_station[station]["resistivities"]
        ]
        thresholds = self._color_thresholds_from_values(rho_values)
        background_resistivity = self._background_resistivity(rho_values, thresholds)
        anomaly_regions = self._detect_anomaly_regions(stations, inversion_by_station, xy_profiles, thresholds)
        anomaly_lookup = {
            (cell["station"], cell["layer_index"]): region
            for region in anomaly_regions
            for cell in region["cells"]
        }

        max_md = trajectory[-1]["md"]
        min_station = min(stations)
        max_station = max(stations)
        radius_limit = self._radius_limit_from_params(params)

        station_markers = []
        columns = []
        layer_points = []
        surface_points = []
        volume_points = []
        actual_sections = []

        for station in stations:
            station_md = self._station_to_md(station, min_station, max_station, max_md)
            origin, tangent, right, down, interp_info = self._frame_at_md(trajectory, station_md)
            station_markers.append(
                {
                    "station": station,
                    "md": round(station_md, 3),
                    "x": round(float(origin[0]), 3),
                    "y": round(float(origin[1]), 3),
                    "z": round(float(origin[2]), 3),
                    "inclination": interp_info["inclination"],
                    "azimuth": interp_info["azimuth"],
                }
            )
            columns.append(
                {
                    "station": station,
                    "origin": origin.tolist(),
                    "right": right.tolist(),
                    "down": down.tolist(),
                    "tangent": tangent.tolist(),
                }
            )

            inversion = inversion_by_station[station]
            layer_edges = self._layer_edges(inversion["depths"], len(inversion["resistivities"]))
            layer_edges = self._scale_layer_edges(layer_edges, radius_limit)
            section_layers = []
            for layer_index, rho in enumerate(inversion["resistivities"]):
                inner_radius = layer_edges[layer_index]
                outer_radius = layer_edges[layer_index + 1]
                resistivity = self._display_resistivity(float(rho))
                if not np.isfinite(resistivity) or resistivity <= 0:
                    continue

                region = anomaly_lookup.get((station, layer_index))
                if region:
                    resistivity_class = region["kind"]
                    class_code = self._class_code(resistivity_class)
                    direction_info = {
                        "angle": region["angle"],
                        "quadrant": region["quadrant"],
                        "strength": region["strength"],
                    }
                    render_resistivity = resistivity
                    region_id = region["id"]
                else:
                    resistivity_class = "normal"
                    class_code = 0
                    direction_info = self._layer_direction(
                        xy_profiles.get(station),
                        layer_index,
                        len(inversion["resistivities"]),
                    )
                    render_resistivity = self._normal_region_resistivity(resistivity, background_resistivity, thresholds)
                    region_id = None
                layer_points.append(
                    {
                        "station": station,
                        "layer": layer_index + 1,
                        "inner_radius": round(inner_radius, 3),
                        "outer_radius": round(outer_radius, 3),
                        "resistivity": round(resistivity, 6),
                        "resistivity_class": resistivity_class,
                        "preferred_angle": round(math.degrees(direction_info["angle"]), 3),
                        "quadrant": direction_info["quadrant"],
                        "xy_strength": round(direction_info["strength"], 6),
                    "region_id": region_id,
                    }
                )
                section_layers.append(
                    {
                        "layer_index": layer_index,
                        "layer": layer_index + 1,
                        "inner_radius": inner_radius,
                        "outer_radius": outer_radius,
                        "resistivity": resistivity,
                        "render_resistivity": render_resistivity,
                        "class_code": class_code,
                        "direction": direction_info,
                        "region_id": region_id,
                    }
                )
            actual_sections.append({"station": station, "md": station_md, "layers": section_layers})

        render_sections = self._interpolate_sections(
            actual_sections=actual_sections,
            trajectory=trajectory,
            anomaly_regions=anomaly_regions,
            background_resistivity=background_resistivity,
            thresholds=thresholds,
        )
        for section in render_sections:
            origin = section["origin"]
            right = section["right"]
            down = section["down"]
            for layer in section["layers"]:
                surface_points.extend(
                    self._cylindrical_layer_points(
                        origin=origin,
                        right=right,
                        down=down,
                        station=section["station"],
                        layer=layer["layer"],
                        inner_radius=layer["inner_radius"],
                        outer_radius=layer["outer_radius"],
                        resistivity=layer["render_resistivity"],
                        background_resistivity=background_resistivity,
                        class_code=layer["class_code"],
                        point_type="resistivity-gradient",
                        preferred_angle=layer["direction"]["angle"] if layer["class_code"] else None,
                        direction_strength=layer["direction"]["strength"] if layer["class_code"] else 0.0,
                        region_id=layer["region_id"],
                        radial_samples=1,
                        md=section["md"],
                    )
                )
                volume_points.extend(
                    self._cylindrical_layer_points(
                        origin=origin,
                        right=right,
                        down=down,
                        station=section["station"],
                        layer=layer["layer"],
                        inner_radius=layer["inner_radius"],
                        outer_radius=layer["outer_radius"],
                        resistivity=layer["render_resistivity"],
                        background_resistivity=background_resistivity,
                        class_code=layer["class_code"],
                        point_type="resistivity-gradient",
                        preferred_angle=layer["direction"]["angle"] if layer["class_code"] else None,
                        direction_strength=layer["direction"]["strength"] if layer["class_code"] else 0.0,
                        region_id=layer["region_id"],
                        radial_samples=4,
                        md=section["md"],
                    )
                )

        render_points = volume_points if volume_points else surface_points
        self._attach_resistivity_class(render_points, thresholds)
        self._attach_resistivity_class(surface_points, thresholds)
        result_points = self._result_rows_from_render_points(render_points)
        x_section, y_section = self._section_rows_from_render_points(render_points)
        result_metadata = self._result_points_metadata(
            result_points,
            coordinate_mode="trajectory_xyz",
            radius_limit=radius_limit,
            longitudinal_section_count=len(render_sections),
            anomaly_region_count=len(anomaly_regions),
        )
        voxels = self._voxelize(render_points)
        return {
            "trajectory": trajectory,
            "stations": station_markers,
            "columns": columns,
            "anomaly_points": layer_points,
            "cylinder_points": surface_points,
            "volume_point_count": len(volume_points),
            "points": result_points,
            "x_section": x_section,
            "y_section": y_section,
            "voxels": voxels,
            "bounds": self._bounds(trajectory, render_points),
            "meta": {
                "qc": qc_report,
                "result_points": result_metadata,
                "station_count": len(stations),
                "longitudinal_section_count": len(render_sections),
                "layer_count": max(len(v["resistivities"]) for v in inversion_by_station.values()),
                "point_count": len(render_points),
                "render_point_count": len(voxels),
                "color_thresholds": thresholds,
                "background_resistivity": round(background_resistivity, 6),
                "class_codes": {"normal": 0, "low": 1, "high": 2},
                "anomaly_regions": self._region_summaries(anomaly_regions),
                "algorithm": "pt_z_inversion_trajectory_cylindrical_resistivity_body",
            },
        }

    def _moving_residual(self, values: np.ndarray, window: int = 7) -> np.ndarray:
        values = np.nan_to_num(values.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
        if values.shape[0] < 3:
            return values
        window = min(window, values.shape[0] if values.shape[0] % 2 == 1 else values.shape[0] - 1)
        window = max(window, 3)
        kernel = np.ones(window, dtype=float) / window
        residual = np.zeros_like(values)
        for col in range(values.shape[1]):
            smooth = np.convolve(values[:, col], kernel, mode="same")
            residual[:, col] = values[:, col] - smooth
        scale = np.nanmedian(np.abs(residual), axis=0)
        residual = residual / (scale + 1e-12)
        return residual

    def _rotation_angle(self, vx: float, vy: float) -> Tuple[float, int]:
        ax = abs(vx)
        ay = abs(vy)
        theta = math.asin(ay / math.sqrt(ax * ax + ay * ay + 1e-18))
        if vx >= 0 and vy >= 0:
            return theta, 1
        if vx < 0 <= vy:
            return math.pi - theta, 2
        if vx < 0 and vy < 0:
            return math.pi + theta, 3
        return 2.0 * math.pi - theta, 4

    def _depth_radius(self, rho: float, time_value: float) -> float:
        rho = max(abs(float(rho)), 1e-9)
        t = abs(float(time_value))
        # Most uploaded field files store time in microseconds.
        if t > 1.0:
            t *= 1e-6
        log_c = -0.50009365 * math.log10(rho) - 0.00137449
        c = 10.0**log_c
        radius = c * math.sqrt(rho * max(t, 1e-12))
        return float(np.clip(radius, 0.5, 120.0))

    def _display_resistivity(self, rho: float) -> float:
        rho = abs(float(rho))
        if rho < 1e-3:
            return rho * 1e6
        return rho

    def _map_inversion_to_station(self, station_ids: List[int], inversion_results: List[dict]) -> Dict[int, dict]:
        mapped: Dict[int, dict] = {}
        for idx, result in enumerate(inversion_results):
            if idx < len(station_ids):
                station = int(station_ids[idx])
            else:
                station = int(result.get("station", idx + 1))

            depths = [float(v) for v in result.get("depths", []) if np.isfinite(float(v))]
            resistivities = [
                self._display_resistivity(float(v))
                for v in result.get("resistivities", [])
                if np.isfinite(float(v))
            ]
            if resistivities:
                mapped[station] = {
                    "station": station,
                    "depths": depths,
                    "resistivities": resistivities,
                }
        return mapped

    def _layer_edges(self, depths: List[float], layer_count: int) -> List[float]:
        edges = sorted({abs(float(v)) for v in depths if np.isfinite(float(v))})
        if not edges or edges[0] > 1e-6:
            edges.insert(0, 0.0)

        if len(edges) > 1:
            steps = np.diff(np.asarray(edges, dtype=float))
            step = float(np.nanmedian(steps[steps > 1e-6])) if np.any(steps > 1e-6) else 1.0
        else:
            step = max(edges[-1] if edges else 0.0, 1.0)
        step = max(step, 1.0)

        while len(edges) < layer_count + 1:
            edges.append(edges[-1] + step)

        monotonic_edges = [edges[0]]
        for value in edges[1 : layer_count + 1]:
            monotonic_edges.append(max(float(value), monotonic_edges[-1] + 0.2))
        return monotonic_edges

    def _cylindrical_layer_points(
        self,
        origin: np.ndarray,
        right: np.ndarray,
        down: np.ndarray,
        station: int,
        layer: int,
        inner_radius: float,
        outer_radius: float,
        resistivity: float,
        background_resistivity: Optional[float] = None,
        class_code: int = 0,
        point_type: str = "background",
        preferred_angle: Optional[float] = None,
        direction_strength: float = 0.0,
        region_id: Optional[str] = None,
        radial_samples: int = 4,
        md: Optional[float] = None,
    ) -> List[dict]:
        points = []
        angular_samples = 32
        inner = max(float(inner_radius), 0.0)
        outer = max(float(outer_radius), inner + 0.2)

        if radial_samples <= 1:
            radii = [outer]
        else:
            radii = np.linspace(inner, outer, radial_samples + 1, dtype=float)[1:].tolist()

        for radius in radii:
            display_radius = max(float(radius), 0.05)
            radial_ratio = (display_radius - inner) / max(outer - inner, 1e-9)
            for idx in range(angular_samples):
                angle = 2.0 * math.pi * idx / angular_samples
                direction = math.cos(angle) * right + math.sin(angle) * down
                point = origin + direction * display_radius
                value, local_class_code, anomaly_weight = self._gradient_resistivity(
                    resistivity=resistivity,
                    background_resistivity=background_resistivity,
                    class_code=class_code,
                    angle=angle,
                    preferred_angle=preferred_angle,
                    direction_strength=direction_strength,
                    radial_ratio=radial_ratio,
                )
                points.append(
                    {
                        "station": station,
                        "md": round(float(md), 3) if md is not None else round(float(station), 3),
                        "layer": layer,
                        "radius": round(display_radius, 3),
                        "angle": round(math.degrees(angle), 3),
                        "x": round(float(point[0]), 3),
                        "y": round(float(point[1]), 3),
                        "z": round(float(point[2]), 3),
                        "resistivity": round(float(value), 6),
                        "class_code": local_class_code,
                        "point_type": point_type,
                        "anomaly_weight": round(anomaly_weight, 6),
                        "region_id": region_id,
                    }
                )
        return points

    def _gradient_resistivity(
        self,
        resistivity: float,
        background_resistivity: Optional[float],
        class_code: int,
        angle: float,
        preferred_angle: Optional[float],
        direction_strength: float,
        radial_ratio: float,
    ) -> Tuple[float, int, float]:
        if not class_code or preferred_angle is None or background_resistivity is None:
            return float(resistivity), int(class_code), 1.0

        delta = math.atan2(math.sin(angle - preferred_angle), math.cos(angle - preferred_angle))
        sigma = math.radians(18.0 + 36.0 * float(np.clip(direction_strength, 0.0, 1.0)))
        angular_weight = math.exp(-0.5 * (delta / max(sigma, 1e-6)) ** 2)
        radial_weight = 0.45 + 0.55 * float(np.clip(radial_ratio, 0.0, 1.0))
        anomaly_weight = float(np.clip(angular_weight * radial_weight, 0.0, 1.0))
        value = float(background_resistivity) + (float(resistivity) - float(background_resistivity)) * anomaly_weight
        local_class_code = int(class_code) if anomaly_weight >= 0.28 else 0
        return value, local_class_code, anomaly_weight

    def _radius_limit_from_params(self, params: dict) -> float:
        def axis_radius(key: str) -> float:
            value = params.get(key) or (-30.0, 30.0)
            try:
                return max(abs(float(value[0])), abs(float(value[1])))
            except (TypeError, ValueError, IndexError):
                return 30.0

        explicit = params.get("radius_limit")
        if explicit is not None:
            try:
                radius = float(explicit)
                if np.isfinite(radius) and radius > 0:
                    return radius
            except (TypeError, ValueError):
                pass
        return float(min(axis_radius("x_range"), axis_radius("y_range")))

    def _scale_layer_edges(self, edges: List[float], radius_limit: float) -> List[float]:
        if not edges:
            return edges
        radius_limit = float(radius_limit)
        if not np.isfinite(radius_limit) or radius_limit <= 0:
            return edges
        outer = max(float(edges[-1]), 1e-9)
        scale = radius_limit / outer
        return [float(edge) * scale for edge in edges]

    def _result_rows_from_render_points(self, points: List[dict]) -> List[List[float]]:
        rows = []
        ordered = sorted(
            points,
            key=lambda p: (
                float(p.get("md", p.get("station", 0.0))),
                float(p.get("radius", 0.0)),
                float(p.get("angle", 0.0)),
            ),
        )
        for point in ordered:
            try:
                row = [
                    float(point["x"]),
                    float(point["y"]),
                    float(point["z"]),
                    float(point["resistivity"]),
                    int(point.get("class_code", 0)),
                ]
            except (KeyError, TypeError, ValueError):
                continue
            if np.isfinite(row[:4]).all():
                rows.append([round(row[0], 6), round(row[1], 6), round(row[2], 6), round(row[3], 6), row[4]])
        return rows

    def _section_rows_from_render_points(self, points: List[dict]) -> Tuple[List[List[float]], List[List[float]]]:
        x_rows: List[List[float]] = []
        y_rows: List[List[float]] = []
        for point in points:
            try:
                md = float(point.get("md", point.get("station", 0.0)))
                radius = float(point.get("radius", 0.0))
                angle = math.radians(float(point.get("angle", 0.0)))
                value = float(point["resistivity"])
            except (TypeError, ValueError, KeyError):
                continue
            x_offset = radius * math.cos(angle)
            y_offset = radius * math.sin(angle)
            if abs(y_offset) <= max(radius * 1e-6, 1e-6):
                x_rows.append([round(md, 6), round(x_offset, 6), round(value, 6)])
            if abs(x_offset) <= max(radius * 1e-6, 1e-6):
                y_rows.append([round(md, 6), round(y_offset, 6), round(value, 6)])

        x_rows.sort(key=lambda row: (row[0], row[1]))
        y_rows.sort(key=lambda row: (row[0], row[1]))
        return x_rows, y_rows

    def _result_points_metadata(
        self,
        points: List[List[float]],
        coordinate_mode: str,
        radius_limit: float,
        longitudinal_section_count: int,
        anomaly_region_count: int,
    ) -> dict:
        if not points:
            return {
                "point_count": 0,
                "coordinate_mode": coordinate_mode,
                "radius_limit": float(radius_limit),
                "longitudinal_section_count": int(longitudinal_section_count),
                "anomaly_region_count": int(anomaly_region_count),
            }
        arr = np.asarray(points, dtype=float)
        class_values, class_counts = np.unique(arr[:, 4].astype(int), return_counts=True)
        return {
            "point_count": int(arr.shape[0]),
            "coordinate_mode": coordinate_mode,
            "radius_limit": float(radius_limit),
            "longitudinal_section_count": int(longitudinal_section_count),
            "anomaly_region_count": int(anomaly_region_count),
            "x_range": [round(float(np.nanmin(arr[:, 0])), 6), round(float(np.nanmax(arr[:, 0])), 6)],
            "y_range": [round(float(np.nanmin(arr[:, 1])), 6), round(float(np.nanmax(arr[:, 1])), 6)],
            "z_range": [round(float(np.nanmin(arr[:, 2])), 6), round(float(np.nanmax(arr[:, 2])), 6)],
            "value_min": round(float(np.nanmin(arr[:, 3])), 6),
            "value_max": round(float(np.nanmax(arr[:, 3])), 6),
            "class_counts": {str(int(k)): int(v) for k, v in zip(class_values, class_counts)},
        }

    def _cylindrical_sector_points(
        self,
        origin: np.ndarray,
        right: np.ndarray,
        down: np.ndarray,
        station: int,
        layer: int,
        inner_radius: float,
        outer_radius: float,
        resistivity: float,
        class_code: int,
        center_angle: float,
        strength: float,
        radial_samples: int = 3,
        angular_samples: int = 14,
    ) -> List[dict]:
        points = []
        inner = max(float(inner_radius), 0.0)
        outer = max(float(outer_radius), inner + 0.2)
        strength = float(np.clip(strength, 0.0, 1.0))
        half_width = math.radians(18.0 + 34.0 * strength)
        radii = np.linspace(inner, outer, radial_samples + 1, dtype=float)[1:].tolist()
        angles = np.linspace(center_angle - half_width, center_angle + half_width, angular_samples, dtype=float)

        for radius in radii:
            display_radius = max(float(radius), 0.05)
            for angle in angles:
                direction = math.cos(float(angle)) * right + math.sin(float(angle)) * down
                point = origin + direction * display_radius
                points.append(
                    {
                        "station": station,
                        "layer": layer,
                        "radius": round(display_radius, 3),
                        "angle": round(math.degrees(float(angle)), 3),
                        "preferred_angle": round(math.degrees(center_angle), 3),
                        "x": round(float(point[0]), 3),
                        "y": round(float(point[1]), 3),
                        "z": round(float(point[2]), 3),
                        "resistivity": round(float(resistivity), 6),
                        "class_code": class_code,
                        "point_type": "anomaly",
                        "xy_strength": round(strength, 6),
                    }
                )
        return points

    def _xy_direction_profiles(
        self,
        comp_x: ComponentData,
        comp_y: ComponentData,
        stations: List[int],
    ) -> Dict[int, dict]:
        x_index = {station: idx for idx, station in enumerate(comp_x.stations)}
        y_index = {station: idx for idx, station in enumerate(comp_y.stations)}
        channel_count = min(comp_x.voltage.shape[1], comp_y.voltage.shape[1])
        if channel_count == 0:
            return {}

        x_values = np.nan_to_num(comp_x.voltage[:, :channel_count], nan=0.0, posinf=0.0, neginf=0.0)
        y_values = np.nan_to_num(comp_y.voltage[:, :channel_count], nan=0.0, posinf=0.0, neginf=0.0)
        x_residual = self._moving_residual(x_values)
        y_residual = self._moving_residual(y_values)

        profiles: Dict[int, dict] = {}
        all_strengths = []
        for station in stations:
            if station not in x_index or station not in y_index:
                continue
            xi = x_index[station]
            yi = y_index[station]
            angles = []
            quadrants = []
            strengths = []
            for channel in range(channel_count):
                vx = float(x_residual[xi, channel])
                vy = float(y_residual[yi, channel])
                if abs(vx) + abs(vy) < 1e-12:
                    vx = float(x_values[xi, channel])
                    vy = float(y_values[yi, channel])
                angle, quadrant = self._rotation_angle(vx, vy)
                strength = math.sqrt(vx * vx + vy * vy)
                angles.append(angle)
                quadrants.append(quadrant)
                strengths.append(strength)
                all_strengths.append(strength)
            profiles[station] = {
                "angles": np.asarray(angles, dtype=float),
                "quadrants": np.asarray(quadrants, dtype=int),
                "strengths": np.asarray(strengths, dtype=float),
            }

        if not all_strengths:
            return profiles

        values = np.asarray(all_strengths, dtype=float)
        median = float(np.nanmedian(values))
        mad = float(np.nanmedian(np.abs(values - median)))
        scale = max(median + 2.5 * 1.4826 * mad, float(np.nanmax(values)) * 0.35, 1e-12)
        for profile in profiles.values():
            profile["strengths"] = np.clip(profile["strengths"] / scale, 0.0, 1.0)
        return profiles

    def _layer_direction(self, profile: Optional[dict], layer_index: int, layer_count: int) -> dict:
        if not profile or len(profile.get("angles", [])) == 0:
            return {"angle": 0.0, "quadrant": 1, "strength": 0.35}

        angles = profile["angles"]
        quadrants = profile["quadrants"]
        strengths = profile["strengths"]
        channel_count = len(angles)
        start = int(layer_index / max(layer_count, 1) * channel_count)
        end = int((layer_index + 1) / max(layer_count, 1) * channel_count)
        end = max(start + 1, min(end, channel_count))
        start = min(start, channel_count - 1)

        local_strengths = strengths[start:end]
        local_offset = int(np.nanargmax(local_strengths)) if len(local_strengths) else 0
        idx = min(start + local_offset, channel_count - 1)
        return {
            "angle": float(angles[idx]),
            "quadrant": int(quadrants[idx]),
            "strength": float(np.clip(strengths[idx], 0.15, 1.0)),
        }

    def _interpolate_sections(
        self,
        actual_sections: List[dict],
        trajectory: List[dict],
        anomaly_regions: List[dict],
        background_resistivity: float,
        thresholds: dict,
    ) -> List[dict]:
        if not actual_sections:
            return []
        if len(actual_sections) == 1:
            section = actual_sections[0]
            origin, tangent, right, down, _ = self._frame_at_md(trajectory, section["md"])
            return [
                {
                    "station": float(section["station"]),
                    "md": section["md"],
                    "origin": origin,
                    "tangent": tangent,
                    "right": right,
                    "down": down,
                    "layers": section["layers"],
                }
            ]

        section_mds = [section["md"] for section in actual_sections]
        spacing = self._longitudinal_spacing(section_mds)
        render_sections = []
        for section_index in range(len(actual_sections) - 1):
            start = actual_sections[section_index]
            end = actual_sections[section_index + 1]
            span = max(float(end["md"] - start["md"]), 0.0)
            steps = max(1, int(math.ceil(span / spacing)))
            first_step = 0 if section_index == 0 else 1
            for step in range(first_step, steps + 1):
                ratio = step / steps
                md = start["md"] + (end["md"] - start["md"]) * ratio
                station_value = start["station"] + (end["station"] - start["station"]) * ratio
                origin, tangent, right, down, _ = self._frame_at_md(trajectory, md)
                render_sections.append(
                    {
                        "station": round(float(station_value), 3),
                        "md": md,
                        "origin": origin,
                        "tangent": tangent,
                        "right": right,
                        "down": down,
                        "layers": self._interpolate_layers(
                            start["layers"],
                            end["layers"],
                            ratio,
                            station_value,
                            anomaly_regions,
                            background_resistivity,
                            thresholds,
                        ),
                    }
                )
        return render_sections

    def _longitudinal_spacing(self, mds: List[float]) -> float:
        diffs = np.diff(np.asarray(mds, dtype=float))
        diffs = diffs[diffs > 1e-6]
        if diffs.size == 0:
            return 2.0
        median_spacing = float(np.nanmedian(diffs))
        return float(np.clip(median_spacing / 4.0, 1.2, 2.5))

    def _interpolate_layers(
        self,
        start_layers: List[dict],
        end_layers: List[dict],
        ratio: float,
        station_value: float,
        anomaly_regions: List[dict],
        background_resistivity: float,
        thresholds: dict,
    ) -> List[dict]:
        layers = []
        layer_count = min(len(start_layers), len(end_layers))
        for idx in range(layer_count):
            start = start_layers[idx]
            end = end_layers[idx]
            layer_index = int(start["layer_index"])
            resistivity = self._lerp(start["resistivity"], end["resistivity"], ratio)
            region = self._region_for_station_layer(anomaly_regions, station_value, layer_index)
            if region:
                class_code = self._class_code(region["kind"])
                render_resistivity = resistivity
                direction = {
                    "angle": region["angle"],
                    "quadrant": region["quadrant"],
                    "strength": region["strength"],
                }
                region_id = region["id"]
            else:
                class_code = 0
                render_resistivity = self._normal_region_resistivity(resistivity, background_resistivity, thresholds)
                direction = {"angle": 0.0, "quadrant": 1, "strength": 0.0}
                region_id = None
            layers.append(
                {
                    "layer_index": layer_index,
                    "layer": int(start["layer"]),
                    "inner_radius": self._lerp(start["inner_radius"], end["inner_radius"], ratio),
                    "outer_radius": self._lerp(start["outer_radius"], end["outer_radius"], ratio),
                    "resistivity": resistivity,
                    "render_resistivity": render_resistivity,
                    "class_code": class_code,
                    "direction": direction,
                    "region_id": region_id,
                }
            )
        return layers

    def _region_for_station_layer(self, regions: List[dict], station_value: float, layer_index: int) -> Optional[dict]:
        layer_number = layer_index + 1
        for region in regions:
            if (
                float(region["station_min"]) <= station_value <= float(region["station_max"])
                and int(region["layer_min"]) <= layer_number <= int(region["layer_max"])
            ):
                return region
        return None

    def _lerp(self, start: float, end: float, ratio: float) -> float:
        return float(start + (end - start) * ratio)

    def _detect_anomaly_regions(
        self,
        stations: List[int],
        inversion_by_station: Dict[int, dict],
        xy_profiles: Dict[int, dict],
        thresholds: dict,
        max_regions_per_kind: int = 2,
    ) -> List[dict]:
        cells_by_kind = {"low": [], "high": []}
        all_resistivities = [
            self._display_resistivity(float(rho))
            for station in stations
            for rho in inversion_by_station[station]["resistivities"]
        ]
        if not all_resistivities:
            return []
        min_rho = min(all_resistivities)
        max_rho = max(all_resistivities)
        low_threshold = float(thresholds.get("low", min_rho))
        high_threshold = float(thresholds.get("high", max_rho))

        for station_index, station in enumerate(stations):
            resistivities = inversion_by_station[station]["resistivities"]
            layer_count = len(resistivities)
            for layer_index, rho in enumerate(resistivities):
                resistivity = self._display_resistivity(float(rho))
                if resistivity <= low_threshold:
                    kind = "low"
                    intensity = (low_threshold - resistivity) / max(low_threshold - min_rho, 1e-9)
                elif resistivity >= high_threshold:
                    kind = "high"
                    intensity = (resistivity - high_threshold) / max(max_rho - high_threshold, 1e-9)
                else:
                    continue

                direction = self._layer_direction(xy_profiles.get(station), layer_index, layer_count)
                strength = float(direction["strength"])
                score = float(np.clip(intensity, 0.05, 1.0) * (0.35 + 0.65 * strength))
                cells_by_kind[kind].append(
                    {
                        "station": station,
                        "station_index": station_index,
                        "layer_index": layer_index,
                        "resistivity": resistivity,
                        "angle": float(direction["angle"]),
                        "quadrant": int(direction["quadrant"]),
                        "strength": strength,
                        "score": score,
                    }
                )

        regions = []
        for kind, cells in cells_by_kind.items():
            if not cells:
                continue
            components = self._localized_anomaly_components(cells, len(stations), max_regions_per_kind)
            for region_index, component in enumerate(components, start=1):
                region = self._build_region(kind, region_index, component)
                if region:
                    regions.append(region)
        return regions

    def _localized_anomaly_components(
        self,
        cells: List[dict],
        station_count: int,
        max_regions: int,
    ) -> List[List[dict]]:
        if not cells:
            return []
        max_span = max(3, min(station_count, int(math.ceil(station_count * 0.22))))
        half_span = max(1, max_span // 2)

        station_scores: Dict[int, float] = {}
        for cell in cells:
            station_index = int(cell["station_index"])
            station_scores[station_index] = max(station_scores.get(station_index, 0.0), float(cell["score"]))

        peaks = sorted(station_scores, key=lambda idx: station_scores[idx], reverse=True)
        selected_ranges: List[Tuple[int, int]] = []
        selected_components: List[List[dict]] = []

        for peak in peaks:
            start = max(0, peak - half_span)
            end = min(station_count - 1, start + max_span - 1)
            start = max(0, end - max_span + 1)
            if any(not (end < used_start or start > used_end) for used_start, used_end in selected_ranges):
                continue

            window_cells = [cell for cell in cells if start <= int(cell["station_index"]) <= end]
            if not window_cells:
                continue
            peak_score = max(float(cell["score"]) for cell in window_cells)
            focused_cells = [cell for cell in window_cells if float(cell["score"]) >= peak_score * 0.45]
            if not focused_cells:
                focused_cells = window_cells

            components = self._connected_components(focused_cells)
            if not components:
                continue
            component = max(components, key=lambda group: sum(float(cell["score"]) for cell in group))
            selected_components.append(component)
            selected_ranges.append((start, end))
            if len(selected_components) >= max_regions:
                break

        return selected_components

    def _connected_components(self, cells: List[dict]) -> List[List[dict]]:
        cell_map = {(cell["station_index"], cell["layer_index"]): cell for cell in cells}
        visited = set()
        components = []
        for key in cell_map:
            if key in visited:
                continue
            stack = [key]
            visited.add(key)
            component = []
            while stack:
                current = stack.pop()
                cell = cell_map[current]
                component.append(cell)
                station_index, layer_index = current
                for neighbor in (
                    (station_index - 1, layer_index),
                    (station_index + 1, layer_index),
                    (station_index, layer_index - 1),
                    (station_index, layer_index + 1),
                ):
                    if neighbor in cell_map and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
            components.append(component)
        return components

    def _build_region(self, kind: str, region_index: int, cells: List[dict]) -> Optional[dict]:
        if not cells:
            return None
        weights = np.asarray([max(cell["score"], 1e-6) for cell in cells], dtype=float)
        angles = np.asarray([cell["angle"] for cell in cells], dtype=float)
        sin_sum = float(np.sum(np.sin(angles) * weights))
        cos_sum = float(np.sum(np.cos(angles) * weights))
        angle = math.atan2(sin_sum, cos_sum)
        if angle < 0:
            angle += 2.0 * math.pi

        quadrants = [cell["quadrant"] for cell in cells]
        quadrant = max(set(quadrants), key=quadrants.count)
        stations = [cell["station"] for cell in cells]
        layer_indices = [cell["layer_index"] for cell in cells]
        return {
            "id": f"{kind}-{region_index}",
            "kind": kind,
            "angle": angle,
            "quadrant": int(quadrant),
            "strength": float(np.clip(np.average([cell["strength"] for cell in cells], weights=weights), 0.2, 1.0)),
            "score": float(np.sum(weights)),
            "station_min": int(min(stations)),
            "station_max": int(max(stations)),
            "layer_min": int(min(layer_indices) + 1),
            "layer_max": int(max(layer_indices) + 1),
            "cells": cells,
        }

    def _region_summaries(self, regions: List[dict]) -> List[dict]:
        return [
            {
                "id": region["id"],
                "kind": region["kind"],
                "station_min": region["station_min"],
                "station_max": region["station_max"],
                "layer_min": region["layer_min"],
                "layer_max": region["layer_max"],
                "preferred_angle": round(math.degrees(region["angle"]), 3),
                "quadrant": region["quadrant"],
                "cell_count": len(region["cells"]),
                "score": round(float(region["score"]), 6),
            }
            for region in regions
        ]

    def _color_thresholds_from_values(self, values: List[float]) -> dict:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return {"low": 0.0, "high": 0.0, "mode": "z_inversion_quantile_25_75"}
        low = float(np.nanquantile(arr, 0.25))
        high = float(np.nanquantile(arr, 0.75))
        if abs(high - low) < 1e-9:
            center = float(np.nanmedian(arr))
            low = center * 0.9
            high = center * 1.1
        return {"low": low, "high": high, "mode": "z_inversion_quantile_25_75"}

    def _background_resistivity(self, values: List[float], thresholds: dict) -> float:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return 1.0
        low = float(thresholds.get("low", np.nanmin(arr)))
        high = float(thresholds.get("high", np.nanmax(arr)))
        normal = arr[(arr > low) & (arr < high)]
        if normal.size:
            value = float(np.nanmedian(normal))
            if low < value < high:
                return value
        if np.isfinite(low) and np.isfinite(high) and high > low:
            return (low + high) * 0.5
        return float(np.nanmedian(arr))

    def _normal_region_resistivity(self, value: float, background_resistivity: float, thresholds: dict) -> float:
        low = float(thresholds.get("low", background_resistivity))
        high = float(thresholds.get("high", background_resistivity))
        if not np.isfinite(value):
            return float(background_resistivity)
        if low < value < high:
            return float(value)
        if high > low:
            clipped = float(np.clip(value, low, high))
            return float(background_resistivity + (clipped - background_resistivity) * 0.2)
        return float(background_resistivity)

    def _classify_resistivity(self, value: float, thresholds: dict) -> str:
        if value <= float(thresholds.get("low", value - 1.0)):
            return "low"
        if value >= float(thresholds.get("high", value + 1.0)):
            return "high"
        return "normal"

    def _class_code(self, resistivity_class: str) -> int:
        return {"low": 1, "high": 2}.get(resistivity_class, 0)

    def _color_thresholds(self, points: List[dict]) -> dict:
        values = np.asarray([p["resistivity"] for p in points], dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return {"low": 0.0, "high": 0.0, "mode": "quantile_25_75"}

        low = float(np.nanquantile(values, 0.25))
        high = float(np.nanquantile(values, 0.75))
        if not np.isfinite(low) or not np.isfinite(high):
            low = high = float(np.nanmedian(values))
        if abs(high - low) < 1e-9:
            center = float(np.nanmedian(values))
            low = center * 0.9
            high = center * 1.1
        return {"low": low, "high": high, "mode": "quantile_25_75"}

    def _attach_resistivity_class(self, points: List[dict], thresholds: dict) -> None:
        for point in points:
            class_code = int(point.get("class_code", 0))
            if class_code == 1:
                point["resistivity_class"] = "low"
            elif class_code == 2:
                point["resistivity_class"] = "high"
            else:
                point["resistivity_class"] = "normal"
                point["class_code"] = 0

    def _cylindrical_section_points(
        self,
        origin: np.ndarray,
        right: np.ndarray,
        down: np.ndarray,
        station: int,
        channel: int,
        time_value: float,
        radius: float,
        preferred_angle: float,
        quadrant: int,
        resistivity: float,
        radial_layers: Tuple[float, ...] = (1.0,),
    ) -> List[dict]:
        points = []
        angular_samples = 24

        for layer_ratio in radial_layers:
            for idx in range(angular_samples):
                angle = 2.0 * math.pi * idx / angular_samples
                direction = math.cos(angle) * right + math.sin(angle) * down
                point = origin + direction * radius * layer_ratio

                # Preserve the X/Y-derived abnormal direction as anisotropic
                # resistivity, but still build the complete cylindrical body.
                delta = math.atan2(math.sin(angle - preferred_angle), math.cos(angle - preferred_angle))
                direction_weight = 0.78 + 0.22 * max(0.0, math.cos(delta))
                radial_weight = 0.92 + 0.08 * layer_ratio
                value = resistivity * direction_weight * radial_weight

                points.append(
                    {
                        "station": station,
                        "channel": channel,
                        "time": time_value,
                        "radius": round(radius * layer_ratio, 3),
                        "outer_radius": round(radius, 3),
                        "angle": round(math.degrees(angle), 3),
                        "preferred_angle": round(math.degrees(preferred_angle), 3),
                        "quadrant": quadrant,
                        "x": round(float(point[0]), 3),
                        "y": round(float(point[1]), 3),
                        "z": round(float(point[2]), 3),
                        "resistivity": round(float(value), 6),
                    }
                )

        return points

    def _station_to_md(self, station: int, min_station: int, max_station: int, max_md: float) -> float:
        if max_station == min_station:
            return 0.0
        return (station - min_station) / (max_station - min_station) * max_md

    def _station_depth_map(self, stations: List[int], trajectory: List[dict]) -> Dict[int, float]:
        if not stations or not trajectory:
            return {int(station): float(station) for station in stations}
        min_station = min(stations)
        max_station = max(stations)
        max_md = float(trajectory[-1]["md"])
        return {
            int(station): self._station_to_md(int(station), min_station, max_station, max_md)
            for station in stations
        }

    def _frame_at_md(self, trajectory: List[dict], md: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
        mds = np.array([p["md"] for p in trajectory], dtype=float)
        idx = int(np.searchsorted(mds, md))
        idx = max(1, min(idx, len(trajectory) - 1))
        p0 = trajectory[idx - 1]
        p1 = trajectory[idx]
        span = max(p1["md"] - p0["md"], 1e-9)
        ratio = (md - p0["md"]) / span

        def lerp(key: str) -> float:
            return float(p0[key] + (p1[key] - p0[key]) * ratio)

        origin = np.array([lerp("x"), lerp("y"), lerp("z")], dtype=float)
        prev_pt = np.array([p0["x"], p0["y"], p0["z"]], dtype=float)
        next_pt = np.array([p1["x"], p1["y"], p1["z"]], dtype=float)
        tangent = self._normalize(next_pt - prev_pt, np.array([0.0, 0.0, 1.0]))
        right, down = self._cross_section_axes(tangent)
        return origin, tangent, right, down, {"inclination": lerp("inclination"), "azimuth": lerp("azimuth")}

    def _cross_section_axes(self, tangent: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        reference_axes = (
            np.array([1.0, 0.0, 0.0], dtype=float),
            np.array([0.0, 1.0, 0.0], dtype=float),
            np.array([0.0, 0.0, 1.0], dtype=float),
        )
        reference = min(reference_axes, key=lambda axis: abs(float(np.dot(tangent, axis))))
        right = self._normalize(np.cross(tangent, reference), np.array([1.0, 0.0, 0.0], dtype=float))
        down = self._normalize(np.cross(tangent, right), np.array([0.0, 1.0, 0.0], dtype=float))
        return right, down

    def _normalize(self, vec: np.ndarray, fallback: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vec))
        if norm < 1e-9:
            return fallback.astype(float)
        return vec / norm

    def _voxelize(self, points: List[dict], max_points: int = 45000) -> List[List[float]]:
        if len(points) <= max_points:
            selected = points
        else:
            anomalies = [p for p in points if int(p.get("class_code", 0)) != 0]
            background = [p for p in points if int(p.get("class_code", 0)) == 0]
            anomaly_count = min(len(anomalies), max_points // 2)
            background_count = max_points - anomaly_count
            selected = self._sample_points(background, background_count) + self._sample_points(anomalies, anomaly_count)
        return [[p["x"], p["y"], p["z"], p["resistivity"], int(p.get("class_code", 0))] for p in selected]

    def _sample_points(self, points: List[dict], count: int) -> List[dict]:
        if count <= 0 or not points:
            return []
        if len(points) <= count:
            return points
        order = np.linspace(0, len(points) - 1, count).astype(int)
        return [points[i] for i in order]

    def _bounds(self, trajectory: List[dict], points: List[dict]) -> dict:
        xs = [p["x"] for p in trajectory] + [p["x"] for p in points]
        ys = [p["y"] for p in trajectory] + [p["y"] for p in points]
        zs = [p["z"] for p in trajectory] + [p["z"] for p in points]
        return {
            "minX": float(min(xs)),
            "maxX": float(max(xs)),
            "minY": float(min(ys)),
            "maxY": float(max(ys)),
            "minZ": float(min(zs)),
            "maxZ": float(max(zs)),
        }


borehole_image_engine = BoreholeImagingEngine()
