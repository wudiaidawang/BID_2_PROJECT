#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
命令行交互式问答客户端
使用方式：
1. 确保 main.py 服务已经启动（运行 python main.py）
2. 在这个脚本所在的终端执行：python ask_cli.py
3. 输入问题后按回车，等待返回答案
4. 输入 'exit' 或 'quit' 退出
"""

import httpx
import json
import sys
from typing import Optional

API_BASE_URL = "http://localhost:8000"

def ask_question(question: str, session_id: Optional[str] = None) -> dict:
    """向 API 发送问题，返回完整响应"""
    payload = {"question": question}
    if session_id:
        payload["session_id"] = session_id

    try:
        # 超时时间设为 30 秒，避免卡死
        response = httpx.post(
            f"{API_BASE_URL}/api/v1/ask",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()  # 如果状态码不是 2xx，抛出异常
        return response.json()
    except httpx.ConnectError:
        return {"error": f"无法连接到服务，请确认 {API_BASE_URL} 上的 main.py 是否已启动"}
    except httpx.TimeoutException:
        return {"error": "请求超时，可能是服务处理时间过长或模型调用无响应"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP 错误 {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": f"未知错误: {str(e)}"}


def main():
    print("=" * 60)
    print("招投标智能问答系统 - 命令行客户端")
    print(f"服务地址: {API_BASE_URL}")
    print("输入问题后按回车，输入 'exit' 或 'quit' 退出")
    print("=" * 60)

    # 可选：先检查服务健康状态
    try:
        health = httpx.get(f"{API_BASE_URL}/api/v1/health", timeout=5.0)
        if health.status_code == 200:
            print("✅ 服务健康检查通过\n")
        else:
            print(f"⚠️ 服务状态异常，状态码: {health.status_code}\n")
    except Exception:
        print("⚠️ 无法获取服务健康状态，请确认 main.py 已启动\n")

    session_id = None
    while True:
        try:
            user_input = input("\n💬 请输入问题: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 退出")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 退出")
            break

        if not user_input:
            print("⚠️ 问题不能为空")
            continue

        print("⏳ 正在思考...")
        result = ask_question(user_input, session_id)

        if "error" in result:
            print(f"❌ 错误: {result['error']}")
            # 如果错误信息中包含详细堆栈，可以打印更多
            if "detail" in result:
                print(f"   详情: {result['detail']}")
            continue

        # 正常返回
        answer = result.get("answer", "没有返回答案")
        sources = result.get("sources", [])
        processing_time = result.get("processing_time", 0)
        session_id = result.get("session_id", session_id)

        print(f"\n🤖 答案: {answer}")
        if sources:
            print(f"\n📚 参考来源 (共{len(sources)}条):")
            for i, src in enumerate(sources[:3], 1):
                title = src.get("title", "无标题")
                content_preview = src.get("content_preview", "")[:100]
                print(f"  [{i}] {title}")
                print(f"      {content_preview}...")
        print(f"\n⏱️  处理耗时: {processing_time:.2f} 秒")
        print("-" * 60)
        if sources:
            print(f"\n📚 召回详情 (共 {len(sources)} 条，按相关性排序):")
            for i, src in enumerate(sources, 1):
                title = src.get("title", "无标题")
                content = src.get("content_preview", "")[:200]  # 前200字符
                score = src.get("score", 0.0)
                src_type = src.get("source_type", "未知")
                print(f"\n  [{i}] 来源: {src_type} | 分数: {score:.4f}")
                print(f"      标题: {title}")
                print(f"      预览: {content}...")
        else:
            print("\n⚠️ 没有召回任何文档")
            # ========================================

        print(f"\n⏱️  处理耗时: {processing_time:.2f} 秒")
        print("-" * 60)




if __name__ == "__main__":
    main()