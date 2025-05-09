from typing import List, Type
from api.common.search_interfaces import SearchableAsset
import logging

logger = logging.getLogger(__name__)

# Global registry for searchable asset manager classes
SEARCHABLE_ASSET_MANAGERS: List[Type[SearchableAsset]] = []

def searchable_asset(cls: Type[SearchableAsset]):
    """
    Class decorator to register classes that implement the SearchableAsset interface.
    """
    if not issubclass(cls, SearchableAsset):
        raise TypeError(f"Class {cls.__name__} must inherit from SearchableAsset to be registered.")
    
    if cls not in SEARCHABLE_ASSET_MANAGERS:
        logger.info(f"Registering searchable asset manager: {cls.__name__}")
        SEARCHABLE_ASSET_MANAGERS.append(cls)
    else:
        logger.warning(f"Searchable asset manager {cls.__name__} is already registered.")
        
    return cls 