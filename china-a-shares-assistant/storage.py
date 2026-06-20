"""自选股管理(会话级隔离)。

每个浏览器会话(每位访问者)拥有独立的自选股,互不影响,适合多人分享。
数据存于 st.session_state,关闭页面后不保留;首次打开会载入一份默认清单。
函数签名与此前的文件版保持一致,界面层无需改动。
"""

from __future__ import annotations

import streamlit as st

# 新会话的默认自选股(跨板块/行业的示例)
DEFAULTS: list[dict] = [
    {"code": "600519", "name": "贵州茅台"},
    {"code": "000858", "name": "五粮液"},
    {"code": "000001", "name": "平安银行"},
    {"code": "688981", "name": "中芯国际"},
    {"code": "300750", "name": "宁德时代"},
]

_KEY = "watchlist"


def _wl() -> list[dict]:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = [d.copy() for d in DEFAULTS]
    return st.session_state[_KEY]


def load_watchlist() -> list[dict]:
    return list(_wl())


def add_watch(code: str, name: str) -> list[dict]:
    code = str(code).zfill(6)
    items = _wl()
    if not any(it["code"] == code for it in items):
        items.append({"code": code, "name": name})
    return list(items)


def remove_watch(code: str) -> list[dict]:
    code = str(code).zfill(6)
    st.session_state[_KEY] = [it for it in _wl() if it["code"] != code]
    return list(st.session_state[_KEY])


def is_watched(code: str) -> bool:
    code = str(code).zfill(6)
    return any(it["code"] == code for it in _wl())
