from typing import Protocol


class ModelGateway(Protocol):
    def explain(self, prompt: str) -> str:
        ...


class DisabledModelGateway:
    def explain(self, prompt: str) -> str:
        return "AI模型尚未配置。本次仅返回规则和风控解释。"


class OpenAIModelGateway:
    def explain(self, prompt: str) -> str:
        raise NotImplementedError("OpenAI 接口将在配置 API Key 后接入")


class QwenModelGateway:
    def explain(self, prompt: str) -> str:
        raise NotImplementedError("通义千问接口将在配置 API Key 后接入")


class LocalModelGateway:
    def explain(self, prompt: str) -> str:
        raise NotImplementedError("本地模型接口将在模型路径确认后接入")
