import numpy as np
import io
import math


def parse_tem_file(file_content: bytes, params: dict):
    """
    解析单分量 TEM 文本数据格式，并应用该分量的特有工程参数
    """
    # 1. 编码兼容处理
    try:
        content_str = file_content.decode('utf-8')
    except UnicodeDecodeError:
        content_str = file_content.decode('gbk', errors='ignore')

    # 2. 读取参数 (❗此处为你原来缺失的参数提取和物理换算逻辑)
    target_channels = int(params.get('channels', 40))
    data_type = params.get('dataType', 'borehole')  # 获取前端单选按钮的值
    tx_edge = float(params.get('txEdge', 2.0))  # 发射边长 或 发射直径
    rx_area = float(params.get('rxArea', 450.0))  # 接收面积
    turns = int(params.get('turns', 10))  # 线圈匝数

    # 根据数据类型(矿井/钻孔)计算发射面积(S)和等效发射磁矩(M = N*S)
    if data_type == 'mine':
        # 矿井瞬变：通常为方形线框，发射面积 = 边长 * 边长
        tx_area = tx_edge ** 2
    else:
        # 钻孔瞬变：通常为圆形探管，发射面积 = pi * (直径/2)^2
        tx_area = math.pi * (tx_edge / 2.0) ** 2

    # 计算等效磁矩 (实际如需包含电流I，前端也需传I的值，目前用 面积*匝数 示例)
    tx_moment = tx_area * turns

    # 3. 使用 numpy 解析文本表格数据 (完全保留你的逻辑)
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

    # ❗将计算出的物理参数应用到数据序列上(归一化换算)
    # 示例：将感应电压除以 发射磁矩 * 接收面积
    abs_series = abs_series / (tx_moment * rx_area)

    # 8. 🚨核心防御：清洗 NaN 和 Infinity (完全保留你的处理)
    abs_series = np.nan_to_num(abs_series, nan=0.0, posinf=0.0, neginf=0.0)
    time_channels = np.nan_to_num(time_channels, nan=0.0, posinf=0.0, neginf=0.0)

    return time_channels.tolist(), abs_series.tolist()