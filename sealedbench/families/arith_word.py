"""GSM8K-style word problems with a parameter oracle.

Every template is 2 to 5 integer arithmetic steps. The oracle is a pure
function of `params`. The prompt does not contain the answer line. Sampling
is constructive, so a candidate is rejected only when a duplicate prompt
appears or a constraint cannot be met.
"""

from __future__ import annotations

from sealedbench.items import Item
from sealedbench.rng import RNG

NAMES = [
    "Ava", "Ben", "Cara", "Diego", "Elena", "Farid", "Gina", "Hugo",
    "Ivy", "Jamal", "Kira", "Leo", "Mina", "Nico", "Olga", "Pavel",
    "Quinn", "Rosa", "Samir", "Tara", "Uma", "Victor", "Willa", "Xavier",
    "Yara", "Zane", "Aisha", "Boris", "Chloe", "Dmitri", "Esme", "Felix",
]

THINGS = [
    ("apples", "apple"),
    ("pencils", "pencil"),
    ("stickers", "sticker"),
    ("marbles", "marble"),
    ("cards", "card"),
    ("erasers", "eraser"),
    ("cookies", "cookie"),
    ("buttons", "button"),
    ("ribbons", "ribbon"),
    ("tokens", "token"),
    ("stamps", "stamp"),
    ("beads", "bead"),
    ("tickets", "ticket"),
    ("notebooks", "notebook"),
    ("muffins", "muffin"),
    ("oranges", "orange"),
    ("balloons", "balloon"),
    ("crayons", "crayon"),
    ("magnets", "magnet"),
    ("badges", "badge"),
]


def _qty(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _two_names(rng: RNG) -> tuple[str, str]:
    first = rng.choice(NAMES)
    second = rng.choice([name for name in NAMES if name != first])
    return first, second


def _thing(rng: RNG) -> tuple[str, str]:
    return rng.choice(THINGS)


def _positive(value: int) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def steps_of(params: dict) -> int:
    template = params["template"]
    table = {
        "buy_give": 2,
        "buy_receive": 2,
        "buy_give_receive": 3,
        "two_buys": 3,
        "buy_give_price": 3,
        "buy_give_receive_price": 4,
        "two_buys_give": 4,
        "two_buys_give_price": 5,
        "buy_give_share": 3,
        "two_buys_share": 4,
        "two_buys_give_share": 5,
        "one_day_spend": 2,
        "two_days": 3,
        "two_days_spend": 4,
        "three_days": 5,
        "days_plus": 2,
        "days_plus_skip": 3,
        "two_books": 3,
        "two_books_skip": 4,
        "two_books_weeks": 5,
        "rows_left": 2,
        "rows_price": 3,
        "two_sections": 3,
        "two_sections_sold": 4,
        "two_sections_price": 5,
    }
    if template not in table:
        raise ValueError(template)
    return table[template]


def answer_of(params: dict) -> int | None:
    t = params["template"]
    try:
        if t == "buy_give":
            value = params["packs"] * params["per"] - params["give"]
        elif t == "buy_receive":
            value = params["packs"] * params["per"] + params["receive"]
        elif t == "buy_give_receive":
            value = params["packs"] * params["per"] - params["give"] + params["receive"]
        elif t == "two_buys":
            value = params["packs"] * params["per"] + params["packs2"] * params["per2"]
        elif t == "buy_give_price":
            value = (params["packs"] * params["per"] - params["give"]) * params["price"]
        elif t == "buy_give_receive_price":
            value = (params["packs"] * params["per"] - params["give"] + params["receive"]) * params["price"]
        elif t == "two_buys_give":
            value = params["packs"] * params["per"] + params["packs2"] * params["per2"] - params["give"]
        elif t == "two_buys_give_price":
            value = (params["packs"] * params["per"] + params["packs2"] * params["per2"] - params["give"]) * params["price"]
        elif t == "buy_give_share":
            left = params["packs"] * params["per"] - params["give"]
            if left % params["share"] != 0:
                return None
            value = left // params["share"]
        elif t == "two_buys_share":
            left = params["packs"] * params["per"] + params["packs2"] * params["per2"]
            if left % params["share"] != 0:
                return None
            value = left // params["share"]
        elif t == "two_buys_give_share":
            left = params["packs"] * params["per"] + params["packs2"] * params["per2"] - params["give"]
            if left % params["share"] != 0:
                return None
            value = left // params["share"]
        elif t == "one_day_spend":
            value = params["rate"] * params["hours"] - params["spend"]
        elif t == "two_days":
            value = params["rate"] * (params["hours"][0] + params["hours"][1])
        elif t == "two_days_spend":
            value = params["rate"] * (params["hours"][0] + params["hours"][1]) - params["spend"]
        elif t == "three_days":
            value = params["rate"] * sum(params["hours"])
        elif t == "days_plus":
            value = params["per_day"] * params["days"] + params["extra"]
        elif t == "days_plus_skip":
            value = params["per_day"] * params["days"] + params["extra"] - params["skip"]
        elif t == "two_books":
            value = params["per_day"] * params["days"] + params["per_day2"] * params["days2"]
        elif t == "two_books_skip":
            value = params["per_day"] * params["days"] + params["per_day2"] * params["days2"] - params["skip"]
        elif t == "two_books_weeks":
            value = (params["per_day"] * params["days"] + params["per_day2"] * params["days2"] - params["skip"]) * params["weeks"]
        elif t == "rows_left":
            value = params["rows"] * params["seats"] - params["sold"]
        elif t == "rows_price":
            value = (params["rows"] * params["seats"] - params["sold"]) * params["price"]
        elif t == "two_sections":
            value = params["rows"] * params["seats"] + params["rows2"] * params["seats2"]
        elif t == "two_sections_sold":
            value = params["rows"] * params["seats"] + params["rows2"] * params["seats2"] - params["sold"]
        elif t == "two_sections_price":
            value = (params["rows"] * params["seats"] + params["rows2"] * params["seats2"] - params["sold"]) * params["price"]
        else:
            return None
    except (KeyError, TypeError, ZeroDivisionError):
        return None
    return _positive(value)


def _buy(name: str, packs: int, per: int, plural: str) -> str:
    return (
        f"{name} buys {_qty(packs, 'pack', 'packs')} of {plural}. "
        f"Each pack contains {_qty(per, plural, plural)}."
    )


def render(params: dict) -> str:
    t = params["template"]
    name = params["name"]
    if t.startswith("buy") or t.startswith("two_buys"):
        plural = params["plural"]
        singular = params["singular"]
        friend = params.get("friend", "")
        parts = [_buy(name, params["packs"], params["per"], plural)]
        if "packs2" in params:
            parts.append(
                f"Then {name} buys {_qty(params['packs2'], 'pack', 'packs')} with "
                f"{_qty(params['per2'], plural, plural)} in each pack."
            )
        if "give" in params:
            parts.append(f"Then {name} gives {_qty(params['give'], singular, plural)} to {friend}.")
        if "receive" in params:
            word = singular if params["receive"] == 1 else plural
            parts.append(f"Then {friend} gives {name} {params['receive']} more {word}.")
        if "share" in params:
            parts.append(
                f"Then the {plural} are shared equally among {params['share']} people."
            )
            question = f"How many {plural} does one person get?"
        elif "price" in params:
            parts.append(f"Each {singular} is worth {params['price']} dollars.")
            question = f"How many dollars are {name}'s {plural} worth?"
        else:
            question = f"How many {plural} does {name} have?"
        return " ".join(parts + [question])
    if t in ("one_day_spend", "two_days", "two_days_spend", "three_days"):
        hours = params["hours"] if isinstance(params["hours"], list) else [params["hours"]]
        parts = [f"{name} earns {params['rate']} dollars an hour."]
        if len(hours) == 1:
            parts.append(f"{name} works {hours[0]} hours.")
        else:
            for index, hours_on_day in enumerate(hours, start=1):
                parts.append(f"On day {index}, {name} works {hours_on_day} hours.")
        if params.get("spend"):
            parts.append(f"Then {name} spends {params['spend']} dollars.")
            question = f"How many dollars does {name} have left from these wages?"
        else:
            question = f"How many dollars does {name} earn?"
        return " ".join(parts + [question])
    if t in ("days_plus", "days_plus_skip", "two_books", "two_books_skip", "two_books_weeks"):
        parts = [
            f"{name} reads {params['per_day']} pages a day for {params['days']} days."
        ]
        if "per_day2" in params:
            parts.append(
                f"{name} also reads a second book at {params['per_day2']} pages a day for {params['days2']} days."
            )
        elif "extra" in params:
            parts.append(f"Then {name} reads {params['extra']} more pages.")
        if "skip" in params:
            parts.append(f"Then {name} skips {params['skip']} pages that were blank and do not count.")
        if "weeks" in params:
            parts.append(f"{name} repeats that same total each week for {params['weeks']} weeks.")
            question = f"How many pages does {name} read in those {params['weeks']} weeks?"
        else:
            question = f"How many pages does {name} read?"
        return " ".join(parts + [question])
    if t in ("rows_left", "rows_price", "two_sections", "two_sections_sold", "two_sections_price"):
        parts = [
            f"{name} sets out {params['rows']} rows of seats with {params['seats']} seats in each row."
        ]
        if "rows2" in params:
            parts.append(
                f"Then {name} adds {params['rows2']} more rows with {params['seats2']} seats in each row."
            )
        if "sold" in params:
            parts.append(f"Then {params['sold']} seats are sold.")
        if "price" in params:
            parts.append(f"Each unsold seat is worth {params['price']} dollars.")
            question = f"How many dollars are the unsold seats worth?"
        elif "sold" in params:
            question = f"How many seats are still unsold?"
        else:
            question = f"How many seats are there?"
        return " ".join(parts + [question])
    raise ValueError(t)


def _base_pack(rng: RNG) -> dict:
    name, friend = _two_names(rng)
    plural, singular = _thing(rng)
    return {
        "frame": "packs",
        "name": name,
        "friend": friend,
        "plural": plural,
        "singular": singular,
        "packs": rng.randint(2, 9),
        "per": rng.randint(3, 12),
    }


def _second_pack(rng: RNG, params: dict) -> None:
    params["packs2"] = rng.randint(2, 6)
    params["per2"] = rng.randint(2, 9)


def _give_leaving(rng: RNG, total: int) -> int:
    return rng.randint(1, total - 1)


def _sample(rng: RNG) -> dict | None:
    template = rng.choice(
        [
            "buy_give",
            "buy_receive",
            "buy_give_receive",
            "two_buys",
            "buy_give_price",
            "buy_give_receive_price",
            "two_buys_give",
            "two_buys_give_price",
            "buy_give_share",
            "two_buys_share",
            "two_buys_give_share",
            "one_day_spend",
            "two_days",
            "two_days_spend",
            "three_days",
            "days_plus",
            "days_plus_skip",
            "two_books",
            "two_books_skip",
            "two_books_weeks",
            "rows_left",
            "rows_price",
            "two_sections",
            "two_sections_sold",
            "two_sections_price",
        ]
    )
    if template.startswith("buy") or template.startswith("two_buys"):
        params = _base_pack(rng)
        params["template"] = template
        total = params["packs"] * params["per"]
        if template in ("two_buys", "two_buys_give", "two_buys_give_price", "two_buys_share", "two_buys_give_share"):
            _second_pack(rng, params)
            total += params["packs2"] * params["per2"]
        if "give" in template:
            params["give"] = _give_leaving(rng, total)
            total -= params["give"]
        if "receive" in template:
            params["receive"] = rng.randint(2, 24)
            total += params["receive"]
        if "share" in template:
            exact = [d for d in (2, 3, 4, 5) if total % d == 0 and total // d >= 1]
            if not exact:
                # Adjust give, or the second purchase, so the total divides.
                share = rng.choice((2, 3, 4, 5))
                if "give" in params and total + params["give"] > share:
                    gross = total + params["give"]
                    max_q = (gross - 1) // share
                    if max_q < 1:
                        return None
                    quotient = rng.randint(1, max_q)
                    params["give"] = gross - share * quotient
                    total = share * quotient
                    params["share"] = share
                else:
                    return None
            else:
                params["share"] = rng.choice(exact)
                total = total // params["share"]
        if "price" in template:
            params["price"] = rng.randint(2, 9)
        if answer_of(params) is None:
            return None
        return params
    if template in ("one_day_spend", "two_days", "two_days_spend", "three_days"):
        name, _friend = _two_names(rng)
        rate = rng.randint(8, 30)
        if template == "one_day_spend":
            hours = rng.randint(2, 9)
            earn = rate * hours
            spend = rng.randint(1, earn - 1)
            return {
                "frame": "wage",
                "template": template,
                "name": name,
                "rate": rate,
                "hours": hours,
                "spend": spend,
            }
        if template == "two_days":
            return {
                "frame": "wage",
                "template": template,
                "name": name,
                "rate": rate,
                "hours": [rng.randint(2, 8), rng.randint(2, 8)],
                "spend": 0,
            }
        if template == "two_days_spend":
            pair = [rng.randint(2, 8), rng.randint(2, 8)]
            earn = rate * sum(pair)
            return {
                "frame": "wage",
                "template": template,
                "name": name,
                "rate": rate,
                "hours": pair,
                "spend": rng.randint(1, earn - 1),
            }
        triple = [rng.randint(2, 6), rng.randint(2, 6), rng.randint(2, 6)]
        return {
            "frame": "wage",
            "template": template,
            "name": name,
            "rate": rng.randint(6, 20),
            "hours": triple,
            "spend": 0,
        }
    if template in ("days_plus", "days_plus_skip", "two_books", "two_books_skip", "two_books_weeks"):
        name, _friend = _two_names(rng)
        params = {
            "frame": "pages",
            "template": template,
            "name": name,
            "per_day": rng.randint(6, 24),
            "days": rng.randint(2, 6),
        }
        if template in ("days_plus", "days_plus_skip"):
            params["extra"] = rng.randint(3, 40)
            total = params["per_day"] * params["days"] + params["extra"]
        else:
            params["per_day2"] = rng.randint(5, 20)
            params["days2"] = rng.randint(2, 5)
            total = params["per_day"] * params["days"] + params["per_day2"] * params["days2"]
        if template in ("days_plus_skip", "two_books_skip", "two_books_weeks"):
            params["skip"] = rng.randint(1, total - 1)
            total -= params["skip"]
        if template == "two_books_weeks":
            params["weeks"] = rng.randint(2, 4)
        if answer_of(params) is None:
            return None
        return params
    name, _friend = _two_names(rng)
    params = {
        "frame": "tickets",
        "template": template,
        "name": name,
        "rows": rng.randint(2, 12),
        "seats": rng.randint(4, 16),
    }
    total = params["rows"] * params["seats"]
    if template in ("two_sections", "two_sections_sold", "two_sections_price"):
        params["rows2"] = rng.randint(2, 8)
        params["seats2"] = rng.randint(3, 10)
        total += params["rows2"] * params["seats2"]
    if template in ("rows_left", "rows_price", "two_sections_sold", "two_sections_price"):
        params["sold"] = rng.randint(1, total - 1)
        total -= params["sold"]
    if template in ("rows_price", "two_sections_price"):
        params["price"] = rng.randint(2, 12)
    if answer_of(params) is None:
        return None
    return params


def generate(seed_bytes: bytes, n: int) -> list[Item]:
    rng = RNG(seed_bytes)
    items: list[Item] = []
    seen: set[str] = set()
    attempts = 0
    limit = max(20, n * 40)
    while len(items) < n:
        attempts += 1
        if attempts > limit:
            raise RuntimeError(f"arith_word produced {len(items)} of {n} after {attempts} draws")
        params = _sample(rng)
        if params is None:
            continue
        answer = answer_of(params)
        steps = steps_of(params)
        if answer is None or answer == 0 or steps < 2 or steps > 5:
            continue
        if answer > 20000:
            continue
        params = dict(params)
        params["n_steps"] = steps
        prompt = render(params)
        if "####" in prompt or prompt in seen:
            continue
        seen.add(prompt)
        items.append(
            Item(
                item_id=f"arith_word-{len(items):04d}",
                prompt=prompt,
                oracle_answer=str(answer),
                family="arith_word",
                params=params,
            )
        )
    return items
