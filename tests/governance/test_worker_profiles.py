from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.governance import gen_worker_profile as profiles


REPO = Path(__file__).resolve().parents[2]


def _module_dir(repo: Path, name: str) -> Path:
    return repo / "src" / "edu_cloud" / "modules" / name


def _add_module(repo: Path, name: str) -> None:
    module_dir = _module_dir(repo, name)
    module_dir.mkdir(parents=True)
    (module_dir / "MODULE.md").write_text(f"---\nname: {name}\n---\n# {name}\n", encoding="utf-8")


def _load_profile(module: str) -> dict:
    path = REPO / "control" / "steward" / "worker-profiles" / "modules" / f"{module}.settings.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest() -> dict:
    path = REPO / "control" / "steward" / "worker-profiles" / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_generated_profiles_are_current_for_repo():
    assert profiles.check_profiles(REPO) == []


def test_every_repo_module_has_profile_and_manifest_entry():
    modules = profiles.discover_modules(REPO)
    module_names = [module.name for module in modules]

    manifest = _load_manifest()

    assert manifest["moduleCount"] == len(module_names)
    assert [item["name"] for item in manifest["modules"]] == module_names
    assert all(
        item["settingsPath"].endswith(f"{item['name']}.settings.json")
        for item in manifest["modules"]
    )
    for module in module_names:
        profile_path = (
            REPO
            / "control"
            / "steward"
            / "worker-profiles"
            / "modules"
            / f"{module}.settings.json"
        )
        assert profile_path.exists(), module


def test_added_module_directory_makes_generation_check_fail(tmp_path: Path):
    _add_module(tmp_path, "alpha")
    _add_module(tmp_path, "beta")
    profiles.write_profiles(tmp_path)

    assert profiles.check_profiles(tmp_path) == []

    _add_module(tmp_path, "gamma")

    errors = profiles.check_profiles(tmp_path)
    assert any("manifest.json" in error for error in errors)
    assert any("gamma.settings.json" in error for error in errors)


def test_deleted_module_directory_makes_generation_check_fail(tmp_path: Path):
    _add_module(tmp_path, "alpha")
    _add_module(tmp_path, "beta")
    profiles.write_profiles(tmp_path)

    shutil.rmtree(_module_dir(tmp_path, "beta"))

    errors = profiles.check_profiles(tmp_path)
    assert any("manifest.json" in error for error in errors)
    assert any("beta.settings.json" in error for error in errors)


def test_each_profile_denies_every_sibling_module_write():
    modules = [module.name for module in profiles.discover_modules(REPO)]

    for module in modules:
        deny = set(_load_profile(module)["permissions"]["deny"])
        for sibling in modules:
            if sibling == module:
                continue
            sibling_path = f"src/edu_cloud/modules/{sibling}/**"
            assert f"Edit({sibling_path})" in deny
            assert f"Write({sibling_path})" in deny


def test_profiles_forbid_shell_bypass_self_modify_and_central_paths():
    module = profiles.discover_modules(REPO)[0].name
    profile = _load_profile(module)
    manifest = _load_manifest()
    permissions = profile["permissions"]
    deny = set(permissions["deny"])

    assert permissions["defaultMode"] == "dontAsk"
    assert permissions["disableBypassPermissionsMode"] == "disable"
    assert "Bash" in deny
    assert "PowerShell" in deny
    assert "Edit(.claude/**)" in deny
    assert "Write(.claude/**)" in deny
    assert "Edit(src/edu_cloud/ai/**)" in deny
    assert "Write(src/edu_cloud/core/**)" in deny
    assert "Edit(src/edu_cloud/api/router_registry.py)" in deny
    assert "Write(src/edu_cloud/api/app.py)" in deny
    assert "Edit(src/edu_cloud/models/school_settings.py)" in deny
    assert "Write(alembic/**)" in deny
    assert "Edit(.github/**)" in deny
    assert "Write(control/**)" in deny
    assert "Edit(deploy/**)" in deny
    assert "--permission-mode" in manifest["startup"]["forbiddenFlags"]
    assert "--dangerously-skip-permissions" in manifest["startup"]["forbiddenFlags"]
    assert manifest["workerContract"]["noShell"] is True
    assert manifest["workerContract"]["mayRunShell"] is False
    assert manifest["workerContract"]["mayRunTests"] is False
    assert manifest["workerContract"]["mayRunGit"] is False


def test_allowed_tools_do_not_include_sibling_modules():
    modules = [module.name for module in profiles.discover_modules(REPO)]

    for module in modules:
        allow = _load_profile(module)["permissions"]["allow"]
        assert allow[0] == "Read(**)"
        assert all("Bash" not in item and "PowerShell" not in item for item in allow)
        for sibling in modules:
            if sibling == module:
                continue
            sibling_path = f"src/edu_cloud/modules/{sibling}/**"
            assert all(sibling_path not in item for item in allow)
