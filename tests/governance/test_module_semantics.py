from pathlib import Path
import copy
import pytest
from scripts.governance import check_module_semantics as cms

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def truth():
    return cms.load_truth(REPO / "docs/governance/module-semantics.yaml")


def test_self_consistency_passes_on_real_truth(truth):
    assert cms.check_self_consistency(truth, REPO) == []


def test_layer1_mismatch_with_module_codes_fails(truth):  # 反例 #8
    bad = copy.deepcopy(truth)
    bad["school_module_codes"].append("ghost_module")
    errs = cms.check_self_consistency(bad, REPO)
    assert any("school_module_codes" in e for e in errs)


def test_layer2_missing_arch_module_fails(truth):  # 反例 #9
    bad = copy.deepcopy(truth)
    del bad["architecture_to_module_code"]["scan"]
    errs = cms.check_self_consistency(bad, REPO)
    assert any("architecture_to_module_code" in e and "scan" in e for e in errs)
