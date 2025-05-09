"""
Shared utilities for the Databricks App API.

This package provides common utilities for:
- Configuration management
- Database access
- Logging
- Job management
- Search functionality
- Notifications
- Git integration
- FastAPI middleware and dependencies
"""

from .config import ConfigManager, get_config_manager, get_settings, init_config
from .database import InMemorySession, get_db
from .deps import (
    get_db_dep,
    get_git_service_dep,
    get_job_runner_dep,
    get_notification_service_dep,
    get_search_service_dep,
    get_user_id,
    require_user_id,
)
from .git import GitService, get_git_service
from .job_runner import JobRunner, get_job_runner
from .logging import get_logger
from .middleware import ErrorHandlingMiddleware, LoggingMiddleware
from .notifications import NotificationService, get_notification_service
from .search import SearchService, get_search_service
from .workspace_client import CachingWorkspaceClient, get_workspace_client

__all__ = [
    "ConfigManager",
    "get_config_manager",
    "get_settings",
    "init_config",
    'get_db',
    'get_logger',
    'JobRunner',
    'get_job_runner',
    'SearchService',
    'get_search_service',
    'NotificationService',
    'get_notification_service',
    'GitService',
    'get_git_service',
    'get_db_dep',
    'get_notification_service_dep',
    'get_search_service_dep',
    'get_job_runner_dep',
    'get_git_service_dep',
    'get_user_id',
    'require_user_id',
    'LoggingMiddleware',
    'ErrorHandlingMiddleware',
    'CachingWorkspaceClient',
    'get_workspace_client',
    'get_sql_connection'
]
