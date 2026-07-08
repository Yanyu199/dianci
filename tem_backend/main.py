from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import numpy as np
import io
import os
import uuid
from pydantic import BaseModel
from app.services.inversion_engine import tem_engine
from app.services.imaging_engine import image_engine_3d
from app.services.borehole_imaging_engine import borehole_image_engine
from app.services.result_dat_generator import (
    export_3d_result_dat,
    export_section_dat,
    generate_result_points,
    generate_sections,
)
from app.services.tem_data_parser import parse_tem_bytes, validate_three_components
app = FastAPI()

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_tem_file(file_content: bytes, params: dict):
    """
    解析单分量 TEM 文本数据格式，并应用该分量的特有工程参数
    """
    # 1. 编码兼容处理
    try:
        content_str = file_content.decode('utf-8')
    except UnicodeDecodeError:
        content_str = file_content.decode('gbk', errors='ignore')

    # 2. 读取参数中的测道数目 (channels)
    target_channels = int(params.get('channels', 40))

    # 3. 使用 numpy 解析文本表格数据
    try:
        data_matrix = np.genfromtxt(io.StringIO(content_str), skip_header=1)
        if data_matrix.size == 0:
            return [], []
        # 防御：如果文件只有一行数据，强制转换为 2D 矩阵防止后续切片报错
        data_matrix = np.atleast_2d(data_matrix)
    except Exception as e:
        raise ValueError(f"文件内容无法解析，请确保文件内是标准的数据矩阵: {str(e)}")

    # 4. 根据设置的测道数目截取行数
    if len(data_matrix) > target_channels:
        data_matrix = data_matrix[:target_channels]

    # 5. 提取采样时间列 (第 0 列)，并将秒(s)转换为毫秒(ms)
    time_channels = data_matrix[:, 0] * 1000.0

    # 6. 提取测点数据（防御性截取：即使文件列数不足10列，也切取现有的全部有效列）
    cols_to_take = min(data_matrix.shape[1], 10)
    raw_series = data_matrix[:, 1:cols_to_take].T

    # 7. 取绝对值平移防溢出
    abs_series = np.abs(raw_series) + 1e-16

    # 8. 🚨核心防御：清洗 NaN 和 Infinity (无穷大)
    # FastAPI 在序列化返回 JSON 时遇到 NaN 会底层崩溃触发 500 错误，这里统一替换为 0.0
    abs_series = np.nan_to_num(abs_series, nan=0.0, posinf=0.0, neginf=0.0)
    time_channels = np.nan_to_num(time_channels, nan=0.0, posinf=0.0, neginf=0.0)

    return time_channels.tolist(), abs_series.tolist()


@app.post("/api/upload_xy")
async def upload_xy_data(
        fileX: UploadFile = File(...),
        fileY: UploadFile = File(...),
        paramsX: str = Form(...),
        paramsY: str = Form(...)
):
    try:
        # 文件后缀名拦截
        allowed_extensions = ('.txt', '.dat', '.csv')
        if not fileX.filename.lower().endswith(allowed_extensions):
            raise ValueError(f"X分量文件格式不支持: {fileX.filename}，仅支持 .txt, .dat, .csv")
        if not fileY.filename.lower().endswith(allowed_extensions):
            raise ValueError(f"Y分量文件格式不支持: {fileY.filename}，仅支持 .txt, .dat, .csv")

        # 反序列化工程参数
        param_dict_x = json.loads(paramsX)
        param_dict_y = json.loads(paramsY)

        content_x = await fileX.read()
        content_y = await fileY.read()

        time_arr_x, x_series = parse_tem_file(content_x, param_dict_x)
        time_arr_y, y_series = parse_tem_file(content_y, param_dict_y)

        # ========= 修改这里 =========
        # 统一时间轴：谁长用谁的，防止短的数据截断长的数据
        if len(time_arr_x) >= len(time_arr_y):
            time_arr = time_arr_x
        else:
            time_arr = time_arr_y
        # ==========================

        table_data = []
        for t_idx in range(len(time_arr)):
            row = {"time": round(time_arr[t_idx], 5)}
            for p_idx in range(9):
                # 🚨核心防御：防止数组索引越界。如果文件缺失列，这里不会抛出 IndexError，而是安全地补 0
                x_val = x_series[p_idx][t_idx] if p_idx < len(x_series) and t_idx < len(x_series[p_idx]) else 0.0
                y_val = y_series[p_idx][t_idx] if p_idx < len(y_series) and t_idx < len(y_series[p_idx]) else 0.0

                row[f"x_p{p_idx + 1}"] = x_val
                row[f"y_p{p_idx + 1}"] = y_val
            table_data.append(row)

        return {
            "time": time_arr,
            "x_series": x_series,
            "y_series": y_series,
            "table_data": table_data
        }

    except ValueError as ve:
        # 捕捉已知的异常，向前端优雅返回 400
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # 其他严重的未知异常
        raise HTTPException(status_code=500, detail=f"数据计算及解析失败: {str(e)}")


@app.post("/api/tem/invert")
async def invert_tem_data(file: UploadFile = File(...)):
    try:
        # 1. 读取用户上传的文本
        content = await file.read()
        text = content.decode("utf-8")

        # 2. 解析文本获取矩阵
        data_matrix = tem_engine.parse_txt(text)

        # 3. 极速批量反演
        results = tem_engine.batch_invert(data_matrix)

        return {
            "status": "success",
            "message": f"成功反演 {len(results)} 个测点数据",
            "data": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 定义前端传过来的路径参数模型
class BatchLocalRequest(BaseModel):
    input_dir: str
    output_dir: str


@app.post("/api/tem/batch_local")
async def batch_local_inversion(req: BatchLocalRequest):
    """直接读取本地硬盘目录，进行全自动批量反演"""
    input_base_dir = req.input_dir.strip()
    output_base_dir = req.output_dir.strip()

    if not os.path.exists(input_base_dir):
        return {"status": "error", "message": f"后端找不到输入文件夹: {input_base_dir}"}

    success_count = 0
    try:
        # 遍历原始数据文件夹下的所有子文件夹 (比如 model_1, model_2)
        for item in os.listdir(input_base_dir):
            model_folder = os.path.join(input_base_dir, item)

            if os.path.isdir(model_folder):
                # 拼接寻找到你指定的 abnormal/dBzdt.txt
                input_file = os.path.join(model_folder, "abnormal", "dBzdt.txt")

                if os.path.exists(input_file):
                    # 准备输出文件夹 (比如 model_1)
                    output_folder = os.path.join(output_base_dir, item)
                    os.makedirs(output_folder, exist_ok=True)

                    output_file_csv = os.path.join(output_folder, "inversion_result.csv")
                    output_file_dat = os.path.join(output_folder, "inversion_result.dat")

                    # 1. 读取文本
                    with open(input_file, 'r', encoding='utf-8') as f:
                        text_content = f.read()

                    # 2. 核心计算
                    data_matrix = tem_engine.parse_txt(text_content)
                    results = tem_engine.batch_invert(data_matrix)

                    # 3. 写入 CSV 和 DAT 到目标硬盘
                    with open(output_file_csv, 'w', encoding='utf-8') as f:
                        f.write('\ufeff测点号,层号,顶面深度(m),地层电阻率(Ω·m)\n')
                        for res in results:
                            for j in range(len(res["resistivities"])):
                                f.write(
                                    f'{res["station"]},{j + 1},{res["depths"][j]:.2f},{res["resistivities"][j]:.2f}\n')

                    with open(output_file_dat, 'w', encoding='utf-8') as f:
                        f.write('Station\tLayer\tDepth(m)\tResistivity(Ohm.m)\n')
                        for res in results:
                            for j in range(len(res["resistivities"])):
                                f.write(
                                    f'{res["station"]}\t{j + 1}\t{res["depths"][j]:.2f}\t{res["resistivities"][j]:.2f}\n')

                    success_count += 1

        return {
            "status": "success",
            "message": f"批量反演成功！共处理了 {success_count} 个模型文件夹。",
            "count": success_count
        }
    except Exception as e:
        return {"status": "error", "message": f"处理过程中发生异常: {str(e)}"}


# ==========================================
# === 新增：3D 智能立体成像接口 ===
# ==========================================
@app.post("/api/tem/generate_3d")
async def generate_3d_model(
        file_x: UploadFile = File(...),
        file_y: UploadFile = File(...),
        file_z: UploadFile = File(...)
):
    try:
        text_x = (await file_x.read()).decode("utf-8-sig")
        text_y = (await file_y.read()).decode("utf-8-sig")
        text_z = (await file_z.read()).decode("utf-8-sig")

        # 将三分量数据送入 3D 融合引擎
        voxel_data = image_engine_3d.generate_full_space_voxel(text_x, text_y, text_z, point_spacing=10.0)

        return {
            "status": "success",
            "message": "全空间三分量 3D 矩阵融合完毕",
            "data": voxel_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/tem/borehole_image")
async def generate_borehole_image(
        file_x: UploadFile = File(...),
        file_y: UploadFile = File(...),
        file_z: UploadFile = File(...),
        trajectory_file: UploadFile = File(...)
):
    try:
        scene = borehole_image_engine.generate_scene(
            await file_x.read(),
            await file_y.read(),
            await file_z.read(),
            await trajectory_file.read(),
        )
        return {
            "status": "success",
            "message": "Borehole trajectory TEM 3D imaging completed.",
            "data": scene
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _parse_range(value: str, default):
    if value is None or str(value).strip() == "":
        return default
    try:
        parts = [float(part.strip()) for part in str(value).replace("[", "").replace("]", "").split(",")]
        if len(parts) != 2 or parts[0] >= parts[1]:
            raise ValueError
        return (parts[0], parts[1])
    except Exception as exc:
        raise ValueError(f"范围参数格式错误：{value}，应为 min,max") from exc


@app.post("/api/tem/generate_result_dat")
async def generate_result_dat(
        file_x: UploadFile = File(...),
        file_y: UploadFile = File(...),
        file_z: UploadFile = File(...),
        trajectory_file: UploadFile = File(None),
        x_range: str = Form("-30,30"),
        y_range: str = Form("-30,30"),
        grid_size: float = Form(3.0)
):
    try:
        x_payload = await file_x.read()
        y_payload = await file_y.read()
        z_payload = await file_z.read()
        trajectory_payload = await trajectory_file.read() if trajectory_file is not None else None

        if trajectory_payload:
            params = {
                "x_range": _parse_range(x_range, (-30.0, 30.0)),
                "y_range": _parse_range(y_range, (-30.0, 30.0)),
                "grid_size": float(grid_size),
            }
            scene = borehole_image_engine.generate_scene(x_payload, y_payload, z_payload, trajectory_payload, params)
            points = scene.get("points", [])
            x_section = scene.get("x_section", [])
            y_section = scene.get("y_section", [])
            scene_meta = scene.get("meta", {})

            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "tem_results", uuid.uuid4().hex)
            result_3d_path = os.path.join(output_dir, "\u4e09\u7ef4\u6210\u679c\u6570\u636e.dat")
            x_section_path = os.path.join(output_dir, "X\u5256\u9762.dat")
            y_section_path = os.path.join(output_dir, "Y\u5256\u9762.dat")
            export_3d_result_dat(points, result_3d_path)
            export_section_dat(x_section, x_section_path)
            export_section_dat(y_section, y_section_path)

            return {
                "status": "success",
                "message": "\u4e09\u7ef4\u6210\u679c DAT \u751f\u6210\u5b8c\u6210\u3002",
                "data": {
                    "points": points,
                    "x_section": x_section,
                    "y_section": y_section,
                    "trajectory": scene.get("trajectory", []),
                    "stations": scene.get("stations", []),
                    "files": {
                        "result_3d": result_3d_path,
                        "x_section": x_section_path,
                        "y_section": y_section_path,
                    },
                    "metadata": {
                        "qc": scene_meta.get("qc", {}),
                        "result": scene_meta.get("result_points", {}),
                        "inversion_count": scene_meta.get("station_count", 0),
                        "coordinate_mode": "trajectory_xyz",
                        "color_thresholds": scene_meta.get("color_thresholds"),
                        "class_codes": scene_meta.get("class_codes"),
                        "anomaly_regions": scene_meta.get("anomaly_regions", []),
                    },
                },
            }

        x_component = parse_tem_bytes(x_payload, component_name="X")
        y_component = parse_tem_bytes(y_payload, component_name="Y")
        z_component = parse_tem_bytes(z_payload, component_name="Z")
        qc_report = validate_three_components(x_component, y_component, z_component)

        inversion_results = tem_engine.invert_component(z_component)
        if not inversion_results:
            raise ValueError("Z 文件反演没有返回结果。")

        depth_map = None
        if trajectory_file is not None:
            trajectory = borehole_image_engine.parse_trajectory_excel(await trajectory_file.read())
            min_station = min(z_component.stations)
            max_station = max(z_component.stations)
            max_md = float(trajectory[-1]["md"])
            depth_map = {
                int(station): borehole_image_engine._station_to_md(int(station), min_station, max_station, max_md)
                for station in z_component.stations
            }

        params = {
            "x_range": _parse_range(x_range, (-30.0, 30.0)),
            "y_range": _parse_range(y_range, (-30.0, 30.0)),
            "grid_size": float(grid_size),
            "depth_map": depth_map,
        }
        points, point_metadata = generate_result_points(
            x_component,
            y_component,
            z_component,
            inversion_results,
            params,
        )
        x_section, y_section = generate_sections(points, grid_size=float(grid_size))

        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs", "tem_results", uuid.uuid4().hex)
        result_3d_path = os.path.join(output_dir, "三维成果数据.dat")
        x_section_path = os.path.join(output_dir, "X剖面.dat")
        y_section_path = os.path.join(output_dir, "Y剖面.dat")
        export_3d_result_dat(points, result_3d_path)
        export_section_dat(x_section, x_section_path)
        export_section_dat(y_section, y_section_path)

        return {
            "status": "success",
            "message": "三维成果 DAT 生成完成。",
            "data": {
                "points": points,
                "x_section": x_section,
                "y_section": y_section,
                "files": {
                    "result_3d": result_3d_path,
                    "x_section": x_section_path,
                    "y_section": y_section_path,
                },
                "metadata": {
                    "qc": qc_report,
                    "result": point_metadata,
                    "inversion_count": len(inversion_results),
                },
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # 注意这里把 app 换成了字符串 "main:app"，并加了 reload=True
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
