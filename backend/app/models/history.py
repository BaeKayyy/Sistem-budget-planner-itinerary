from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SearchHistoryBase(BaseModel):
    query: str = Field(
        min_length=1,
        description="Search query submitted by the authenticated user.",
        examples=["pantai"],
    )

    @field_validator("query")
    @classmethod
    def trim_and_validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("Search query cannot be empty.")

        return query


class SearchHistoryCreate(SearchHistoryBase):
    # user_id is intentionally not accepted from the frontend.
    # It must come from the authenticated JWT user to prevent cross-user writes.
    pass


class SearchHistoryResponse(SearchHistoryBase):
    id: str = Field(
        description="Public search history identifier returned by the API.",
        examples=["665f1c2d8b4f5f0012a34567"],
    )
    user_id: str = Field(
        description="Authenticated user identifier that owns this search history item.",
        examples=["665f1c2d8b4f5f0012a11111"],
    )
    created_at: datetime = Field(
        description="UTC timestamp when this search was saved.",
        examples=["2026-05-10T10:30:00Z"],
    )
