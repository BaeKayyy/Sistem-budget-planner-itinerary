from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    name: str = Field(examples=["Pantai Jogan"])
    type: str = Field(examples=["wisata"])
    rating: float | None = Field(default=None, examples=[4.3])
    price_estimate: int = Field(examples=[10000])
    similarity_score: float = Field(examples=[0.6593])


class RecommendationResponse(BaseModel):
    query: str = Field(examples=["pantai"])
    filter_type: str | None = Field(default=None, examples=["wisata"])
    total_results: int = Field(examples=[5])
    results: list[RecommendationItem]


class SystemStatusResponse(BaseModel):
    dataset_rows: int = Field(examples=[745])
    matrix_shape: list[int] = Field(examples=[[745, 3830]])
    vocabulary_size: int = Field(examples=[3830])
