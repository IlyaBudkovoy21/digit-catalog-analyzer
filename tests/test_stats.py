from app.services.stats import count_digit_stats, empty_digit_stats, merge_digit_stats


def test_count_digit_stats_returns_all_digits() -> None:
    stats = count_digit_stats("0012399\n")

    assert stats == {
        "0": 2,
        "1": 1,
        "2": 1,
        "3": 1,
        "4": 0,
        "5": 0,
        "6": 0,
        "7": 0,
        "8": 0,
        "9": 2,
    }


def test_merge_digit_stats() -> None:
    first = empty_digit_stats()
    second = empty_digit_stats()
    first["7"] = 3
    second["7"] = 4
    second["9"] = 2

    assert merge_digit_stats([first, second])["7"] == 7
    assert merge_digit_stats([first, second])["9"] == 2
