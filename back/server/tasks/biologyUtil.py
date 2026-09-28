import random
import re

DNA_NUCS = ['А', 'Т', 'Г', 'Ц']
DNA_COMP = {'А': 'Т', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}
DNA_TO_RNA = {'А': 'У', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}
RNA_COMP = {'А': 'У', 'У': 'А', 'Г': 'Ц', 'Ц': 'Г'}

GENETIC_MAP = {
    'УУУ': 'ФЕН', 'УУЦ': 'ФЕН', 'УУА': 'ЛЕЙ', 'УУГ': 'ЛЕЙ',
    'ЦУУ': 'ЛЕЙ', 'ЦУЦ': 'ЛЕЙ', 'ЦУА': 'ЛЕЙ', 'ЦУГ': 'ЛЕЙ',
    'АУУ': 'ИЛЕ', 'АУЦ': 'ИЛЕ', 'АУА': 'ИЛЕ', 'АУГ': 'МЕТ',
    'ГУУ': 'ВАЛ', 'ГУЦ': 'ВАЛ', 'ГУА': 'ВАЛ', 'ГУГ': 'ВАЛ',
    'УЦУ': 'СЕР', 'УЦЦ': 'СЕР', 'УЦА': 'СЕР', 'УЦГ': 'СЕР',
    'ЦЦУ': 'ПРО', 'ЦЦЦ': 'ПРО', 'ЦЦА': 'ПРО', 'ЦЦГ': 'ПРО',
    'АЦУ': 'ТРЕ', 'АЦЦ': 'ТРЕ', 'АЦА': 'ТРЕ', 'АЦГ': 'ТРЕ',
    'ГЦУ': 'АЛА', 'ГЦЦ': 'АЛА', 'ГЦА': 'АЛА', 'ГЦГ': 'АЛА',
    'УАУ': 'ТИР', 'УАЦ': 'ТИР', 'УАА': 'СТОП', 'УАГ': 'СТОП',
    'ЦАУ': 'ГИС', 'ЦАЦ': 'ГИС', 'ЦАА': 'ГЛН', 'ЦАГ': 'ГЛН',
    'ААУ': 'АСН', 'ААЦ': 'АСН', 'ААА': 'ЛИЗ', 'ААГ': 'ЛИЗ',
    'ГАУ': 'АСП', 'ГАЦ': 'АСП', 'ГАА': 'ГЛУ', 'ГАГ': 'ГЛУ',
    'УГУ': 'ЦИС', 'УГЦ': 'ЦИС', 'УГА': 'СТОП', 'УГГ': 'ТРИ',
    'ЦГУ': 'АРГ', 'ЦГЦ': 'АРГ', 'ЦГА': 'АРГ', 'ЦГГ': 'АРГ',
    'АГУ': 'СЕР', 'АГЦ': 'СЕР', 'АГА': 'АРГ', 'АГГ': 'АРГ',
    'ГГУ': 'ГЛИ', 'ГГЦ': 'ГЛИ', 'ГГА': 'ГЛИ', 'ГГГ': 'ГЛИ',
}

CODONS_NON_STOP = [codon for codon, aa in GENETIC_MAP.items() if aa != 'СТОП']

QUOTE_CHARS = "\'\"\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u2039\u203a\u00ab\u00bb\u02bc\u02b9\u02bb\u02c8\u00b4`\u2032\u2033\uff07\uff02"
DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2212"

INPUT_TRANSLATION = str.maketrans({
    **{char: "'" for char in QUOTE_CHARS},
    **{char: '-' for char in DASH_CHARS},
})


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

    elif mode == 4:
        # Биосинтез белка (трансляция по таблице генетического кода)
        n_triplets = max(1, length // 3)
        codons = [random.choice(CODONS_NON_STOP) for _ in range(n_triplets)]
        mrna_seq = "".join(codons)
        amino_acids = [GENETIC_MAP[c] for c in codons]
        canonical = "-".join(amino_acids)
        task["condition"] = {
            "mrna": f"5'-{mrna_seq}-3'",
            "table_hint": True,
            "instruction": "Используя таблицу генетического кода, определите аминокислотную последовательность полипептида (через дефис или пробел):"
        }
        task["internal_solution"] = {
            "type": "protein",
            "canonical": canonical,
            "amino_acids": amino_acids,
            "mrna": mrna_seq
        }

    elif mode == 5:
        # Антикодоны тРНК к кодонам иРНК
        n_triplets = max(1, length // 3)
        codons = [random.choice(CODONS_NON_STOP) for _ in range(n_triplets)]
        anticodons = ["".join(RNA_COMP[n] for n in c) for c in codons]
        canonical = ", ".join(anticodons)
        task["condition"] = {
            "codons": ", ".join(codons),
            "table_hint": True,
            "instruction": "Определите антикодоны тРНК, комплементарные кодонам иРНК (через запятую или дефис):"
        }
        task["internal_solution"] = {
            "type": "anticodons",
            "canonical": canonical,
            "codons": codons,
            "anticodons": anticodons
        }

    elif mode == 6:
        # Интерактивный конструктор нуклеотида
        is_rna = random.choice([True, False])
        sugar = 'рибоза' if is_rna else 'дезоксирибоза'
        base = random.choice(['А', 'У', 'Г', 'Ц'] if is_rna else ['А', 'Т', 'Г', 'Ц'])
        base_names = {'А': 'Адениловый', 'Т': 'Тимидиловый', 'Г': 'Гуаниловый', 'Ц': 'Цитидиловый', 'У': 'Уридиловый'}
        target_name = f"{base_names.get(base, base)} нуклеотид ({'РНК' if is_rna else 'ДНК'})"
        task["condition"] = {
            "kind": "interactive_nucleotide",
            "interactive_type": "nucleotide",
            "target": target_name,
            "sugar": sugar,
            "base": base,
            "instruction": f"Соберите целевой нуклеотид: {target_name}"
        }
        task["internal_solution"] = {
            "type": "interactive_nucleotide",
            "sugar": sugar,
            "base": base,
            "has_phosphate": True,
            "canonical": f"{target_name} ({base} + {sugar} + остаток фосфорной кислоты)"
        }

    elif mode == 7:
        # Интерактивная сборка полинуклеотидной цепи
        template = await generate_sequence(length)
        seq = await complement(template, DNA_COMP)
        task["condition"] = {
            "kind": "interactive_chain",
            "interactive_type": "chain",
            "template_sequence": template,
            "target_sequence": seq,
            "instruction": f"Соберите комплементарную цепь ДНК (5' -> 3') к цепочке 3'-{template}-5'"
        }
        task["internal_solution"] = {
            "type": "interactive_chain",
            "sequence": seq,
            "canonical": f"5'-{seq}-3'"
        }

    elif mode == 8:
        # Интерактивное скручивание тРНК в трилистник
        codon = random.choice(CODONS_NON_STOP)
        amino = GENETIC_MAP[codon]
        anticodon = "".join(RNA_COMP[n] for n in codon)
        task["condition"] = {
            "kind": "interactive_cloverleaf",
            "interactive_type": "cloverleaf",
            "amino_acid": amino,
            "codon": codon,
            "anticodon": anticodon,
            "instruction": f"Скрутите цепь тРНК во вторичную структуру («Трилистник») и укажите антикодон для аминокислоты {amino} (кодон иРНК {codon}):"
        }
        task["internal_solution"] = {
            "type": "interactive_cloverleaf",
            "amino_acid": amino,
            "anticodon": anticodon,
            "paired": True,
            "canonical": f"Антикодон {anticodon} (связывается с кодоном {codon}, переносит {amino})"
        }

    return task


async def validate_submission(user_input, solution: dict):
    if not solution:
        return {"is_correct": False, "score": 0, "errors": []}

    # 1. Интерактивный нуклеотид (режим 6)
    if "sugar" in solution:
        if isinstance(user_input, dict):
            s_ok = str(user_input.get('sugar', '')).strip().lower() == str(solution['sugar']).strip().lower()
            b_ok = str(user_input.get('base', '')).strip().upper() == str(solution['base']).strip().upper()
            p_ok = bool(user_input.get('has_phosphate', user_input.get('phosphate', False))) == bool(solution.get('has_phosphate', True))
            is_correct = s_ok and b_ok and p_ok
        else:
            is_correct = False
        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "errors": [] if is_correct else [{"type": "INCORRECT", "msg": "Нуклеотид собран неверно"}]
        }

    # 2. Интерактивный трилистник тРНК (режим 8)
    if "anticodon" in solution and "paired" in solution:
        if isinstance(user_input, dict):
            a_ok = str(user_input.get('anticodon', '')).strip().upper() == str(solution['anticodon']).strip().upper()
            p_ok = bool(user_input.get('paired', False)) == bool(solution.get('paired', True))
            is_correct = a_ok and p_ok
        else:
            is_correct = str(user_input or '').strip().upper() == str(solution['anticodon']).strip().upper()
        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "errors": [] if is_correct else [{"type": "INCORRECT", "msg": "Антикодон или структура неверны"}]
        }

    # 3. Интерактивная цепь ДНК (режим 7)
    if "sequence" in solution:
        if isinstance(user_input, list):
            given = "".join(str(x) for x in user_input).strip().upper()
        elif isinstance(user_input, dict) and "sequence" in user_input:
            given = str(user_input["sequence"]).strip().upper()
        else:
            given = str(user_input or '').strip().upper()
        is_correct = (given == str(solution['sequence']).strip().upper())
        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "errors": [] if is_correct else [{"type": "MISMATCH", "msg": "Последовательность цепи не совпадает"}]
        }

    # 4. Биосинтез белка и антикодоны (режимы 4, 5)
    if "canonical" in solution and "canonical_5_3" not in solution:
        user_tokens = [t.upper() for t in re.split(r'[^a-zA-Zа-яА-ЯёЁ0-9]+', str(user_input or '').strip()) if t]
        sol_tokens = [t.upper() for t in re.split(r'[^a-zA-Zа-яА-ЯёЁ0-9]+', str(solution['canonical']).strip()) if t]
        is_correct = bool(user_tokens and user_tokens == sol_tokens)
        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "errors": [] if is_correct else [{"type": "MISMATCH", "msg": "Неверный ответ"}]
        }

    # 5. Классические цепи 5'->3' / 3'->5' (режимы 1, 2, 3)
    text = str(user_input or '').translate(INPUT_TRANSLATION).replace(" ", "").upper()
    match = re.fullmatch(r"([53])'-?([АТГЦУ]+)-?([35])'", text)
    if not match:
        return {
            "is_correct": False,
            "score": 0,
            "errors": [{"type": "DIRECTION", "msg": "Неверно указано направление"}]
        }

    start, seq, end = match.groups()

    canonical = solution.get("canonical_5_3", "")
    n = len(canonical)

    if start == "5" and end == "3":
        direction = "forward"
    elif start == "3" and end == "5":
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
            visual_index = i

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
