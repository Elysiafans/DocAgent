from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeToolCallingModel(BaseChatModel):
    """按脚本依次返回消息的模型:可含 tool_calls 触发 ReAct 工具调用。"""

    responses: list
    tools: list | None = None

    def __init__(self, responses, **kwargs):
        super().__init__(responses=list(responses), **kwargs)

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def bind_tools(self, tools, **kwargs):
        self.tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.responses:
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content="完成"))]
            )
        return ChatResult(
            generations=[ChatGeneration(message=self.responses.pop(0))]
        )
