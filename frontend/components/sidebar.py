# coding: utf-8
"""侧边栏 — 会话历史"""

import logging
import uuid

import streamlit as st

from frontend.api_client import (
    request_delete_session,
    request_history_list,
    request_session_messages,
)

logger = logging.getLogger("frontend.sidebar")


def fetch_session_messages(session_id: str):
    result = request_session_messages(session_id)
    if result["ok"]:
        data = result["data"]
        return data.get("messages", [])
    if result["retryable"]:
        st.error(f"服务暂时不可用，请稍后重试。错误编号：{result['request_id']}")
    else:
        st.error(f"会话加载失败。错误编号：{result['request_id']}")
    return []


def load_session(session_id: str, title: str):
    st.session_state.session_id = session_id
    st.session_state.session_title = title
    st.session_state.messages = fetch_session_messages(session_id)


def refresh_history():
    result = request_history_list()
    if result["ok"]:
        st.session_state.history_list = result["data"]
        return
    st.session_state.history_list = []


@st.fragment
def render_history_list():
    st.subheader("历史会话")
    refresh_history()
    for hist in st.session_state.history_list:
        col1, col2 = st.columns([5, 1])
        with col1:
            is_active = hist["session_id"] == st.session_state.session_id
            title = hist.get("title", "New Chat")
            if st.button(
                f"💬 {title}",
                key=f"btn_{hist['session_id']}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                load_session(hist["session_id"], title)
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{hist['session_id']}"):
                result = request_delete_session(hist["session_id"])
                if not result["ok"]:
                    if result["retryable"]:
                        st.error(f"服务暂时不可用。错误编号：{result['request_id']}")
                    else:
                        st.error(f"删除失败。错误编号：{result['request_id']}")
                    return
                if hist["session_id"] == st.session_state.session_id:
                    del st.session_state.app_initialized
                    st.rerun()
                st.rerun(scope="fragment")


def render_sidebar():
    with st.sidebar:
        if st.button("➕ 新建会话", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.session_title = "New Chat"
            st.session_state.messages = []
            st.rerun()

        st.divider()
        render_history_list()
