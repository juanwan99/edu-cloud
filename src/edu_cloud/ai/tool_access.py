"""Three-layer tool permission filtering (Design §4)."""
from __future__ import annotations

from edu_cloud.ai.registry import ToolSpec


class ToolAccessResolver:
    """三重过滤：RBAC → Module → Capability"""

    def resolve(
        self,
        all_specs: list[ToolSpec],
        role: str,
        enabled_modules: set[str] | None,
        capabilities: dict[tuple[str, str], bool],
    ) -> list[ToolSpec]:
        result = []
        for spec in all_specs:
            # Layer 1: RBAC
            if spec.allowed_roles is not None and role not in spec.allowed_roles:
                continue
            # Layer 2: Module switch (enabled_modules=None → 不过滤，platform_admin 无 school_id 时)
            if enabled_modules is not None and spec.module_code is not None:
                if spec.module_code not in enabled_modules:
                    continue
            # Layer 3: Capability matrix
            if not self._check_capabilities(spec.requires_capabilities, capabilities):
                continue
            result.append(spec)
        return result

    @staticmethod
    def _check_capabilities(
        required: list[tuple[str, str]],
        caps: dict[tuple[str, str], bool],
    ) -> bool:
        # INV-002: "无记录默认允许" — 只有显式 False 才拒绝
        for req in required:
            if req in caps and not caps[req]:
                return False
        return True
