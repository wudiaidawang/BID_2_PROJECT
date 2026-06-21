# coding: utf-8
"""招投标智能问答系统 — Streamlit 流式前端"""

import uuid

import streamlit as st

from frontend.components.chat_view import render_chat
from frontend.components.sidebar import load_session, refresh_history, render_sidebar


def init_state():
    if "app_initialized" not in st.session_state:
        refresh_history()

        if st.session_state.history_list:
            first_session = st.session_state.history_list[0]
            load_session(first_session["session_id"], first_session.get("title", "New Chat"))
        else:
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.session_title = "New Chat"
            st.session_state.messages = []

        st.session_state.app_initialized = True


def main():
    st.set_page_config(page_title="招投标智能问答", layout="wide")
    init_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
