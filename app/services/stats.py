from collections import Counter


DIGITS = tuple(str(number) for number in range(10))


def empty_digit_stats() -> dict[str, int]:
    return {digit: 0 for digit in DIGITS}


def count_digit_stats(content: str) -> dict[str, int]:
    counter = Counter(char for char in content.strip() if char in DIGITS)
    return {digit: counter.get(digit, 0) for digit in DIGITS}


def merge_digit_stats(items: list[dict[str, int]]) -> dict[str, int]:
    result = empty_digit_stats()
    for item in items:
        for digit in DIGITS:
            result[digit] += int(item.get(digit, 0))
    return result
