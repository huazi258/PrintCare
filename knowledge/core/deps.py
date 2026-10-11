from functools import cache, lru_cache

from knowledge.services.import_file_service import ImportFileService
from knowledge.services.query_service import QueryService
from knowledge.services.diagnosis_service import DiagnosisService


@cache
def get_import_file_service() -> ImportFileService:
    """工厂函数  单例模式"""
    return ImportFileService()


@lru_cache
def get_query_service() -> QueryService:
    return QueryService()


@lru_cache
def get_diagnosis_service() -> DiagnosisService:
    """Shared orchestration service; repository state remains MongoDB-backed."""
    return DiagnosisService(query_service=get_query_service())
