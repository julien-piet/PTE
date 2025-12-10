import os
import json
from typing import Dict, Any, Optional, List

from .configurator import Configurator


class Authenticator:
    """Per-app authenticator that validates tool calls against permission storage.

    On initialization, reads the temporary permission storage produced by
    ApplicationPermissionManager, plus the reverse mapping and API mapping for
    the specified `app_name` only.
    """

    def __init__(self, app_name: str):
        # Determine project root and temporary storage path (keep in sync with PermissionStore)
        current_file = os.path.abspath(__file__)
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(current_file), "..", ".."))
        self.temporary_storage_path = os.path.join(self.project_root, "credentials", "app_permissions_session.json")

        # Loaded state
        self.app_name = app_name
        self.session_token: Optional[str] = None
        self.app_permissions: Dict[str, Any] = {}  # PermissionStore dict for this app
        self.reverse_mapping: Dict[str, str] = {}   # {function_name: method_name}
        self.method_mapping: Dict[str, Any] = {}    # mapping.json content (methods -> scopes)

        # Load temp permissions and per-app mappings on initialization
        self._load_app_mappings()

    # ---------------------------------------------------------------------
    # Loading helpers
    # ---------------------------------------------------------------------
    def _load_temporary_permissions(self):
        """Load session token and application permissions from temp storage."""
        if not os.path.exists(self.temporary_storage_path):
            # Nothing to load; keep empty state
            return

        with open(self.temporary_storage_path, "r") as f:
            data = json.load(f)

        # Support both new structure {session_token, applications} and legacy {app: perms}
        if isinstance(data, dict) and "applications" in data:
            self.session_token = data.get("session_token")
            apps = data.get("applications", {})
        else:
            # Legacy case: no token, direct mapping
            self.session_token = None
            apps = data if isinstance(data, dict) else {}

        # Extract only this app's permissions
        self.app_permissions = apps.get(self.app_name) or {}

    def _load_app_mappings(self):
        """Load reverse mappings and API method mappings for discovered apps."""

        config = Configurator()

        # Load reverse mapping if present
        try:
            rev_path = config.get_app_reverse_mapping_path(self.app_name)
            if os.path.exists(rev_path):
                with open(rev_path, "r") as f:
                    self.reverse_mapping = json.load(f)
        except Exception:
            # Ignore if not found/malformed; verification will handle absence
            print("No reverse mapping found.")
            pass

        # Load API mapping (contains methods -> scopes)
        try:
            map_path = config.get_app_mapping_path(self.app_name)
            if os.path.exists(map_path):
                with open(map_path, "r") as f:
                    self.method_mapping = json.load(f)
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Verification
    # ---------------------------------------------------------------------
    def verify(self, token: str, function_name: str) -> bool:
        """Verify if a given function invocation is permitted.

        Steps:
        - Validate session token matches the one in temporary storage.
        - Resolve the application and method via reverse mapping.
        - Find required scopes for the method from the app mapping.
        - Return True if any required scope is granted (not denied) in temp permissions.

        Args:
            token: Session token to validate.
            function_name: Function/tool name. Supports formats:
                - "app:function" (preferred)
                - "function" (will search across apps with loaded reverse mappings)

        Returns:
            True if call allowed, False otherwise.
        """

        self._load_temporary_permissions()

        # 1) Token check
        if self.session_token and token != self.session_token:
            print("Mismatch token.")
            return False

        # 2) Determine original function name and ensure any prefix matches app
        func = function_name
        if ":" in function_name:
            app, fname = function_name.split(":", 1)
            if app != self.app_name:
                return False
            func = fname

        # 3) Map function -> method via reverse mapping
        method_name = None
        rev = self.reverse_mapping or {}
        method_name = rev.get(func)
        if not method_name:
            # If no explicit reverse mapping, assume function_name already equals method name
            # after stripping any app prefix.
            method_name = func

        # 4) Fetch required scopes for this method
        required_scopes = self._get_method_required_scopes(method_name)
        if not required_scopes:
            # If we cannot determine scopes, be conservative and deny
            return False
    

        # 5) Check permissions for any acceptable scope
        perm_obj = self.app_permissions
        if not perm_obj:
            return False
        scope_permissions: Dict[str, str] = (perm_obj.get("scope_permissions")
                                             if isinstance(perm_obj, dict)
                                             else {})
        # Allowed if any candidate scope is set to a non-denied state
        for scope in required_scopes:
            state = scope_permissions.get(scope)
            if state and state.lower() != "denied":
                return True
        return False

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _get_method_required_scopes(self, method_name: str) -> List[str]:
        """Return a flat list of acceptable scopes for a method.

        Mapping files store scopes as a list of alternatives, e.g. [["scope:a"], ["scope:b"]].
        We treat any listed scope as sufficient for permission.
        """
        mapping = self.method_mapping or {}
        methods = mapping.get("methods", {})
        method_info = methods.get(method_name)
        if not method_info:
            return []
        scopes = method_info.get("scopes", [])
        flat: List[str] = []
        for alt in scopes:
            # Each alt may be a list of scopes; many mappings use single-scope lists
            if isinstance(alt, list):
                if alt:
                    flat.append(alt[0])
            elif isinstance(alt, str):
                flat.append(alt)
        return flat
    
