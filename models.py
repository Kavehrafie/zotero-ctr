import re

from pydantic import BaseModel, field_validator


class Creator(BaseModel):
    first: str = ""
    last: str = ""


class Item(BaseModel):
    key: str
    title: str
    item_type: str = ""
    year: int | None = None
    doi: str | None = None
    creator: Creator = Creator()

    @field_validator("year", mode="before")
    @classmethod
    def parse_year(cls, value):
        match = re.search(r"\d{4}", str(value or ""))
        return int(match.group()) if match else None


class Attachment(BaseModel):
    key: str
    filename: str = ""
    md5: str = ""
    parent_key: str = ""
