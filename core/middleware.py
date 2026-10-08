"""
Middlewares do projeto.
"""
import logging

from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest

logger = logging.getLogger(__name__)


class ValidationErrorAs400:
    """
    Rede de segurança: em requisições GET, um ValidationError não tratado
    (tipicamente um UUID malformado vindo da query string, ex.: ?cliente=abc)
    vira HTTP 400 em vez de 500.

    O Django registra 4xx como WARNING, então o mail_admins (nível ERROR)
    não dispara e-mail por entrada inválida do usuário/front.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if request.method == "GET" and isinstance(exception, ValidationError):
            logger.warning(
                "Parâmetro inválido em GET %s: %s", request.path, exception
            )
            return HttpResponseBadRequest("Parâmetro inválido")
        return None
