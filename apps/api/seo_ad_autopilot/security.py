"""Security sandbox for safe execution.

Inspired by OpenClaw's security model:
- Permission-based access control
- Execution limits
- Audit logging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Permission(str, Enum):
    """Permission types."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DEPLOY = "deploy"
    DELETE = "delete"


class RiskLevel(str, Enum):
    """Risk levels for operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityPolicy:
    """Security policy configuration."""
    max_execution_time: int = 300  # seconds
    max_memory_mb: int = 512
    allowed_permissions: list[Permission] = field(default_factory=list)
    blocked_domains: list[str] = field(default_factory=list)
    require_approval_for: list[str] = field(default_factory=list)


@dataclass
class AuditEntry:
    """Audit log entry."""
    timestamp: datetime
    action: str
    target: str
    user: str
    risk_level: RiskLevel
    allowed: bool
    details: dict[str, Any] = field(default_factory=dict)


class SecuritySandbox:
    """Security sandbox for safe execution."""
    
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self._policy = policy or SecurityPolicy()
        self._audit_log: list[AuditEntry] = []
        self._permissions: dict[str, list[Permission]] = {}
    
    def check_permission(self, user: str, permission: Permission) -> bool:
        """Check if user has permission."""
        user_perms = self._permissions.get(user, [])
        return permission in user_perms
    
    def grant_permission(self, user: str, permission: Permission) -> None:
        """Grant permission to user."""
        if user not in self._permissions:
            self._permissions[user] = []
        if permission not in self._permissions[user]:
            self._permissions[user].append(permission)
    
    def revoke_permission(self, user: str, permission: Permission) -> None:
        """Revoke permission from user."""
        if user in self._permissions:
            self._permissions[user] = [
                p for p in self._permissions[user] if p != permission
            ]
    
    def validate_operation(
        self,
        user: str,
        action: str,
        target: str,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> bool:
        """Validate if an operation is allowed."""
        # Check if action requires approval
        if action in self._policy.require_approval_for:
            self._log_audit(user, action, target, risk_level, False)
            return False
        
        # Check blocked domains
        for domain in self._policy.blocked_domains:
            if domain in target:
                self._log_audit(user, action, target, risk_level, False)
                return False
        
        # Log and allow
        self._log_audit(user, action, target, risk_level, True)
        return True
    
    def _log_audit(
        self,
        user: str,
        action: str,
        target: str,
        risk_level: RiskLevel,
        allowed: bool,
    ) -> None:
        """Log audit entry."""
        entry = AuditEntry(
            timestamp=datetime.now(),
            action=action,
            target=target,
            user=user,
            risk_level=risk_level,
            allowed=allowed,
        )
        self._audit_log.append(entry)
    
    def get_audit_log(
        self,
        user: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get audit log entries."""
        entries = self._audit_log
        if user:
            entries = [e for e in entries if e.user == user]
        return entries[-limit:]
    
    def get_security_summary(self) -> dict[str, Any]:
        """Get security summary."""
        return {
            "total_operations": len(self._audit_log),
            "allowed_operations": sum(1 for e in self._audit_log if e.allowed),
            "denied_operations": sum(1 for e in self._audit_log if not e.allowed),
            "high_risk_operations": sum(
                1 for e in self._audit_log
                if e.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            ),
            "users_with_permissions": len(self._permissions),
        }


def create_default_sandbox() -> SecuritySandbox:
    """Create a sandbox with default policy."""
    policy = SecurityPolicy(
        max_execution_time=300,
        max_memory_mb=512,
        allowed_permissions=[Permission.READ, Permission.EXECUTE],
        blocked_domains=["malware.com", "phishing.com"],
        require_approval_for=["deploy", "delete"],
    )
    
    sandbox = SecuritySandbox(policy)
    
    # Grant default permissions
    sandbox.grant_permission("system", Permission.READ)
    sandbox.grant_permission("system", Permission.WRITE)
    sandbox.grant_permission("system", Permission.EXECUTE)
    sandbox.grant_permission("admin", Permission.DEPLOY)
    sandbox.grant_permission("admin", Permission.DELETE)
    
    return sandbox
