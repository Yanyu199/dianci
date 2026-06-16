import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from .inversion_engine import tem_engine

class ImagingEngine3D:
    def _get_inversion_results(self, text_content):
        """自动识别原始 txt 数据或已反演的 csv 数据"""
        if "测点号" in text_content or "Station" in text_content or "," in text_content:
            # 如果是 CSV 反演结果，直接解析
            lines = text_content.strip().split('\n')
            stations = {}
            for line in lines[1:]:
                parts = line.strip().split(',') if ',' in line else line.strip().split('\t')
                if len(parts) >= 4:
                    st = int(float(parts[0]))
                    dep = float(parts[2])
                    res = float(parts[3])
                    if st not in stations:
                        stations[st] = {"station": st, "depths": [], "resistivities": []}
                    stations[st]["depths"].append(dep)
                    stations[st]["resistivities"].append(res)
            return list(stations.values())
        else:
            # 如果是第一步的原始 txt 数据，自动调用 AI 引擎进行极速反演
            matrix = tem_engine.parse_txt(text_content)
            return tem_engine.batch_invert(matrix)

    def generate_full_space_voxel(self, text_x, text_y, text_z, point_spacing=10.0):
        """
        融合 X, Y, Z 三分量，生成钻孔全空间三维矩形矩阵 (Voxel)
        """
        # 1. 获取三分量的反演结果
        res_x = self._get_inversion_results(text_x)
        res_y = self._get_inversion_results(text_y)
        res_z = self._get_inversion_results(text_z)

        points = []
        values = []

        # 2. Z分量映射 (孔轴超前探测)
        for item in res_z:
            s = (item["station"] - 1) * point_spacing
            for d, r in zip(item["depths"], item["resistivities"]):
                points.append([0, 0, s + d])
                values.append(r)

        # 3. X分量映射 (横向径向剖面，左右扩展)
        for item in res_x:
            s = (item["station"] - 1) * point_spacing
            for d, r in zip(item["depths"], item["resistivities"]):
                points.append([d, 0, s])
                values.append(r)
                points.append([-d, 0, s])
                values.append(r)

        # 4. Y分量映射 (纵向径向剖面，上下扩展)
        for item in res_y:
            s = (item["station"] - 1) * point_spacing
            for d, r in zip(item["depths"], item["resistivities"]):
                points.append([0, d, s])
                values.append(r)
                points.append([0, -d, s])
                values.append(r)

        # === 🌟 核心修复：数据强制转换与自动清洗 ===
        # 将数据强制转换为 float 类型，遇到无法转换的系统会自动变成 NaN
        points = np.array(points, dtype=float)
        values = np.array(values, dtype=float)

        if len(points) == 0:
            return []

        # 寻找所有健康的、没有 NaN 的数据索引
        valid_mask = ~np.isnan(points).any(axis=1) & ~np.isnan(values) & ~np.isinf(values)

        # 只保留健康的数据参与后续的三维计算
        points = points[valid_mask]
        values = values[valid_mask]

        # 再次检查清洗后是否还有数据
        if len(points) == 0:
            raise ValueError("数据清洗后没有有效坐标点，请检查源数据文件是否全部为无效格式！")
        # ============================================

        # 5. 确定 3D 空间的包围盒范围
        max_radial = np.max(np.abs(points[:, 0:2]))
        max_axial = np.max(points[:, 2])

        grid_x, grid_y, grid_z = np.mgrid[
                                 -max_radial:max_radial:30j,
                                 -max_radial:max_radial:30j,
                                 0:max_axial:60j
                                 ]

        # 6. 三维空间插值与高斯滤波
        grid_res = griddata(points, values, (grid_x, grid_y, grid_z), method='linear', fill_value=np.mean(values))
        grid_res = gaussian_filter(grid_res, sigma=1.0)

        # 7. 组装前端 WebGL 数据
        out_data = []
        for i in range(grid_x.shape[0]):
            for j in range(grid_x.shape[1]):
                for k in range(grid_x.shape[2]):
                    x_val = float(grid_x[i, j, k])
                    y_val = float(grid_y[i, j, k])
                    z_val = float(grid_z[i, j, k])
                    v_val = float(grid_res[i, j, k])

                    # 避免在插值边缘产生新的 NaN
                    if not np.isnan(v_val):
                        out_data.append([round(x_val, 1), round(y_val, 1), round(z_val, 1), round(v_val, 2)])

        return out_data

image_engine_3d = ImagingEngine3D()