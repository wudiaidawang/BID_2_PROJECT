# coding: utf-8
"""对话视图 — 流式渲染"""

import logging

import streamlit as st

from frontend.api_client import request_chat_stream
from frontend.components.sidebar import refresh_history

logger = logging.getLogger("frontend.chat")


def render_chat():
    # 1. 渲染历史消息
    for msg in st.session_state.messages:
        msg_type = msg["type"]
        content = msg["content"]
        if msg_type == "user":
            with st.chat_message("user"):
                st.markdown(content)
        elif msg_type == "assistant":
            with st.chat_message("assistant"):
                st.markdown(content)
        elif msg_type == "reasoning":
            with st.chat_message("assistant"):
                with st.status("Show Thinking", state="complete", expanded=False):
                    st.markdown(content)
        elif msg_type == "error":
            with st.chat_message("assistant"):
                st.error(content)

    # 2. 输入框
    if user_message := st.chat_input("输入问题，按 Enter 发送"):
        is_first_turn = (st.session_state.session_title == "New Chat")

        with st.chat_message("user"):
            st.markdown(user_message)

        with st.chat_message("assistant"):
            status_container = None
            status_placeholder = None
            response_placeholder = st.empty()

            full_response = ""
            full_reasoning = ""
            full_error = ""

            payload = {
                "session_id": st.session_state.session_id,
                "session_title": st.session_state.session_title,
                "user_message": user_message,
            }

            def handle_stream_payload(stream_payload: dict) -> None:
                nonlocal full_response, full_reasoning, full_error, status_container, status_placeholder

                match stream_payload:
                    case {"type": "reasoning", "content": str(chunk_content)}:
                        full_reasoning += chunk_content
                        if status_container is None:
                            status_container = st.status("Model is thinking...", expanded=True)
                            status_placeholder = status_container.empty()
                        status_placeholder.markdown(full_reasoning + "▌")
                    case {"type": "assistant", "content": str(chunk_content)}:
                        if status_container is not None and getattr(status_container, "_state", "") != "complete":
                            status_placeholder.markdown(full_reasoning)
                            status_container.update(label="Show Thinking", state="complete", expanded=False)
                        full_response += chunk_content
                        response_placeholder.markdown(full_response + "▌")
                    case {"type": "error", "content": str(error_content)}:
                        full_error += error_content
                        logger.warning("Stream error received | content=%s", error_content)
                        st.error(error_content)

            result = request_chat_stream(payload, handle_stream_payload)
            if result["ok"]:
                response_placeholder.markdown(full_response)
            elif result["retryable"]:
                st.error(f"服务暂时不可用，请稍后重试。错误编号：{result['request_id']}")
            else:
                st.error(f"本次回答生成失败。错误编号：{result['request_id']}")

            st.session_state.messages.append({"type": "user", "content": user_message})
            if full_reasoning:
                st.session_state.messages.append({"type": "reasoning", "content": full_reasoning})
            if full_response:
                st.session_state.messages.append({"type": "assistant", "content": full_response})
            if full_error:
                st.session_state.messages.append({"type": "error", "content": full_error})

            if is_first_turn:
                st.session_state.session_title = user_message[:30]
                refresh_history()
                st.rerun()
