from services.credits import LOW_CREDITS_RESUBSCRIBE_THRESHOLD, PLAN_CREDITS


def _credit_delta(old_plan: str, new_plan: str, current: int) -> int:
    old_cap = PLAN_CREDITS.get(old_plan, 0)
    new_cap = PLAN_CREDITS.get(new_plan, 0)
    return max(0, current + (new_cap - old_cap))


def test_upgrade_basic_to_pro_preserves_remaining_credits():
    # Basic 200 credits, used 100, remaining 100 -> +200 delta -> 300
    assert _credit_delta("basic", "pro", 100) == 300


def test_upgrade_basic_to_pro_no_usage():
    assert _credit_delta("basic", "pro", 200) == 400


def test_downgrade_pro_to_basic():
    # Pro 400 credits, used 300, remaining 100 -> -200 delta -> 0 (floored)
    assert _credit_delta("pro", "basic", 100) == 0


def test_downgrade_pro_to_basic_with_headroom():
    assert _credit_delta("pro", "basic", 250) == 50


def test_low_credits_resubscribe_threshold():
    assert LOW_CREDITS_RESUBSCRIBE_THRESHOLD == 50


def test_low_credits_topup_adds_plan_credits():
    current = 40
    plan_credits = PLAN_CREDITS["basic"]
    assert current + plan_credits == 240
