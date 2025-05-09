import json
from typing import Dict, List, Optional
from collections import defaultdict

from api.controller.settings_manager import SettingsManager
from api.models.settings import AppRole
from api.common.features import FeatureAccessLevel, ACCESS_LEVEL_ORDER, get_feature_config
from api.common.logging import get_logger

logger = get_logger(__name__)

class AuthorizationManager:
    def __init__(self, settings_manager: SettingsManager):
        """Requires SettingsManager to access role configurations."""
        self._settings_manager = settings_manager

    def get_user_effective_permissions(self, user_groups: Optional[List[str]]) -> Dict[str, FeatureAccessLevel]:
        """
        Calculates the effective permission level for each feature based on the user's groups.
        Permissions are merged by taking the highest level granted by any matching role.

        Args:
            user_groups: A list of group names the user belongs to.

        Returns:
            A dictionary mapping feature IDs to the highest granted FeatureAccessLevel.
        """
        if not user_groups:
            user_groups = []
            logger.warning("Received empty or None user_groups for permission calculation.") # Log if groups are empty
        else:
            logger.info(f"Calculating effective permissions for user groups: {user_groups}") # Log received groups

        user_group_set = set(user_groups)
        effective_permissions: Dict[str, FeatureAccessLevel] = defaultdict(lambda: FeatureAccessLevel.NONE)
        
        # Log before fetching roles
        logger.info("Fetching all application roles from SettingsManager...")
        all_roles = self._settings_manager.list_app_roles() # Fetches roles from DB via SettingsManager
        logger.info(f"Fetched {len(all_roles)} roles total.")
        # Log details of fetched roles (optional, can be verbose)
        # for role in all_roles:
        #     logger.debug(f"  Role '{role.name}' (ID: {role.id}) - Assigned Groups: {role.assigned_groups}, Permissions: {role.feature_permissions}")
            
        feature_config = get_feature_config()

        matching_roles = []
        logger.info("Identifying matching roles based on group intersection...")
        for role in all_roles:
            role_assigned_groups_set = set(role.assigned_groups or []) # Ensure it's a set, handle None
            # Check for intersection
            if user_group_set.intersection(role_assigned_groups_set):
                matching_roles.append(role)
                logger.info(f"  MATCH FOUND: User group(s) {list(user_group_set.intersection(role_assigned_groups_set))} match role: '{role.name}' (Assigned: {role.assigned_groups})")
            # else: 
            #    logger.debug(f"  NO MATCH: User groups {list(user_group_set)} vs Role '{role.name}' groups {list(role_assigned_groups_set)}")

        if not matching_roles:
            logger.warning(f"No matching roles found for user groups: {user_groups}. Returning NONE access for all features.")
            return {feat_id: FeatureAccessLevel.NONE for feat_id in feature_config}

        logger.info(f"Merging permissions from {len(matching_roles)} matching roles...")
        # Merge permissions from matching roles
        for role in matching_roles:
            logger.debug(f"Processing permissions from role: '{role.name}'")
            for feature_id, assigned_level in role.feature_permissions.items():
                if feature_id not in feature_config:
                    logger.warning(f"Role '{role.name}' contains permission for unknown feature ID '{feature_id}'. Skipping.")
                    continue

                current_effective_level = effective_permissions[feature_id]
                # Compare levels using the defined order
                if ACCESS_LEVEL_ORDER[assigned_level] > ACCESS_LEVEL_ORDER[current_effective_level]:
                    effective_permissions[feature_id] = assigned_level
                    logger.debug(f"  Updated effective permission for '{feature_id}' to '{assigned_level.value}' (was '{current_effective_level.value}') from role '{role.name}'")
                # else:
                #    logger.debug(f"  Keeping existing permission for '{feature_id}' ('{current_effective_level.value}') - Role '{role.name}' level ('{assigned_level.value}') is not higher.")

        # Ensure all features have at least NONE permission defined
        for feature_id in feature_config:
            if feature_id not in effective_permissions:
                effective_permissions[feature_id] = FeatureAccessLevel.NONE

        # Log the final permissions
        final_perms_str = {k: v.value for k, v in effective_permissions.items()}
        logger.info(f"Final calculated effective permissions: {final_perms_str}")
        return dict(effective_permissions)

    def has_permission(self, effective_permissions: Dict[str, FeatureAccessLevel], feature_id: str, required_level: FeatureAccessLevel) -> bool:
        """
        Checks if the user's effective permissions meet the required level for a specific feature.

        Args:
            effective_permissions: The user's calculated effective permissions.
            feature_id: The ID of the feature to check.
            required_level: The minimum FeatureAccessLevel required.

        Returns:
            True if the user has sufficient permission, False otherwise.
        """
        user_level = effective_permissions.get(feature_id, FeatureAccessLevel.NONE)
        has_perm = ACCESS_LEVEL_ORDER[user_level] >= ACCESS_LEVEL_ORDER[required_level]
        logger.debug(f"Permission check for feature '{feature_id}': Required='{required_level.value}', User has='{user_level.value}'. Granted: {has_perm}")
        return has_perm 