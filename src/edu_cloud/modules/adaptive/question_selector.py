BAND_ORDER = ["near", "mid", "far"]


def select_transfer_band(state: str) -> str:
    """根据 DA 状态选择目标迁移带"""
    if state in ("unseen", "weak"):
        return "near"
    if state == "fragile":
        return "mid"
    return "far"


def filter_candidates(
    items: list[dict],
    target_band: str,
    limit: int = 5,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    """从候选题中筛选目标迁移带的题目。

    如果目标 band 无题，降级到相邻 band。
    """
    exclude = exclude_ids or set()

    target_idx = BAND_ORDER.index(target_band) if target_band in BAND_ORDER else 1
    band_priority = [target_band]
    for offset in [1, -1, 2, -2]:
        idx = target_idx + offset
        if 0 <= idx < len(BAND_ORDER) and BAND_ORDER[idx] not in band_priority:
            band_priority.append(BAND_ORDER[idx])

    result = []
    for band in band_priority:
        for item in items:
            if item["id"] in exclude:
                continue
            if item.get("transfer_band") == band:
                result.append(item)
                if len(result) >= limit:
                    return result

    return result
