from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import numpy as np
import io

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

        # 解析数据
        time_arr_x, x_series = parse_tem_file(content_x, param_dict_x)
        time_arr_y, y_series = parse_tem_file(content_y, param_dict_y)

        # 统一时间轴
        time_arr = time_arr_x if len(time_arr_x) > 0 else time_arr_y

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)