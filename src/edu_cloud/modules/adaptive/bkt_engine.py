from dataclasses import dataclass


@dataclass(frozen=True)
class BktParams:
    """BKT 四参数"""
    p_init: float = 0.1    # P(L₀) 初始掌握概率
    p_transit: float = 0.2  # P(T) 学习转移概率
    p_guess: float = 0.25   # P(G) 猜测概率
    p_slip: float = 0.1     # P(S) 失误概率


DEFAULT_PARAMS = BktParams()


def bkt_update(mastery: float, is_correct: bool, params: BktParams = DEFAULT_PARAMS) -> float:
    """BKT 单次作答后更新掌握概率。

    标准 BKT 两步：
    1. 后验更新（基于作答结果）
    2. 学习转移（未掌握的部分有概率转为掌握）
    """
    p_l = mastery
    p_g = params.p_guess
    p_s = params.p_slip
    p_t = params.p_transit

    # Step 1: 后验更新
    if is_correct:
        numerator = p_l * (1.0 - p_s)
        denominator = p_l * (1.0 - p_s) + (1.0 - p_l) * p_g
    else:
        numerator = p_l * p_s
        denominator = p_l * p_s + (1.0 - p_l) * (1.0 - p_g)

    if denominator == 0:
        p_posterior = p_l
    else:
        p_posterior = numerator / denominator

    # Step 2: 学习转移
    p_new = p_posterior + (1.0 - p_posterior) * p_t

    return max(0.0, min(1.0, p_new))


def classify_da_state(mastery: float, attempts: int) -> str:
    """将 DA 掌握度分为 4 态"""
    if attempts == 0:
        return "unseen"
    if mastery < 0.5:
        return "weak"
    if mastery < 0.8:
        return "fragile"
    return "solid"
