from edu_cloud.ai.registry import ToolSpec


class ToolAccessResolver:
    """三重过滤：RBAC → Module → Capability"""

    async def resolve(
        self,
        all_specs: list[ToolSpec],
        role: str,
        enabled_modules: set[str],
        capabilities: dict[tuple[str, str], bool],
    ) -> list[ToolSpec]:
        result = []
        for spec in all_specs:
            # 层 1: RBAC
            if spec.allowed_roles is not None and role not in spec.allowed_roles:
                continue
            # 层 2: Module
            if spec.module_code and spec.module_code not in enabled_modules:
                continue
            # 层 3: Capability
            if not self._check_capabilities(spec.requires_capabilities, capabilities):
                continue
            result.append(spec)
        return result

    @staticmethod
    def _check_capabilities(
        required: list[tuple[str, str]],
        caps: dict[tuple[str, str], bool],
    ) -> bool:
        for domain, action in required:
            key = (domain, action)
            if key in caps and not caps[key]:
                return False
        return True
