from pydantic import BaseModel, ConfigDict

############################# Conversation list ###################################################

class ConversationListBase(BaseModel):
    conversation_title: str | None = None



class ConversationListUpdate(BaseModel):
    id:int
    conversation_title: str | None = None
    is_active: bool | None = None

class ConversationListResponse(ConversationListBase):
    id: int
    conversation_title:str
    is_active:bool

class ConversationListRequest():

    conversation_title:str
    is_active: bool
    
    
 #################################### Conversation ################################3   
    
class ConversationResponse(BaseModel):
    
    statement:str
    user_type:str
    