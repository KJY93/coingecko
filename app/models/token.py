from pydantic import BaseModel

class Token(BaseModel):
    access_token: str # the JWT string
    token_type: str # conventionally bearer