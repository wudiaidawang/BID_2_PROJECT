#!/usr/bin/env python
"""模型基准测试工具 — 固定问题集 + 可切换模型/API，结果归档对比"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).parent

# 加载本地 .env（不依赖外层项目）
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    import httpx
except ImportError:
    print("请先安装: pip install httpx python-dotenv pyyaml")
    sys.exit(1)

DATA_DEFAULT = ROOT / "data" / "questions.json"
CONFIG_PATH = ROOT / "config.yaml"
OUTPUT_DIR = ROOT / "output"


# ═════════════════════════════════════════════════════════════════════════════
# 配置加载
# ═════════════════════════════════════════════════════════════════════════════

def _resolve_env(value: str) -> str:
    """将 ${VAR_NAME} 替换为环境变量值"""
    if not isinstance(value, str):
        return value

    def _replace(m):
        var = m.group(1)
        val = os.environ.get(var, "")
        if not val:
            print(f"  [WARN] 环境变量 {var} 未设置，使用空字符串")
        return val

    return re.sub(r"\$\{(\w+)\}", _replace, value)


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        print(f"[ERROR] 配置文件不存在: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 递归解析 ${ENV_VAR}
    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [walk(v) for v in obj]
        elif isinstance(obj, str):
            return _resolve_env(obj)
        return obj

    return walk(raw)


def load_questions(path: Path) -> list:
    if not path.exists():
        print(f"[ERROR] 问题文件不存在: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("[ERROR] 问题文件格式错误：应为 JSON 数组")
        sys.exit(1)

    return data


# ═════════════════════════════════════════════════════════════════════════════
# API 调用
# ═════════════════════════════════════════════════════════════════════════════

async def _call_api(
    question: str,
    model_cfg: dict,
    system_prompt: str = "",
    timeout: int = 60,
) -> dict:
    """调用 OpenAI 兼容 API，返回 {answer, elapsed_ms, tokens, error}"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})

    api_url = model_cfg["api_url"]
    api_key = model_cfg["api_key"]
    model = model_cfg.get("model", "")
    temperature = model_cfg.get("temperature", 0.3)
    max_tokens = model_cfg.get("max_tokens", 2000)

    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if resp.status_code == 200:
            body = resp.json()
            choice = body["choices"][0]
            usage = body.get("usage", {})
            return {
                "answer": choice["message"]["content"],
                "elapsed_ms": elapsed_ms,
                "tokens": {
                    "prompt": usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0),
                },
            }
        else:
            return {
                "answer": "",
                "elapsed_ms": elapsed_ms,
                "tokens": {},
                "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
            }
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return {"answer": "", "elapsed_ms": elapsed_ms, "tokens": {}, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# 运行测试
# ═════════════════════════════════════════════════════════════════════════════

async def run_benchmark(
    model_key: str,
    model_cfg: dict,
    questions: list,
    system_prompt: str = "",
    timeout: int = 60,
) -> dict:
    model_name = model_cfg.get("model", model_key)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'=' * 60}")
    print(f"模型: {model_name} ({model_key})")
    print(f"API:  {model_cfg['api_url']}")
    print(f"问题数: {len(questions)}")
    print(f"{'=' * 60}")

    results = []
    total_tokens = 0
    errors = 0

    for i, q in enumerate(questions, 1):
        qid = q.get("id", i)
        question = q["question"]
        print(f"  [{i}/{len(questions)}] Q{qid}: {question[:60]}...", end=" ", flush=True)

        out = await _call_api(question, model_cfg, system_prompt, timeout)

        if out.get("error"):
            print(f"ERROR: {out['error'][:80]}")
            errors += 1
        else:
            print(f"OK ({out['elapsed_ms']}ms, {out['tokens'].get('total', '?')}t)")

        total_tokens += out.get("tokens", {}).get("total", 0)
        results.append({
            "id": qid,
            "question": question,
            "expected_keywords": q.get("expected_keywords", []),
            "answer": out["answer"],
            "elapsed_ms": out["elapsed_ms"],
            "tokens": out.get("tokens", {}),
            "error": out.get("error", ""),
        })

    summary = {
        "total": len(questions),
        "errors": errors,
        "avg_elapsed_ms": int(sum(r["elapsed_ms"] for r in results) / len(results)) if results else 0,
        "total_tokens": total_tokens,
    }

    # 写入输出文件
    model_dir = OUTPUT_DIR / model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{timestamp}.json"

    report = {
        "model": model_name,
        "model_key": model_key,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "api_url": model_cfg["api_url"],
            "temperature": model_cfg.get("temperature"),
            "max_tokens": model_cfg.get("max_tokens"),
            "system_prompt": system_prompt,
        },
        "results": results,
        "summary": summary,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n结果: {output_path}")
    print(f"汇总: {summary['total']}题, {summary['errors']}错误, "
          f"平均 {summary['avg_elapsed_ms']}ms, 总 {summary['total_tokens']} tokens")
    return report


# ═════════════════════════════════════════════════════════════════════════════
# 对比模式
# ═════════════════════════════════════════════════════════════════════════════

def compare_models(model_a: str, model_b: str):
    """加载两个模型的最新结果并按 question id 对比"""
    def _latest(dir_path: Path) -> dict:
        files = sorted(dir_path.glob("*.json"))
        if not files:
            print(f"[ERROR] 没有找到结果文件: {dir_path}")
            sys.exit(1)
        with open(files[-1], "r", encoding="utf-8") as f:
            return json.load(f)

    report_a = _latest(OUTPUT_DIR / model_a)
    report_b = _latest(OUTPUT_DIR / model_b)

    results_a = {r["id"]: r for r in report_a["results"]}
    results_b = {r["id"]: r for r in report_b["results"]}
    all_ids = sorted(set(results_a) | set(results_b))

    print(f"\n{'=' * 80}")
    print(f"对比: {model_a}  vs  {model_b}")
    print(f"{'=' * 80}")

    for qid in all_ids:
        ra = results_a.get(qid, {})
        rb = results_b.get(qid, {})
        question = ra.get("question") or rb.get("question", "")

        print(f"\n--- Q{qid}: {question[:80]} ---")
        print(f"  [{model_a}] ({ra.get('elapsed_ms', '?')}ms): {ra.get('answer', 'N/A')[:200]}")
        print(f"  [{model_b}] ({rb.get('elapsed_ms', '?')}ms): {rb.get('answer', 'N/A')[:200]}")

    sa = report_a["summary"]
    sb = report_b["summary"]
    print(f"\n{'=' * 80}")
    print(f"汇总对比:")
    print(f"  {model_a}: {sa['total']}题, {sa['errors']}错, 平均 {sa['avg_elapsed_ms']}ms, {sa['total_tokens']}t")
    print(f"  {model_b}: {sb['total']}题, {sb['errors']}错, 平均 {sb['avg_elapsed_ms']}ms, {sb['total_tokens']}t")


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

async def main():
    global OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="模型基准测试工具 — 固定问题集，可切换模型/API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                          # 用默认模型测试
  python run.py --model deepseek         # 指定模型
  python run.py --all                    # 跑所有配置的模型
  python run.py --model hunyuan --system-prompt "你是法律专家"
  python run.py --compare hunyuan-standard deepseek-chat
        """,
    )
    parser.add_argument("--model", "-m", type=str, help="指定模型 key（对应 config.yaml 中 models 下的键）")
    parser.add_argument("--all", action="store_true", help="跑所有已配置的模型")
    parser.add_argument("--data", type=str, default=str(DATA_DEFAULT), help="问题文件路径")
    parser.add_argument("--system-prompt", type=str, default="", help="系统提示词（覆盖 config.yaml 中的默认值）")
    parser.add_argument("--compare", nargs=2, metavar=("MODEL_A", "MODEL_B"), help="对比两个模型的最新结果")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR), help="输出目录")
    args = parser.parse_args()

    OUTPUT_DIR = Path(args.output)

    # 对比模式
    if args.compare:
        compare_models(args.compare[0], args.compare[1])
        return

    # 加载配置 & 问题
    config = load_config()
    questions = load_questions(Path(args.data))
    if not questions:
        print("[ERROR] 问题集为空")
        return

    system_prompt = args.system_prompt or config.get("test", {}).get("system_prompt", "")
    timeout = config.get("test", {}).get("request_timeout", 60)

    models = config.get("models", {})
    if not models:
        print("[ERROR] config.yaml 中没有配置任何模型")
        return

    # 确定要跑的模型列表
    if args.all:
        model_keys = list(models.keys())
    elif args.model:
        if args.model not in models:
            print(f"[ERROR] 未找到模型: {args.model}，可用: {', '.join(models.keys())}")
            return
        model_keys = [args.model]
    else:
        default = config.get("default", list(models.keys())[0] if models else None)
        if not default:
            print("[ERROR] 无默认模型且无 --model 指定")
            return
        model_keys = [default]

    # 验证 API Key
    for mk in model_keys:
        cfg = models[mk]
        if not cfg.get("api_key"):
            env_var = re.findall(r"\$\{(\w+)\}", yaml.dump(cfg))
            print(f"[ERROR] 模型 '{mk}' 的 api_key 未设置。请设置环境变量: {', '.join(env_var) if env_var else 'api_key'}")
            return

    # 逐个模型跑测试
    for mk in model_keys:
        await run_benchmark(mk, models[mk], questions, system_prompt, timeout)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
