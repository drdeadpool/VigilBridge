from sqlalchemy import Select, select

from app.models import Observation

VALID_DATA_QUALITY_STATUS = "valid"


def observation_query(*, include_invalid: bool = False) -> Select:
    query = select(Observation)
    if not include_invalid:
        query = query.where(
            Observation.data_quality_status == VALID_DATA_QUALITY_STATUS
        )
    return query
