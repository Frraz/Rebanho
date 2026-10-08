"""
Helpers para leitura segura de parâmetros de query string.
"""
import uuid

from django.core.exceptions import BadRequest

# Valores que o front (JS) costuma enviar quando não há valor real.
_VAZIOS = {"", "undefined", "null", "None"}


def uuid_param(request, *names, required=False, lenient=False):
    """
    Lê um UUID de request.GET aceitando um ou mais nomes de parâmetro
    (o primeiro que tiver valor real vence).

    - Ausente / vazio / "undefined" / "null" / "None" -> ignorado.
    - Valor presente mas que não é UUID -> BadRequest (HTTP 400, logado como
      WARNING pelo Django, sem e-mail de erro). Com lenient=True o valor
      inválido é ignorado (retorna None) — usado em filtros de telas HTML,
      onde é melhor mostrar a lista sem o filtro do que uma página de erro.
    - Nenhum valor e required=True -> BadRequest.

    Retorna uuid.UUID ou None.
    """
    for name in names:
        raw = (request.GET.get(name) or "").strip()
        if raw in _VAZIOS:
            continue
        try:
            return uuid.UUID(raw)
        except ValueError:
            if lenient:
                continue
            raise BadRequest(f"{name} inválido")
    if required:
        raise BadRequest(f"{names[0]} obrigatório")
    return None
