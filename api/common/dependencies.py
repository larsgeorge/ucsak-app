from typing import Optional, Annotated
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

# Import manager classes needed for Annotated types
from api.controller.settings_manager import SettingsManager
from api.controller.audit_manager import AuditManager
from api.controller.authorization_manager import AuthorizationManager # Needed for PermissionCheckerDep
from api.controller.users_manager import UsersManager # Needed for CurrentUserDep
# Import DataAssetReviewManager for Annotated type
from api.controller.data_asset_reviews_manager import DataAssetReviewManager
from api.controller.notifications_manager import NotificationsManager # Added
from api.controller.data_products_manager import DataProductsManager # Added for DataProductsManagerDep
from api.controller.data_domains_manager import DataDomainManager # Add import
from databricks.sdk import WorkspaceClient # Added for WorkspaceClientDep
# Import other managers
from api.controller.data_contracts_manager import DataContractsManager
from api.controller.business_glossaries_manager import BusinessGlossariesManager
from api.controller.search_manager import SearchManager

# Import base dependencies
from api.common.database import get_session_factory # Import the factory function
from api.common.config import Settings
from api.models.users import UserInfo # Corrected import to UserInfo
from api.common.features import FeatureAccessLevel
from api.common.logging import get_logger

# Import the PermissionChecker class directly for use in require_permission
from api.common.authorization import PermissionChecker, get_user_details_from_sdk # Import checker and user getter
# Import manager getters from the new file
from api.common.manager_dependencies import (
    get_auth_manager, 
    get_settings_manager, 
    get_audit_manager, 
    get_users_manager,
    get_data_asset_review_manager,
    get_notifications_manager, # Added
    get_data_products_manager, # Added
    get_data_domain_manager, # Add import
    # Add imports for new getters
    get_data_contracts_manager,
    get_business_glossaries_manager,
    get_search_manager,
)
# Import workspace client getter separately as it might be structured differently
from api.common.workspace_client import get_workspace_client # Added

logger = get_logger(__name__)

# --- Core Dependency Functions --- #

# Database Session Dependency Provider (Function)
def get_db():
    session_factory = get_session_factory() # Get the factory
    if not session_factory:
        # This should ideally not happen if init_db ran successfully
        logger.critical("Database session factory not initialized!")
        raise HTTPException(status_code=503, detail="Database session factory not available.")
    
    db = session_factory() # Create a session instance from the factory
    try:
        yield db
    finally:
        db.close()

# Settings Dependency Provider (Function)
def get_settings(request: Request) -> Settings:
    # Assuming settings are loaded into app.state during startup
    settings = getattr(request.app.state, 'settings', None)
    if settings is None:
        logger.critical("Settings not found in application state!")
        # Depending on recovery strategy, you might load defaults or raise a critical error
        raise HTTPException(status_code=503, detail="Application settings not available.")
    return settings

# Current User Dependency Provider (Function)
# This relies on the actual implementation of get_user_details_from_sdk
async def get_current_user(user_details: UserInfo = Depends(get_user_details_from_sdk)) -> UserInfo:
    """Dependency to get the currently authenticated user's details."""
    # get_user_details_from_sdk handles fetching or mocking user details
    # We might want to adapt the User model or UserInfo based on what get_user_details_from_sdk returns
    # For now, assuming it returns a compatible UserInfo object or can be adapted.
    if not user_details:
        # This case should ideally be handled within get_user_details_from_sdk by raising HTTPException
        logger.error("get_user_details_from_sdk returned None, but should have raised HTTPException.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve user information.")
    return user_details # Return the user object obtained from the underlying function


# --- Annotated Dependency Types --- #

DBSessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUserDep = Annotated[UserInfo, Depends(get_current_user)]
WorkspaceClientDep = Annotated[WorkspaceClient, Depends(get_workspace_client)]

# Manager Dependencies (using Annotated types that resolve via manager_dependencies.py)
# These rely on the functions defined in manager_dependencies.py
SettingsManagerDep = Annotated[SettingsManager, Depends(get_settings_manager)]
AuditManagerDep = Annotated[AuditManager, Depends(get_audit_manager)]
UsersManagerDep = Annotated[UsersManager, Depends(get_users_manager)]
AuthorizationManagerDep = Annotated[AuthorizationManager, Depends(get_auth_manager)]

# Add DataAssetReviewManagerDep
DataAssetReviewManagerDep = Annotated[DataAssetReviewManager, Depends(get_data_asset_review_manager)]

# Add NotificationsManagerDep
NotificationsManagerDep = Annotated[NotificationsManager, Depends(get_notifications_manager)]

# Add DataProductsManagerDep
DataProductsManagerDep = Annotated[DataProductsManager, Depends(get_data_products_manager)]

# Add DataDomainManagerDep
DataDomainManagerDep = Annotated[DataDomainManager, Depends(get_data_domain_manager)]

# Add other Manager Annotated Types
DataContractsManagerDep = Annotated[DataContractsManager, Depends(get_data_contracts_manager)]
BusinessGlossariesManagerDep = Annotated[BusinessGlossariesManager, Depends(get_business_glossaries_manager)]
SearchManagerDep = Annotated[SearchManager, Depends(get_search_manager)]

# Permission Checker Dependency (Relies on AuthorizationManager)
# This Dep provides the AuthorizationManager needed by PermissionChecker('feature', level)
PermissionCheckerDep = AuthorizationManagerDep 
# Alternatively: PermissionCheckerDep = Annotated[AuthorizationManager, Depends(get_auth_manager)] 

# --- Permission Checking Function --- #

async def require_permission(
    feature: str, # Changed type hint to str
    level: FeatureAccessLevel,
    user: CurrentUserDep, # Use Annotated type (UserInfo)
    auth_manager: AuthorizationManagerDep # Depend on the Auth Manager
):
    """
    FastAPI Dependency function to check if the current user has the required permission level
    for a given feature string ID using the AuthorizationManager.
    """
    # The PermissionChecker class itself is used directly in routes like Depends(PermissionChecker(...))
    # This function provides a simpler way if complex instantiation isn't needed.
    logger.debug(f"Checking permission via require_permission for feature '{feature}' (level: {level.value}) for user '{user.username}'")

    if not user.groups:
        logger.warning(f"User '{user.username}' has no groups. Denying access for '{feature}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no assigned groups, cannot determine permissions."
        )

    try:
        # Use the injected AuthorizationManager directly
        effective_permissions = auth_manager.get_user_effective_permissions(user.groups)
        has_required_permission = auth_manager.has_permission(
            effective_permissions,
            feature, # Use feature string ID directly
            level
        )

        if not has_required_permission:
            user_level = effective_permissions.get(feature, FeatureAccessLevel.NONE)
            logger.warning(
                f"Permission denied via require_permission for user '{user.username}' "
                f"on feature '{feature}'. Required: '{level.value}', Found: '{user_level.value}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for feature '{feature}'. Required level: {level.value}."
            )

        logger.debug(f"Permission granted via require_permission for user '{user.username}' on feature '{feature}'")
        # If permission is granted, the dependency resolves successfully
        return # Success

    except HTTPException:
        raise # Re-raise exceptions from dependencies
    except Exception as e:
        logger.error(f"Unexpected error during permission check (require_permission) for feature '{feature}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking user permissions."
        )

# --- Other Manager Annotated Types (Add as needed) --- #
# Example:
# from api.controller.data_products_manager import DataProductsManager
# from api.common.manager_dependencies import get_data_products_manager
# DataProductsManagerDep = Annotated[DataProductsManager, Depends(get_data_products_manager)]