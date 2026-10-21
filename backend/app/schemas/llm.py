"""Pydantic schemas for the LLM chat endpoint."""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User question for the property-intelligence assistant.",
        examples=["Explain why property documents should be cross-checked."],
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty or whitespace-only")
        return value


class ChatResponse(BaseModel):
    answer: str = Field(
        ...,
        description="Generated assistant answer. Phase 1 answers are general and are not grounded in retrieved property documents.",
    )
