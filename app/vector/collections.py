from dataclasses import dataclass

from qdrant_client.models import Distance


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    vector_size: int
    distance: Distance


def build_collection_specs(
    knowledge_base_name: str,
    question_bank_name: str,
    generated_questions_name: str,
    vector_size: int,
    distance_name: str,
) -> list[CollectionSpec]:
    distance = Distance[distance_name.upper()] if hasattr(Distance, distance_name.upper()) else Distance.COSINE
    return [
        CollectionSpec(name=knowledge_base_name, vector_size=vector_size, distance=distance),
        CollectionSpec(name=question_bank_name, vector_size=vector_size, distance=distance),
        CollectionSpec(name=generated_questions_name, vector_size=vector_size, distance=distance),
    ]
