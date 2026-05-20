from pydantic import BaseModel, ConfigDict

############################# Conversation list ###################################################

class ConversationListBase(BaseModel):
    conversation_title: str | None = None


class ConversationListUpdate(BaseModel):
    id: int
    conversation_title: str | None = None
    is_active: bool | None = None


class ConversationListResponse(ConversationListBase):
    id: int
    conversation_title: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ConversationListRequest(BaseModel):
    conversation_title: str
    is_active: bool


#################################### Conversation ################################################

class ConversationResponse(BaseModel):
    statement: str
    user_type: str
    model_config = ConfigDict(from_attributes=True)
