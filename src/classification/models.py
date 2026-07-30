from typing import Literal

from pydantic import BaseModel


class ClassificationResult(BaseModel):
    category: Literal["A", "N"]
    language: str
    to_verify: bool
    reason: str = ""
    team_division: str = ""
