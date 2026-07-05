import os
import re


def extract_project(md_path, output_root):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 匹配形如 "### 5.x `path/to/file`" 的标题行
    # 注意：可能用反引号或普通引号
    pattern = r'^###\s+\d+\.\d+\s+`([^`]+)`'
    lines = content.split('\n')

    file_path = None
    code_lines = []
    in_code = False
    lang = None
    created = []

    for line in lines:
        # 检查是否是文件路径标题
        m = re.match(pattern, line.strip())
        if m:
            # 如果之前有代码块未写入，先写入
            if file_path and code_lines:
                _write_file(output_root, file_path, code_lines, created)
            file_path = m.group(1)
            code_lines = []
            in_code = False
            continue

        # 处理代码块标记
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                lang = line.strip()[3:]
            else:
                in_code = False
                # 代码块结束，如果当前有 file_path，则收集的代码有效
                # 注意：代码块内容已经保存在 code_lines 中，会在下一个标题或文件末尾写入
            continue

        if in_code and file_path:
            code_lines.append(line)

    # 写入最后一个文件
    if file_path and code_lines:
        _write_file(output_root, file_path, code_lines, created)

    print(f"\n🎉 提取完成！共 {len(created)} 个文件保存到 {output_root}")


def _write_file(output_root, file_path, code_lines, created):
    full_path = os.path.join(output_root, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    code_content = '\n'.join(code_lines).rstrip()
    # 如果内容为空，添加一个占位注释
    if not code_content.strip():
        code_content = f"# {file_path}\n"
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(code_content)
    created.append(file_path)
    print(f"✅ 已创建: {file_path}")


if __name__ == "__main__":
    md_file = r"E:\项目交付\招投标智能问答系统 - 完整交付包 v4.0.md"
    output_dir = r"E:\BID_2_PROJECT"
    extract_project(md_file, output_dir)