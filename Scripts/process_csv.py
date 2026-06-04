import os
import io
import csv
import re
import json
import argparse
import sys


def resolve_custom_json_path(custom_json_arg):
    """
    解析自定义 JSON 文件路径：
    - 绝对路径 → 直接返回
    - 相对路径 → 相对于当前 .py 脚本所在目录解析
    """
    if os.path.isabs(custom_json_arg):
        return custom_json_arg
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, custom_json_arg)


def load_custom_content(json_path):
    """加载自定义内容 JSON 文件"""
    resolved_path = resolve_custom_json_path(json_path)

    if not os.path.isfile(resolved_path):
        print(f"提示: 未找到自定义内容文件 '{resolved_path}'，跳过自定义替换。")
        return {}

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = {}
        for path_key, cols in data.items():
            norm_key = path_key.replace("\\", "/").lower()
            normalized[norm_key] = cols
        print(f"已加载自定义内容文件: {resolved_path}")
        print(f"  共 {len(normalized)} 个文件规则。")
        return normalized
    except Exception as e:
        print(f"警告: 读取自定义内容文件 '{resolved_path}' 失败: {e}")
        return {}


def process_csv_files(input_dir, output_dir, custom_content):
    chinese_re = re.compile(r"[\u4e00-\u9fff]")

    csv_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(os.path.join(root, file))

    total_files = len(csv_files)
    if total_files == 0:
        print("未在输入目录中找到任何 CSV 文件。")
        return

    processed_count = 0
    filtered_count = 0
    custom_applied_count = 0
    errored_files = []

    for index, file_path in enumerate(csv_files):
        percent = ((index + 1) / total_files) * 100
        status = "Processing..." if index < total_files - 1 else "Done." + " " * 10
        sys.stdout.write(
            f"\r进度: [{index + 1}/{total_files}] {percent:.1f}% - {status}"
        )
        sys.stdout.flush()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not chinese_re.search(content):
                filtered_count += 1
                continue

            reader = csv.reader(io.StringIO(content))
            rows = list(reader)

            if len(rows) < 4:
                filtered_count += 1
                continue

            # --- 1. 解析表头与列过滤 (纯粹的结构处理) ---
            header_row = rows[0]
            types_row = rows[3]

            keep_indices = [0]
            # 建立映射: RawExd逻辑物理列号(int) -> 输出列表中的位置(int)
            logical_col_to_out_pos = {}

            for csv_col_idx in range(1, len(types_row)):
                if types_row[csv_col_idx] == "str":
                    try:
                        logical_col_num = int(header_row[csv_col_idx])
                    except (ValueError, IndexError):
                        logical_col_num = csv_col_idx

                    logical_col_to_out_pos[logical_col_num] = len(keep_indices)
                    keep_indices.append(csv_col_idx)

            # --- 2. 预计算当前文件的自定义替换坐标 ---
            rel_path = os.path.relpath(file_path, input_dir)
            norm_rel = rel_path.replace("\\", "/").lower()
            file_custom = custom_content.get(norm_rel, {})

            # 格式: {(row_id, out_col_pos): replacement_value}
            replacements = {}
            if file_custom:
                for col_str, row_map in file_custom.items():
                    try:
                        logical_col = int(col_str)
                        out_pos = logical_col_to_out_pos.get(logical_col)
                        if out_pos is None:
                            print(
                                f"\n警告: {rel_path} 中自定义内容的列 {logical_col} 未被保留或不存在，已跳过。"
                            )
                            continue
                        for row_id, value in row_map.items():
                            replacements[(str(row_id), out_pos)] = (
                                str(value).replace("\r", "").replace("\n", "")
                            )
                    except ValueError:
                        print(
                            f"\n警告: {rel_path} 中自定义内容的列索引 '{col_str}' 不是有效整数，已跳过。"
                        )

            # --- 3. 构建并写入输出文件 ---
            out_path = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            output_rows = []
            file_had_custom = False

            for row_idx, row in enumerate(rows):
                new_row = []
                row_id = row[0].strip() if row else None

                for out_pos, orig_csv_idx in enumerate(keep_indices):
                    val = row[orig_csv_idx] if orig_csv_idx < len(row) else ""

                    if row_idx == 3:
                        if val == "int32":
                            val = "Int32"
                        elif val == "str":
                            val = "String"

                    val = str(val).replace("\r", "").replace("\n", "")

                    if row_idx >= 4 and row_id:
                        replacement = replacements.get((row_id, out_pos))
                        if replacement is not None:
                            val = replacement
                            file_had_custom = True

                    new_row.append(val)
                output_rows.append(new_row)

            # 最终一次性写入磁盘
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, lineterminator="\r\n")
                writer.writerows(output_rows)

            if file_had_custom:
                custom_applied_count += 1
            processed_count += 1

        except Exception as e:
            print(f"\n处理文件 {file_path} 时出现错误: {e}")
            errored_files.append({"path": file_path, "error": str(e)})

    print("\n\n" + "=" * 40)
    print("CSV 文件处理完成！")
    print(f"找到的总文件数：{total_files}")
    print(f"成功处理的文件：{processed_count}")
    print(f"被过滤的文件数：{filtered_count}")
    print(f"应用了自定义替换的文件数：{custom_applied_count}")
    print(f"处理出错的文件数：{len(errored_files)}")
    if errored_files:
        print("出错的文件列表：")
        for ef in errored_files:
            print(f" - {ef['path']}，错误信息：{ef['error']}")
    print("=" * 40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaintCoinach-GP RawExd CSV Processor")
    parser.add_argument("csv_dir", help="需要处理的 CSV 文件所在的目录")
    parser.add_argument(
        "--output_dir", default="", help="输出目录 (留空则默认为 ./rawexd_output 目录)"
    )
    parser.add_argument(
        "--custom_json",
        default="custom_content.json",
        help="自定义内容 JSON 文件路径 (默认: 脚本同目录下的 custom_content.json；支持绝对路径)",
    )

    args = parser.parse_args()

    input_dir = args.csv_dir
    output_dir = args.output_dir
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "rawexd_output")

    if not os.path.isdir(input_dir):
        print(f"错误: 找不到目录 '{input_dir}'。")
        sys.exit(1)

    custom_content = load_custom_content(args.custom_json)
    process_csv_files(input_dir, output_dir, custom_content)
