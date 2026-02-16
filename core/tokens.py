"""
Tokens de aprovação de usuário.

Usa django.core.signing — sem migration, sem nova tabela.
Token expira em 7 dias (configurável).
Contém o user_id assinado com SECRET_KEY — impossível forjar.
"""
from django.core import signing

SALT    = 'user-approval-v1'
MAX_AGE = 60 * 60 * 24 * 7  # 7 dias em segundos


def gerar_token(user_id: int) -> str:
    """Gera token assinado para aprovação do usuário."""
    return signing.dumps({'user_id': user_id}, salt=SALT)


def validar_token(token: str) -> int | None:
    """
    Valida e decodifica o token.
    Retorna o user_id se válido, None se expirado/inválido.
    """
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        return data['user_id']
    except signing.SignatureExpired:
        return None
    except signing.BadSignature:
        return None
    except (KeyError, Exception):
        return None