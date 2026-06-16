import os
# 直接引入我们已经写好的强大反演引擎
from app.services.inversion_engine import tem_engine


def batch_process_local_folders(start_id=1, end_id=10):
    """
    遍历本地文件夹进行批量反演
    """
    # 你的基础路径设置 (使用 r 前缀防止 Windows 路径转义报错)
    input_base_dir = r"I:\shunbian\训练文件夹\原始数据"
    output_base_dir = r"I:\shunbian\训练文件夹\反演数据"

    success_count = 0

    print("🚀 开始执行本地全自动批量反演流水线...")
    print("=" * 50)

    for i in range(start_id, end_id + 1):
        model_name = f"model_{i}"
        input_file = os.path.join(input_base_dir, model_name, "abnormal", "dBzdt.txt")
        output_folder = os.path.join(output_base_dir, model_name)

        # 1. 检查输入文件是否存在
        if not os.path.exists(input_file):
            print(f"⚠️ [跳过] 找不到文件: {input_file}")
            continue

        # 2. 确保输出文件夹存在，如果没有则自动创建
        os.makedirs(output_folder, exist_ok=True)
        output_file_csv = os.path.join(output_folder, "inversion_result.csv")
        output_file_dat = os.path.join(output_folder, "inversion_result.dat")

        print(f"⏳ 正在处理 {model_name} ...")

        try:
            # 3. 读取野外数据文本
            with open(input_file, 'r', encoding='utf-8') as f:
                text_content = f.read()

            # 4. 核心计算：极速反演
            data_matrix = tem_engine.parse_txt(text_content)
            results = tem_engine.batch_invert(data_matrix)

            # 5. 保存为 CSV (Excel查看) 和 DAT (专业绘图)
            # --- 写入 CSV ---
            with open(output_file_csv, 'w', encoding='utf-8') as f:
                f.write('\ufeff测点号,层号,顶面深度(m),地层电阻率(Ω·m)\n')  # \ufeff 是BOM头防乱码
                for item in results:
                    for j in range(len(item["resistivities"])):
                        f.write(f'{item["station"]},{j + 1},{item["depths"][j]:.2f},{item["resistivities"][j]:.2f}\n')

            # --- 写入 DAT (Tab 分隔) ---
            with open(output_file_dat, 'w', encoding='utf-8') as f:
                f.write('Station\tLayer\tDepth(m)\tResistivity(Ohm.m)\n')
                for item in results:
                    for j in range(len(item["resistivities"])):
                        f.write(
                            f'{item["station"]}\t{j + 1}\t{item["depths"][j]:.2f}\t{item["resistivities"][j]:.2f}\n')

            print(f"✅ {model_name} 处理成功！包含 {len(results)} 个测点。")
            success_count += 1

        except Exception as e:
            print(f"❌ {model_name} 处理失败: {str(e)}")

    print("=" * 50)
    print(f"🎉 批量反演任务结束！共成功处理 {success_count} 个模型。")
    print(f"📁 结果已全部保存在: {output_base_dir}")


if __name__ == "__main__":
    # 在这里设置你要跑的模型编号范围
    # 目前设置为 1 到 10。当你准备好跑全部 1500 个时，改成 (1, 1500) 即可！
    batch_process_local_folders(start_id=1, end_id=10)