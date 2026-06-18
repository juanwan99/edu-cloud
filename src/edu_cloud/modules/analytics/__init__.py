"""Backward-compatible re-export of the shared effective-score read model.

The canonical implementation now lives in the module-external shared layer
``edu_cloud.services.effective_scores`` so that the cross-module model imports
(``grading`` / ``scan`` / ``exam``) and canonical identity resolution sit in one
shared place instead of inside the ``analytics`` package, lowering analytics
cross-module coupling (D-03F). Every analytics service and the analytics AI
tools keep importing ``get_effective_scores`` / ``get_effective_scores_batch``
through this shim, so existing ``edu_cloud.modules.analytics`` import sites work
unchanged.
"""
from __future__ import annotations

from edu_cloud.services.effective_scores import (  # noqa: F401
    _score_source,
    get_effective_scores,
    get_effective_scores_batch,
)

__all__ = ["get_effective_scores", "get_effective_scores_batch"]
