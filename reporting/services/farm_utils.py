"""
Utilitários de ordenação de fazendas para relatórios.

A ordem de exibição das fazendas é fixa e definida pelo cliente.
Fazendas não listadas aparecem ao final, em ordem alfabética.
"""

FARM_ORDER = [
    "LUCIANA",
    "SUPRESA FIA",
    "SUPRESA",
    "PARAÍSO",
    "LACY",
    "MARIANA",
    "PEDRO",
    "PEDRO FIA",
    "ROSS CLÉIA (SURP. NELSON)",
    "ROSS CLÉIA (LUCIANA)",
]

_FARM_POSITIONS = {name: i for i, name in enumerate(FARM_ORDER)}


def sort_farms(farms):
    """
    Ordena uma lista de fazendas de acordo com FARM_ORDER.

    Aceita tanto objetos ORM com atributo `.name` quanto strings puras.
    Fazendas não presentes na lista canônica aparecem ao final,
    em ordem alfabética.
    """
    max_pos = len(_FARM_POSITIONS)

    def sort_key(farm):
        name = farm.name if hasattr(farm, "name") else str(farm)
        name_upper = name.strip().upper()
        pos = _FARM_POSITIONS.get(name_upper, max_pos)
        return (pos, name_upper)

    return sorted(farms, key=sort_key)


def sort_farm_names(names):
    """
    Ordena uma lista de nomes de fazendas (strings).
    Conveniência para quando já se tem apenas os nomes.
    """
    max_pos = len(_FARM_POSITIONS)

    def sort_key(name):
        name_upper = name.strip().upper()
        pos = _FARM_POSITIONS.get(name_upper, max_pos)
        return (pos, name_upper)

    return sorted(names, key=sort_key)