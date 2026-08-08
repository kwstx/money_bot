import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SecurityContext:
    """
    Defines security boundaries for the platform.
    Isolates credentials, signing systems, user data, and execution permissions from research components.
    """
    def __init__(self):
        # In a real system, these would be KMS references or Vault tokens
        self._signing_keys_accessible = False
        self._user_data_accessible = False
        
    def assert_execution_permission(self, workflow_name: str) -> None:
        """Only specific, highly trusted workflows (like automated execution) can access signing keys."""
        if workflow_name != "Execution":
            raise PermissionError(f"Workflow '{workflow_name}' is not permitted to access execution boundaries.")
            
    def get_safe_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Strips PII or sensitive keys before passing to generic ML models."""
        safe_copy = raw_metadata.copy()
        safe_copy.pop("ip_address", None)
        safe_copy.pop("auth_token", None)
        return safe_copy

security_context = SecurityContext()
