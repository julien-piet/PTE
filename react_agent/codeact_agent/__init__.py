try:
    from opendevin.controller.agent import Agent
    from .codeact_agent import CodeActAgent
    Agent.register('CodeActAgent', CodeActAgent)
except ImportError:
    from .codeact_agent import CodeActAgent  # noqa: F401
