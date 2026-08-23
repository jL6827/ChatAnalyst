"""Agent 核心循环：LLM function calling（OpenAI 兼容接口，默认智谱 GLM）+ 工具执行。"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from prompts import SYSTEM_PROMPT
from tools import TOOLS_SPEC, execute_tool

load_dotenv()

MAX_TOOL_ROUNDS = 6
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"  # 智谱 GLM
DEFAULT_MODEL = "glm-4.6"


def get_client() -> OpenAI:
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 LLM_API_KEY，请复制 .env.example 为 .env 并填入")
    return OpenAI(
        api_key=api_key,
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
    )


def get_model() -> str:
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)


def chat(history: list):
    """执行一轮对话。history 为 OpenAI messages 格式（不含 system）。

    yield: (文本增量或完整段落, 本轮图片列表)
    """
    client = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    figures = []

    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=TOOLS_SPEC,
            stream=False,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            yield msg.content or "", figures
            return

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                tool_text, tool_figs = execute_tool(tc.function.name, args)
            except Exception as e:  # 工具异常也回传给模型，让它决定如何向用户解释
                tool_text, tool_figs = f"工具执行异常: {e}", []
            figures.extend(tool_figs)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_text[:4000],
                }
            )

    yield "分析步骤过多已中止，请尝试简化问题（例如先看单变量的分布）。", figures
