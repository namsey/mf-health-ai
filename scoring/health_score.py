def score_returns(r1, r3, r5):
    score = 0

    if r3 is not None:
        if r3 > 50:
            score += 30
        elif r3 > 30:
            score += 20
        else:
            score += 10

    if r1 is not None:
        if r1 > 10:
            score += 10
        elif r1 > 0:
            score += 5

    return score


def score_risk(volatility, drawdown, consistency):
    score = 0

    # Lower volatility = better
    if volatility < 12:
        score += 15
    elif volatility < 16:
        score += 10
    else:
        score += 5

    # Drawdown
    if drawdown > -25:
        score += 15
    elif drawdown > -35:
        score += 10
    else:
        score += 5

    # Consistency
    if consistency > 55:
        score += 15
    elif consistency > 50:
        score += 10
    else:
        score += 5

    return score


def get_fund_status(score):
    if score >= 70:
        return "HEALTHY"
    elif score >= 50:
        return "WATCH"
    else:
        return "REVIEW"