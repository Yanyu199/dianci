from fastapi import FastAPI, UploadFile, File, Form
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
    # 1. 将上传的字节流解码为字符串
    content_str = file_content.decode('utf-8', errors='ignore')

    # 2. 读取参数中的测道数目 (channels)
    target_channels = int(params.get('channels', 40))

    # 3. 使用 numpy 解析文本表格数据
    # skip_header=1 跳过第一行表头 (time[s] 1.00 2.00 ...)
    data_matrix = np.genfromtxt(io.StringIO(content_str), skip_header=1)

    if data_matrix.size == 0:
        return [], []

    # 4. 根据设置的测道数目截取行数，防止文件中数据行数与工程设置不一致
    if len(data_matrix) > target_channels:
        data_matrix = data_matrix[:target_channels]

    # 5. 提取采样时间列 (第 0 列)，并将秒(s)转换为毫秒(ms)
    time_channels = data_matrix[:, 0] * 1000.0

    # 6. 提取 9 个测点的数据列 (第 1 到 第 9 列)
    # 转换成转置矩阵 (.T)，结构变为：9行 x N列 (每行代表一个测点的一条衰减曲线)
    raw_series = data_matrix[:, 1:10].T

    # 7. 异常值与对数坐标兼容处理 (取绝对值，避免 log(0) 或负数导致前端图表崩溃)
    abs_series = np.abs(raw_series) + 1e-16

    return time_channels.tolist(), abs_series.tolist()


@app.post("/api/upload_xy")
async def upload_xy_data(
        fileX: UploadFile = File(...),
        fileY: UploadFile = File(...),
        paramsX: str = Form(...),
        paramsY: str = Form(...)
):
    try:
        # 1. 分别反序列化 X 和 Y 的专属工程参数
        param_dict_x = json.loads(paramsX)
        param_dict_y = json.loads(paramsY)

        # 2. 读取二进制文件内容
        content_x = await fileX.read()
        content_y = await fileY.read()

        # 3. 使用各自的参数独立解析 X 分量和 Y 分量
        time_arr_x, x_series = parse_tem_file(content_x, param_dict_x)
        time_arr_y, y_series = parse_tem_file(content_y, param_dict_y)

        # 4. 统一时间轴（优先使用 X 分量的时间序列）
        time_arr = time_arr_x if len(time_arr_x) > 0 else time_arr_y

        # 5. 构筑右侧表格所需的结构化明细数据 (JSON)
        # 格式：[{ time: 0.013, x_p1: 2.29e-7, y_p1: 1.25e-6, ... }]
        table_data = []
        for t_idx in range(len(time_arr)):
            row = {"time": round(time_arr[t_idx], 5)}
            for p_idx in range(9):
                row[f"x_p{p_idx + 1}"] = x_series[p_idx][t_idx] if t_idx < len(x_series[p_idx]) else 0
                row[f"y_p{p_idx + 1}"] = y_series[p_idx][t_idx] if t_idx < len(y_series[p_idx]) else 0
            table_data.append(row)

        # 6. 返回综合数据包
        return {
            "time": time_arr,
            "x_series": x_series,
            "y_series": y_series,
            "table_data": table_data
        }

    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"数据计算及解析失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)