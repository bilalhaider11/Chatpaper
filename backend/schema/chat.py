from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=20)
    use_summary_routing: bool = True
    use_bm25: bool = True
    use_propositions: bool = False


class Citation(BaseModel):
    file_id: int
    filename: str
    page_start: int | None
    page_end: int | None
    content_preview: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: int
