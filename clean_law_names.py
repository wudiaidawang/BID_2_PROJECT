#!/usr/bin/env python
"""用 GLM-4.1V-Thinking-FlashX 清洗 policy_chunks_export.json 中被污染的 law_name"""
import json, sys, time, shutil
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import settings

CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export.json"
BACKUP_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export_backup_before_law_fix.json"
MODEL = "GLM-4.1V-Thinking-FlashX"

def main():
    # 1. 加载
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)

    # 提取所有不重复非空脏法规名
    unique_dirty = list(set([
        c["law_name"] for c in chunks_data["chunks"]
        if c.get("law_name", "").strip()
    ]))
    print(f"去重后脏法规名数量: {len(unique_dirty)}")

    # 2. 构建 prompt
    ai_prompt = f"""你是一个专业的数据清洗专家。下面有一批从法律 PDF 文件中由于解析错位、截断导致的错误法规名称。
请根据你的上下文语感，推测出它们真正、完整的官方标准法律法规名称。

错误名称列表：
{unique_dirty}

请直接返回一个标准的 Python JSON 字典，格式严格为: {{"错误名称": "完整官方标准名称"}}，不要任何Markdown标记、解释或废话。"""

    # 3. 调用 FlashX
    api_key = settings.llm_api_key
    base_url = settings.llm_api_url.replace("/chat/completions", "")
    client = OpenAI(base_url=base_url, api_key=api_key)

    print("正在调用 GLM-4.1V-Thinking-FlashX 进行清洗...")
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的数据清洗专家，擅长纠正OCR/PDF解析导致的文本错误。"},
                    {"role": "user", "content": ai_prompt},
                ],
                temperature=0.3,
                max_tokens=16384,
                timeout=300,
                extra_body={"thinking": {"type": "enabled"}},
            )
            content = resp.choices[0].message.content
            if not content:
                content = getattr(resp.choices[0].message, "reasoning_content", "")
            break
        except Exception as e:
            print(f"  调用失败 (尝试 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    else:
        print("LLM 调用失败，退出")
        return

    # 保存模型原始响应用于调试
    raw_path = CHUNKS_PATH.parent / "law_name_fix_raw_response.txt"
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"原始响应已保存: {raw_path}")

    # 4. 解析返回
    clean = content.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:]) if len(lines) > 1 else clean
        if clean.endswith("```"):
            clean = clean[:-3]
    clean = clean.strip()

    try:
        correction_map = json.loads(clean)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            correction_map = json.loads(match.group())
        else:
            print(f"JSON 解析失败，原始响应前 2000 字符:\n{content[:2000]}")
            return

    if not isinstance(correction_map, dict):
        print(f"返回类型错误: {type(correction_map)}")
        return

    print(f"获取到 {len(correction_map)} 条映射")

    # 5. 应用修正
    corrected_count = 0
    unchanged_count = 0
    for chunk in chunks_data["chunks"]:
        old_name = chunk.get("law_name", "")
        if old_name and old_name in correction_map:
            new_name = correction_map[old_name]
            if new_name != old_name:
                chunk["law_name"] = new_name
                corrected_count += 1
            else:
                unchanged_count += 1

    print(f"修正: {corrected_count} 条, 不变: {unchanged_count} 条")

    # 6. 备份 + 保存
    shutil.copy2(CHUNKS_PATH, BACKUP_PATH)
    print(f"已备份到: {BACKUP_PATH}")

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {CHUNKS_PATH}")

    # 7. 打印修正示例
    print("\n--- 修正示例 ---")
    shown = 0
    for dirty, clean_name in sorted(correction_map.items(), key=lambda x: len(x[0]), reverse=True):
        if dirty != clean_name:
            print(f"  [{dirty}]")
            print(f"   → [{clean_name}]\n")
            shown += 1
            if shown >= 30:
                break


if __name__ == "__main__":
    main()
