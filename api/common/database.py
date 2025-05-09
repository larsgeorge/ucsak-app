import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar

from sqlalchemy import create_engine, Index  # Need Index for type checking
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import CreateTable
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy import event

from alembic import command
# Rename the Alembic Config import to avoid collision
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

from .config import get_settings, Settings
from .logging import get_logger
from api.common.workspace_client import get_workspace_client
# Import SDK components
from databricks.sdk.errors import NotFound, DatabricksError
from databricks.sdk.core import Config, oauth_service_principal

logger = get_logger(__name__)

T = TypeVar('T')

# Define the base class for SQLAlchemy models
Base = declarative_base()

# --- Explicitly import all model modules HERE to register them with Base --- #
# This ensures Base.metadata is populated before init_db needs it.
logger.debug("Importing all DB model modules to register with Base...")
try:
    from api.db_models import settings as settings_db
    from api.db_models import audit_log
    from api.db_models import data_asset_reviews
    from api.db_models import data_products
    from api.db_models import notifications
    from api.db_models import data_domains
    # Add imports for any other future model modules here
    logger.debug("DB model modules imported successfully.")
except ImportError as e:
    logger.critical(
        f"Failed to import a DB model module during initial registration: {e}", exc_info=True)
    # This is likely a fatal error, consider raising or exiting
    raise
# ------------------------------------------------------------------------- #

# Singleton engine instance
_engine = None
_SessionLocal = None
# Public engine instance (will be assigned after creation)
engine = None


@dataclass
class InMemorySession:
    """In-memory session for managing transactions."""
    changes: List[Dict[str, Any]]

    def __init__(self):
        self.changes = []

    def commit(self):
        """Commit changes to the global store."""

    def rollback(self):
        """Discard changes."""
        self.changes = []


class InMemoryStore:
    """In-memory storage system."""

    def __init__(self):
        """Initialize the in-memory store."""
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def create_table(self, table_name: str, metadata: Dict[str, Any] = None) -> None:
        """Create a new table in the store.

        Args:
            table_name: Name of the table
            metadata: Optional metadata for the table
        """
        if table_name not in self._data:
            self._data[table_name] = []
            if metadata:
                self._metadata[table_name] = metadata

    def insert(self, table_name: str, data: Dict[str, Any]) -> None:
        """Insert a record into a table.

        Args:
            table_name: Name of the table
            data: Record to insert
        """
        if table_name not in self._data:
            self.create_table(table_name)

        # Add timestamp and id if not present
        if 'id' not in data:
            data['id'] = str(len(self._data[table_name]) + 1)
        if 'created_at' not in data:
            data['created_at'] = datetime.utcnow().isoformat()
        if 'updated_at' not in data:
            data['updated_at'] = data['created_at']

        self._data[table_name].append(data)

    def get(self, table_name: str, id: str) -> Optional[Dict[str, Any]]:
        """Get a record by ID.

        Args:
            table_name: Name of the table
            id: Record ID

        Returns:
            Record if found, None otherwise
        """
        if table_name not in self._data:
            return None
        return next((item for item in self._data[table_name] if item['id'] == id), None)

    def get_all(self, table_name: str) -> List[Dict[str, Any]]:
        """Get all records from a table.

        Args:
            table_name: Name of the table

        Returns:
            List of records
        """
        return self._data.get(table_name, [])

    def update(self, table_name: str, id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record.

        Args:
            table_name: Name of the table
            id: Record ID
            data: Updated data

        Returns:
            Updated record if found, None otherwise
        """
        if table_name not in self._data:
            return None

        for item in self._data[table_name]:
            if item['id'] == id:
                item.update(data)
                item['updated_at'] = datetime.utcnow().isoformat()
                return item
        return None

    def delete(self, table_name: str, id: str) -> bool:
        """Delete a record.

        Args:
            table_name: Name of the table
            id: Record ID

        Returns:
            True if deleted, False otherwise
        """
        if table_name not in self._data:
            return False

        initial_length = len(self._data[table_name])
        self._data[table_name] = [
            item for item in self._data[table_name] if item['id'] != id]
        return len(self._data[table_name]) < initial_length

    def clear(self, table_name: str) -> None:
        """Clear all records from a table.

        Args:
            table_name: Name of the table
        """
        if table_name in self._data:
            self._data[table_name] = []


class DatabaseManager:
    """Manages in-memory database operations."""

    def __init__(self) -> None:
        """Initialize the database manager."""
        self.store = InMemoryStore()

    @contextmanager
    def get_session(self) -> InMemorySession:
        """Get a database session.

        Yields:
            In-memory session

        Raises:
            Exception: If session operations fail
        """
        session = InMemorySession()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e!s}")
            raise

    def dispose(self) -> None:
        """Clear all data from the store."""
        self.store = InMemoryStore()


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def get_db_url(settings: Settings) -> str:
    """Constructs the Databricks SQLAlchemy URL."""
    logger.info(f"Configuring database connection for type: {settings.DATABASE_TYPE}")
    if settings.DATABASE_TYPE == "postgres":
        if not all([settings.POSTGRES_HOST, settings.POSTGRES_USER, settings.POSTGRES_PASSWORD, settings.POSTGRES_DB]):
            raise ValueError("PostgreSQL connection details (Host, User, Password, DB) are missing in settings.")
        # Using psycopg2 driver
        url = (
            f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
            f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            f"?sslmode=require"
        )
        logger.debug(f"Constructed PostgreSQL SQLAlchemy URL (credentials redacted, sslmode=require)")
        return url
    elif settings.DATABASE_TYPE == "databricks":
        token = os.getenv("DATABRICKS_TOKEN")
        if not settings.DATABRICKS_HOST or not settings.DATABRICKS_HTTP_PATH:
            raise ValueError("DATABRICKS_HOST and DATABRICKS_HTTP_PATH must be configured.")
        host = settings.DATABRICKS_HOST.replace("https://", "")
        schema = settings.DATABRICKS_SCHEMA or "default"
        catalog = settings.DATABRICKS_CATALOG or "main"
        url = (
            f"databricks://token:{token}@{host}"
            f"?http_path={settings.DATABRICKS_HTTP_PATH}"
            f"&catalog={catalog}"
            f"&schema={schema}"
        )
        logger.debug(f"Constructed Databricks SQLAlchemy URL (token redacted)")
        return url
    else:
        raise ValueError(f"Unsupported DATABASE_TYPE: {settings.DATABASE_TYPE}")


def ensure_catalog_schema_exists(settings: Settings):
    """Checks if the configured catalog and schema exist, creates them if not."""
    logger.info("Ensuring required catalog and schema exist...")
    try:
        # Get a workspace client instance (use the underlying client to bypass caching)
        caching_ws_client = get_workspace_client(settings)
        ws_client = caching_ws_client._client  # Access raw client

        catalog_name = settings.DATABRICKS_CATALOG
        schema_name = settings.DATABRICKS_SCHEMA
        full_schema_name = f"{catalog_name}.{schema_name}"

        # 1. Check/Create Catalog
        try:
            logger.debug(f"Checking existence of catalog: {catalog_name}")
            ws_client.catalogs.get(catalog_name)
            logger.info(f"Catalog '{catalog_name}' already exists.")
        except NotFound:
            logger.warning(
                f"Catalog '{catalog_name}' not found. Attempting to create...")
            try:
                ws_client.catalogs.create(name=catalog_name)
                logger.info(f"Successfully created catalog: {catalog_name}")
            except DatabricksError as e:
                logger.critical(
                    f"Failed to create catalog '{catalog_name}': {e}. Check permissions.", exc_info=True)
                raise ConnectionError(
                    f"Failed to create required catalog '{catalog_name}': {e}") from e
        except DatabricksError as e:
            logger.error(
                f"Error checking catalog '{catalog_name}': {e}", exc_info=True)
            raise ConnectionError(
                f"Failed to check catalog '{catalog_name}': {e}") from e

        # 2. Check/Create Schema
        try:
            logger.debug(f"Checking existence of schema: {full_schema_name}")
            ws_client.schemas.get(full_schema_name)
            logger.info(f"Schema '{full_schema_name}' already exists.")
        except NotFound:
            logger.warning(
                f"Schema '{full_schema_name}' not found. Attempting to create...")
            try:
                ws_client.schemas.create(
                    name=schema_name, catalog_name=catalog_name)
                logger.info(f"Successfully created schema: {full_schema_name}")
            except DatabricksError as e:
                logger.critical(
                    f"Failed to create schema '{full_schema_name}': {e}. Check permissions.", exc_info=True)
                raise ConnectionError(
                    f"Failed to create required schema '{full_schema_name}': {e}") from e
        except DatabricksError as e:
            logger.error(
                f"Error checking schema '{full_schema_name}': {e}", exc_info=True)
            raise ConnectionError(
                f"Failed to check schema '{full_schema_name}': {e}") from e

    except Exception as e:
        logger.critical(
            f"An unexpected error occurred during catalog/schema check/creation: {e}", exc_info=True)
        raise ConnectionError(
            f"Failed during catalog/schema setup: {e}") from e


def get_current_db_revision(engine_connection: Connection, alembic_cfg: AlembicConfig) -> str | None:
    """Gets the current revision of the database."""
    context = MigrationContext.configure(engine_connection)
    return context.get_current_revision()


def init_db() -> None:
    """Initializes the database connection, checks/creates catalog/schema, and runs migrations."""
    global _engine, _SessionLocal, engine
    settings = get_settings()

    if _engine is not None:
        logger.debug("Database engine already initialized.")
        return

    logger.info("Initializing database engine and session factory...")

    try:
        db_url = get_db_url(settings)

        if settings.DATABASE_TYPE == "databricks":
            # Ensure target catalog and schema exist before connecting engine (uses API)
            ensure_catalog_schema_exists(settings)
            # Databricks specific connect_args
            logger.info(f"Environment for DB connection: {settings.ENV}")
            if settings.ENV.startswith('LOCAL'):
                connect_args = {
                    "server_hostname": settings.DATABRICKS_HOST,
                    "http_path": settings.DATABRICKS_HTTP_PATH,
                    "access_token": settings.DATABRICKS_TOKEN,
                }
            else:
                cfg = Config() # Hands in SQL host and OAuth function when run in Databricks
                connect_args = {
                    "server_hostname": cfg.host,
                    "http_path": settings.DATABRICKS_HTTP_PATH,
                    "credentials_provider": lambda: cfg.authenticate,
                    "auth_type": "databricks-oauth",
                }
        elif settings.DATABASE_TYPE == "postgres":
            # No special pre-checks needed for standard PG catalog/schema
            # Standard connect_args for PG are usually empty or handled by the URL
            connect_args = {}
        else:
            raise NotImplementedError(f"Database type {settings.DATABASE_TYPE} not fully implemented in init_db.")

        logger.info("Connecting to database...")
        logger.info(f"- Database URL: {db_url}")
        logger.info(f"- Connect args: {connect_args}")
        _engine = create_engine(db_url,
                                connect_args=connect_args, 
                                echo=settings.DB_ECHO, 
                                poolclass=pool.QueuePool, 
                                pool_size=5, 
                                max_overflow=10,
                                pool_recycle=840,
                                pool_pre_ping=True)
        engine = _engine # Assign to public variable

        # def refresh_connection(dbapi_connection, connection_record):
        #     if dbapi_connection.is_closed() or not dbapi_connection.is_valid():
        #         connection_record.invalidate()

        # event.listen(engine, "engine_connect", refresh_connection)

        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info("Database engine and session factory initialized.")

        # --- Alembic Migration Logic --- #
        alembic_cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..' , 'alembic.ini'))
        logger.info(f"Loading Alembic configuration from: {alembic_cfg_path}")
        alembic_cfg = AlembicConfig(alembic_cfg_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url) # Ensure Alembic uses the same URL
        script = ScriptDirectory.from_config(alembic_cfg)
        head_revision = script.get_current_head()
        logger.info(f"Alembic Head Revision: {head_revision}")

        # Create a connection for Alembic context
        with engine.connect() as connection:
            logger.info("Getting current database revision...")
            db_revision = get_current_db_revision(connection, alembic_cfg)
            logger.info(f"Current Database Revision: {db_revision}")

            # if db_revision != head_revision:
            #     logger.warning(f"Database revision '{db_revision}' differs from head revision '{head_revision}'.")
            #     if settings.APP_DEMO_MODE:
            #         # WARNING: This wipes data in managed tables!
            #         border = "=" * 50
            #         logger.warning(border)
            #         logger.warning("APP_DEMO_MODE: Database revision differs from head revision.")
            #         logger.warning(f"DB: {db_revision}, Head: {head_revision}")
            #         logger.warning("Performing Alembic downgrade to base and upgrade to head...")
            #         logger.warning("THIS WILL WIPE ALL DATA IN MANAGED TABLES!")
            #         logger.warning(border)
            #         try:
            #             # Remove logging around downgrade/upgrade
            #             logger.info("Downgrading database to base version...")
            #             command.downgrade(alembic_cfg, "base")
            #             logger.info("Upgrading database to head version...")
            #             command.upgrade(alembic_cfg, "head")
            #             logger.info("Alembic downgrade/upgrade completed successfully.") # Keep completion message
            #         except Exception as alembic_err:
            #             logger.critical("Alembic downgrade/upgrade failed during demo mode reset!", exc_info=True)
            #             raise RuntimeError("Failed to reset database schema for demo mode.") from alembic_err
            #     else:
            #         logger.info("Attempting Alembic upgrade to head...")
            #         try:
            #             command.upgrade(alembic_cfg, "head")
            #             logger.info("Alembic upgrade to head COMPLETED.")
            #         except Exception as alembic_err:
            #             logger.critical("Alembic upgrade failed! Manual intervention may be required.", exc_info=True)
            #             raise RuntimeError("Failed to upgrade database schema.") from alembic_err
            # else:
            #     logger.info("Database schema is up to date according to Alembic.")

        # Ensure all tables defined in Base metadata exist
        logger.info("Verifying/creating tables based on SQLAlchemy models...")
        is_databricks = settings.DATABASE_TYPE == 'databricks'
        if is_databricks:
            logger.info("Databricks dialect detected. Modifying metadata for DDL generation.")
            indexes_to_remove = []
            for table in Base.metadata.tables.values():
                # Find indexes associated directly with this table via Column(index=True)
                # We check the column's index attribute, not just table.indexes 
                # as table.indexes might include functional indexes etc.
                for col in table.columns:
                    if col.index:
                        # Find the actual Index object SQLAlchemy created for this column
                        # This is a bit involved as Index name isn't guaranteed
                        # Let's try removing ALL indexes associated with the table for simplicity
                        # as UC doesn't support any CREATE INDEX.
                        logger.debug(f"Preparing to remove indexes associated with table: {table.name}")
                        # Collect indexes associated with the table to avoid modifying while iterating
                        for idx in list(table.indexes): # Iterate over a copy
                            if idx not in indexes_to_remove:
                                indexes_to_remove.append(idx)
                                logger.debug(f"Marked index {idx.name} for removal from metadata.")

            # Actually remove them from the metadata's central index collection if necessary
            # In newer SQLAlchemy, removing from table.indexes might be sufficient
            for idx in indexes_to_remove:
                try:
                    # Attempt removal from the table's collection first
                    if hasattr(idx, 'table') and idx in idx.table.indexes:
                        idx.table.indexes.remove(idx)
                    # Attempt removal from metadata collection (less common needed)
                    # if idx in Base.metadata.indexes:
                    #     Base.metadata.indexes.remove(idx)
                    logger.info(f"Successfully removed index {idx.name} from metadata for DDL generation.")
                except Exception as remove_err:
                    logger.warning(f"Could not fully remove index {idx.name} from metadata: {remove_err}")
        # --- End Conditional Metadata Modification --- 

        # Now, call create_all. It will operate on the potentially modified metadata.
        logger.info("Executing Base.metadata.create_all()...")
        Base.metadata.create_all(bind=_engine)
        logger.info("Database tables checked/created by create_all.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}", exc_info=True)
        _engine = None
        _SessionLocal = None
        engine = None # Reset public engine on failure
        raise ConnectionError("Failed to initialize database connection or run migrations.") from e

def get_db():
    global _SessionLocal
    if _SessionLocal is None:
        logger.error("Database not initialized. Cannot get session.")
        raise RuntimeError("Database session factory is not available.")
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_engine():
    global _engine
    if _engine is None:
        raise RuntimeError("Database engine not initialized.")
    return _engine

def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        raise RuntimeError("Database session factory not initialized.")
    return _SessionLocal
