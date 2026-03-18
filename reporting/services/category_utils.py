"""
Utilitários de ordenação de categorias de animais para relatórios.

A ordem canônica segue a sequência zootécnica do rebanho:
touros e vacas primeiro, bezerros, novilhos, primíparas,
bois, descartes e rufião por último.
"""

CATEGORY_ORDER = [
    "TOUROS",
    "VACAS",
    "B. MACHO",
    "B. FÊMEA",
    "NOV - 2 A.",
    "NOV - 3 A.",
    "V. PRIMIP",
    "BOIS - 2 A.",
    "BOIS - 2-3 A.",
    "DESC. VACAS",
    "DESC. NOV",
    "DESC. BOIS",
    "RUFIÃO",
]


def sort_categories(categories):
    """
    Ordena uma lista de categorias de acordo com CATEGORY_ORDER.

    Aceita tanto objetos ORM com atributo `.name` quanto strings puras.
    Categorias não presentes na lista canônica aparecem ao final,
    em ordem alfabética.

    Uso:
        # QuerySet de objetos ORM
        categories = sort_categories(list(AnimalCategory.objects.filter(is_active=True)))

        # Lista de strings
        categories = sort_categories(["VACAS", "TOUROS", "RUFIÃO"])
    """
    def sort_key(cat):
        name = cat.name if hasattr(cat, "name") else str(cat)
        name_upper = name.strip().upper()
        try:
            return (CATEGORY_ORDER.index(name_upper), name_upper)
        except ValueError:
            return (len(CATEGORY_ORDER), name_upper)

    return sorted(categories, key=sort_key)