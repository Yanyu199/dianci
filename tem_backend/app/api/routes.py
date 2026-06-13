from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import json
from services.tem_parser import parse_tem_file  # 引入拆分出去的解析算法
from app.services.inversion_engine import tem_engine
router = APIRouter()

@router.post("/upload_xy")
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

        # 解析数据并传入对应的物理参数
        time_arr_x, x_series = parse_tem_file(content_x, param_dict_x)
        time_arr_y, y_series = parse_tem_file(content_y, param_dict_y)

        # 统一时间轴
        time_arr = time_arr_x if len(time_arr_x) > 0 else time_arr_y

        # 完全保留你的组装逻辑和防御性判断
        table_data = []
        for t_idx in range(len(time_arr)):
            row = {"time": round(time_arr[t_idx], 5)}
            for p_idx in range(9):
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
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据计算及解析失败: {str(e)}")

    @router.post("/tem/invert")
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