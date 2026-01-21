import random

DNA_NUCS = ['А', 'Т', 'Г', 'Ц']
DNA_COMP = {'А': 'Т', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}
DNA_TO_RNA = {'А': 'У', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}


async def generate_sequence(length: int) -> str:
    return "".join(random.choice(DNA_NUCS) for _ in range(length))


async def complement(seq: str, table: dict) -> str:
    return "".join(table[n] for n in seq)


async def reverse(seq: str) -> str:
    return seq[::-1]


async def generate_task(mode: int, length: int = 18):
    top = await generate_sequence(length)
    bottom = await complement(top, DNA_COMP)

    task = {
        "mode": mode,
        "task_id": random.randint(10_000_000, 999_999_999),
        "condition": {},
        "internal_solution": {},
        "tryings": 0
    }

    if mode == 1:
        mrna = await complement(bottom, DNA_TO_RNA)
        task["condition"] = {
            "top": f"5'-{top}-3'",
            "bottom": f"3'-{bottom}-5'",
            "instruction": "Нижняя цепь транскрибируемая. Введите мРНК:"
        }
        task["internal_solution"] = {"type": "RNA", "canonical_5_3": mrna}

    elif mode == 2:
        mrna = await reverse(await complement(top, DNA_TO_RNA))
        task["condition"] = {
            "top": f"5'-{top}-3'",
            "bottom": f"3'-{bottom}-5'",
            "instruction": "Верхняя цепь транскрибируемая. Введите мРНК:"
        }
        task["internal_solution"] = {"type": "RNA", "canonical_5_3": mrna}

    elif mode == 3:
        second = await reverse(bottom)
        task["condition"] = {
            "single_chain": f"5'-{top}-3'",
            "instruction": "Постройте транскрибируемую цепь ДНК:"
        }
        task["internal_solution"] = {"type": "DNA", "canonical_5_3": second}

    return task


async def validate_submission(user_input: str, solution: dict):
    text = user_input.replace(" ", "").upper()

    start, end = text[:2], text[-2:]
    seq = text[3:-3] if "-" in text else text[2:-2]

    canonical = solution["canonical_5_3"]
    n = len(canonical)

    if start == "5'" and end == "3'":
        direction = "forward"
    elif start == "3'" and end == "5'":
        direction = "reverse"
    else:
        return {
            "is_correct": False,
            "score": 0,
            "errors": [{"type": "DIRECTION", "msg": "Неверно указано направление"}]
        }

    if len(seq) != n:
        return {
            "is_correct": False,
            "score": 0,
            "errors": [{"type": "LENGTH", "msg": "Неверная длина цепи"}]
        }

    errors = []

    for i in range(n):
        if direction == "forward":
            expected = canonical[i]
            got = seq[i]
            visual_index = i
        else:
            expected = canonical[n - 1 - i]
            got = seq[i]
            visual_index = i  # важно: индекс именно ввода пользователя

        if got != expected:
            errors.append({
                "index": visual_index,
                "expected": expected,
                "got": got
            })

    if not errors:
        return {"is_correct": True, "score": 100, "errors": []}

    return {
        "is_correct": False,
        "score": max(0, 100 - len(errors) * 10),
        "errors": errors,
        "direction_used": direction
    }

