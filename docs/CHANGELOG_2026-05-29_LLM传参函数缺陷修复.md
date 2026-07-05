# RAG → Agent 架构升级问题总结（项目更新日志）

## 背景

项目初期是传统 RAG 架构：

```python
_call_llm(prompt: str)
```

整个流程为：

```text
用户问题
→ 检索器召回文本
→ 拼接 Prompt
→ LLM 生成回答
```

LLM 输入始终是：

```text
单个字符串 prompt
```

因此 generator.py 的 `_call_llm()` 只支持：

```python
prompt: str
```

即可满足需求。

---

# 架构升级

后期项目新增：

* Router
* Agent
* Tool Calling

系统从：

```text
单轮 RAG
```

升级为：

```text
多轮 Agent 工作流
```

此时 LLM 输入结构发生变化。

Agent 不再只传：

```text
纯文本 prompt
```

而是需要传：

```python
messages = [
    {"role": "system", ...},
    {"role": "user", ...},
    {"role": "assistant", ...},
    {"role": "tool", ...}
]
```

其中包含：

* 历史对话
* Tool Call
* Tool Result
* 中间推理状态

---

# 出现的问题

Router / Agent 模块开始按新版方式调用：

```python
_call_llm(
    messages=messages,
    temperature=0
)
```

但底层 generator.py 中的：

```python
_call_llm()
```

仍停留在旧版接口：

```python
_call_llm(prompt: str)
```

仅支持单字符串输入。

导致：

* messages 无法正确传递
* tool result 无法进入上下文
* 多轮状态丢失
* temperature 等参数失效
* Agent 部分路径触发时报接口签名错误

---

# 问题本质

不是：

```text
RAG 检索失败
```

也不是：

```text
数据内容丢失
```

而是：

```text
LLM 输入结构从 “prompt string”
升级为了 “messages array”
```

但底层公共接口没有同步升级。

属于：

```text
架构演进过程中的接口兼容问题
```

本质是：

```text
旧版单轮 RAG 接口
无法承载新版 Agent 工作流状态
```

---

# 技术债来源

从 git 历史可发现：

* 初始提交仅存在 generator.py
* 后续某次 commit 同时新增 Router 与 Agent
* 新模块使用新版 messages 调用方式
* 但底层 `_call_llm()` 未同步重构

因此形成：

```text
新调用方 + 旧底层接口
```

的兼容性隐患。

问题此前未暴露，原因可能是：

* 某些 Agent 路径未真正执行
* 参数被部分吞掉
* Tool Calling 流程未完整走通

直到后期复杂链路运行时才正式触发。

---

# 后续改造方向

统一 LLM 调用层：

旧版：

```python
_call_llm(prompt: str)
```

升级为：

```python
_call_llm(
    messages: list,
    temperature: float = 0.7,
    max_tokens: int = ...
)
```

同时兼容：

* 普通 RAG
* Router
* Agent
* Tool Calling
* 多轮对话

实现：

```text
统一 LLM Gateway
```

避免后续模块继续出现接口分裂。
