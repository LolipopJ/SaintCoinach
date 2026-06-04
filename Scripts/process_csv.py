import os
import csv
import re
import argparse
import sys

def process_csv_files(input_dir, output_dir):
    chinese_re = re.compile(r'[\u4e00-\u9fff]')
    
    # 获取所有的 csv 文件，包含子文件夹
    csv_files = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))
                
    total_files = len(csv_files)
    if total_files == 0:
        print("未在输入目录中找到任何 CSV 文件。")
        return
        
    processed_count = 0
    filtered_count = 0
    errored_files = []
    
    for index, file_path in enumerate(csv_files):
        # 显示运行进度
        percent = ((index + 1) / total_files) * 100
        status = "Processing..." if index < total_files - 1 else "Done." + " " * 10
        sys.stdout.write(f"\r进度: [{index + 1}/{total_files}] {percent:.1f}% - {status}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if not chinese_re.search(content):
                filtered_count += 1
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            if len(rows) < 4:
                filtered_count += 1
                continue
                
            types_row = rows[3]
            
            keep_indices = [0]
            is_str_col = {0: types_row[0] == 'str'}
            
            for i in range(1, len(types_row)):
                is_string = (types_row[i] == 'str')
                is_str_col[i] = is_string
                if is_string:
                    keep_indices.append(i)
                    
            output_rows = []
            for row_idx, row in enumerate(rows):
                new_row = []
                for i in keep_indices:
                    val = row[i] if i < len(row) else ""
                    
                    if row_idx == 3:
                        if val == 'int32': val = 'Int32'
                        elif val == 'str': val = 'String'
                    
                    # 避免逗号引发的问题，统一处理转义与加引号
                    val_str = str(val)
                    escaped_val = val_str.replace('"', '""')
                    
                    # 数据部分的字符串列必须加引号，其它列存在逗号或换行时也加引号
                    if row_idx > 3 and is_str_col.get(i, False):
                        new_row.append(f'"{escaped_val}"')
                    else:
                        if ',' in escaped_val or '"' in escaped_val or '\n' in escaped_val:
                            new_row.append(f'"{escaped_val}"')
                        else:
                            new_row.append(escaped_val)
                            
                output_rows.append(",".join(new_row))
                
            # 重建输出目录结构
            rel_path = os.path.relpath(file_path, input_dir)
            out_path = os.path.join(output_dir, rel_path)
            
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            
            # 手动写入避免 csv 模块再次进行不符预期的自动处理
            with open(out_path, 'w', encoding='utf-8', newline='') as f:
                f.write('\n'.join(output_rows) + '\n')
                
            processed_count += 1
        except Exception as e:
            print(f"\n处理文件 {file_path} 时出现错误: {e}")
            errored_files.append({"path": file_path, "error": str(e)})

    print("\n\n" + "=" * 40)
    print("CSV 文件处理完成！")
    print(f"找到的总文件数：{total_files}")
    print(f"成功处理的文件：{processed_count}")
    print(f"被过滤的文件数：{filtered_count}")
    print(f"处理出错的文件数：{len(errored_files)}")
    if errored_files:
        print("出错的文件列表：")
        for ef in errored_files:
            print(f" - {ef['path']}，错误信息：{ef['error']}")
    print("=" * 40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaintCoinach-GP RawExd CSV Processor")
    parser.add_argument('csv_dir', help="需要处理的 CSV 文件所在的目录")
    parser.add_argument('--output_dir', default="", help="输出目录 (留空则默认为 ./rawexd_output 目录)")
    
    args = parser.parse_args()
    
    input_dir = args.csv_dir
    output_dir = args.output_dir
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), "rawexd_output")
        
    if not os.path.isdir(input_dir):
        print(f"错误: 找不到目录 '{input_dir}'。")
        sys.exit(1)
        
    process_csv_files(input_dir, output_dir)
