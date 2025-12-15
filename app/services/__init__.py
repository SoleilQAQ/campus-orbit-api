# app/services/__init__.py
"""服务层模块"""

from .weather_service import WeatherService
from .academic_service import AcademicService

__all__ = ["WeatherService", "AcademicService"]
