"""
Utilitários de ordenação de categorias de animais para relatórios.

Ordem canônica definida pelo cliente:
Touros > Vacas > B. Macho > B. Fêmea > Nov. - 2A. > Nov. - 3A. >
V. Primip > Bois - 2A. > Rufião
"""

CATEGORY_ORDER = [
    "TOUROS",
    "VACAS",
    "B. MACHO",
    "B. FÊMEA",
    "NOV - 2 A.",
    "NOV. - 2A.",
    "NOV - 3 A.",
    "NOV. - 3A.",
    "V. PRIMIP",
    "BOIS - 2 A.",
    "BOIS - 2A.",
    "RUFIÃO",
]

# Posições canônicas (variantes ocupam a mesma posição)
_CANONICAL_POSITIONS = {}
_counter = 0
for _name in CATEGORY_ORDER:
    _key = " ".join(_name.strip().upper().split())
    if _key not in _CANONICAL_POSITIONS:
        _CANONICAL_POSITIONS[_key] = _counter
        _counter += 1


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().upper().split())


def sort_categories(categories):
    """
    Ordena uma lista de categorias de acordo com CATEGORY_ORDER.

    Aceita tanto objetos ORM com atributo `.name` quanto strings puras.
    Categorias não presentes na lista canônica aparecem ao final,
    em ordem alfabética.
    """
    max_pos = len(_CANONICAL_POSITIONS)

    def sort_key(cat):
        name = cat.name if hasattr(cat, "name") else str(cat)
        name_upper = _normalize_name(name)
        pos = _CANONICAL_POSITIONS.get(name_upper, max_pos)
        return (pos, name_upper)

    return sorted(categories, key=sort_key)