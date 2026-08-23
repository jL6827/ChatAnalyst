"""Gradio 前端：聊天界面 + 图表内嵌展示。"""
import base64
import io

import gradio as gr

from agent import chat as agent_chat
from data_loader import find_data_file


def figs_to_markdown(figures) -> str:
    parts = []
    for img in figures:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        parts.append(f"![](data:image/png;base64,{b64})")
    return "\n\n".join(parts)


def respond(message, history, *args):
    data_file = find_data_file()
    if data_file is None:
        yield "⚠️ 未找到数据文件：请在项目 `data/` 目录下放入 `.csv` / `.xpt` / `.sav` 文件后刷新页面。"
        return

    history = list(history) + [{"role": "user", "content": message}]
    yield "⏳ 正在分析（调用工具执行真实计算）…"

    final_text = ""
    figures = []
    for text, figs in agent_chat(history):
        final_text, figures = text, figs

    answer = final_text or "（分析完成，但未生成文字结论）"
    if figures:
        answer += "\n\n" + figs_to_markdown(figures)
    yield answer


def build_ui() -> gr.Blocks:
    data_file = find_data_file()
    data_note = (
        f"当前数据文件：`{data_file.name}`" if data_file
        else "⚠️ `data/` 目录下暂无数据文件（支持 csv / xpt / sav）"
    )
    with gr.Blocks(title="ChatAnalyst - 对话式数据分析 Agent") as demo:
        gr.Markdown(
            f"""# ChatAnalyst · 对话式数据分析 Agent
用自然语言提问，Agent 调用工具执行真实 pandas 计算，返回结论与图表。

{data_note} · 模型：DeepSeek · 安全设计：拒答 / 幻觉抑制 / 注入防护（见 README）"""
        )
        gr.ChatInterface(
            fn=respond,
            examples=[
                "数据集有哪些字段？各自是什么类型？",
                "糖尿病组和非糖尿病组的 BMI 分布有何差异？画图并做检验",
                "用逻辑回归预测糖尿病，报告准确率和 AUC，并列出影响最大的5个因素",
                "今天天气怎么样？",  # 用于演示拒答
            ],
        )
    return demo


if __name__ == "__main__":
    build_ui().launch()
