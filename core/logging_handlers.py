"""
Handlers de logging do projeto.
"""
import hashlib

from django.core.cache import cache
from django.utils.log import AdminEmailHandler

# Janela de supressão de e-mails repetidos (segundos).
THROTTLE_SECONDS = 3600


class ThrottledAdminEmailHandler(AdminEmailHandler):
    """
    AdminEmailHandler que envia no máximo 1 e-mail por "assinatura" de erro
    (tipo da exceção + caminho + mensagem) por hora.

    Evita enxurrada de e-mails (e SMTP síncrono dentro do worker) quando um
    mesmo bug é disparado em loop. Se o cache estiver indisponível, envia
    normalmente: nunca perder um alerta é mais importante que o throttle.
    """

    def emit(self, record):
        try:
            exc = record.exc_info[1] if record.exc_info else None
            request = getattr(record, "request", None)
            raw = "|".join(
                [
                    type(exc).__name__ if exc else "",
                    getattr(request, "path", "") or "",
                    record.getMessage(),
                ]
            )
            key = "errmail:" + hashlib.md5(raw.encode("utf-8")).hexdigest()
            if not cache.add(key, 1, THROTTLE_SECONDS):
                return
        except Exception:  # noqa: BLE001 — cache fora do ar: envia mesmo assim
            pass
        super().emit(record)
