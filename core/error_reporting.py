"""
Filtro do relatório de exceções enviado por e-mail aos admins.
"""
from django.views.debug import SafeExceptionReporterFilter


class MaskCsrfExceptionReporterFilter(SafeExceptionReporterFilter):
    """
    Além do que o filtro padrão já mascara (API, AUTH, TOKEN, KEY, SECRET,
    PASS, SIGNATURE, HTTP_COOKIE), mascara também o CSRF_COOKIE, que
    aparece em claro em request.META no e-mail de erro.
    """

    def get_safe_request_meta(self, request):
        meta = super().get_safe_request_meta(request)
        if "CSRF_COOKIE" in meta:
            meta["CSRF_COOKIE"] = self.cleansed_substitute
        return meta
