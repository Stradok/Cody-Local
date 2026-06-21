from typing import Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    messages: list[dict] = Field(default_factory=list)
    workspace: str = Field(default=".")
    model: str = Field(default="")
    session_id: str = Field(default="")
    mode: str = Field(default="build")  # "plan" or "build"

    plan: list[str] = Field(default_factory=list)
    step_types: list[str] = Field(default_factory=list)  # "coding"|"filesystem"|"terminal"|"validation" per step
    done: list[bool] = Field(default_factory=list)
    current_step: int = Field(default=0)
    max_iterations: int = Field(default=30)
    iteration_count: int = Field(default=0)

    error: Optional[str] = None
    finish_reason: Optional[str] = None
