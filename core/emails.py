"""
Core Emails — Funções de envio de e-mail do sistema.

Funções:
  - notificar_staff_novo_cadastro(): e-mail para todos is_staff com link de aprovação
  - notificar_usuario_aprovado():    e-mail de boas-vindas ao usuário aprovado
  - notificar_usuario_rejeitado():   e-mail informando rejeição
"""
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

from core.tokens import gerar_token

User = get_user_model()

FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@gestao-rebanhos.com')


def _build_approval_url(request, user_id: int, acao: str) -> str:
    """Monta URL absoluta de aprovação/rejeição."""
    token = gerar_token(user_id)
    path  = f'/conta/aprovar/{token}/?acao={acao}'
    return request.build_absolute_uri(path)


def notificar_staff_novo_cadastro(request, novo_usuario) -> int:
    """
    Envia e-mail para todos os usuários is_staff=True
    informando sobre o novo cadastro e fornecendo link de aprovação.

    Retorna o número de e-mails enviados.
    """
    staff_users = User.objects.filter(is_staff=True, is_active=True).exclude(email='')

    if not staff_users.exists():
        return 0

    url_aprovar  = _build_approval_url(request, novo_usuario.id, 'aprovar')
    url_rejeitar = _build_approval_url(request, novo_usuario.id, 'rejeitar')

    nome_completo = novo_usuario.get_full_name() or novo_usuario.username

    assunto = f'[Gestão de Rebanhos] Novo cadastro aguardando aprovação — {nome_completo}'

    corpo_html = render_to_string('emails/novo_cadastro_staff.html', {
        'novo_usuario':  novo_usuario,
        'nome_completo': nome_completo,
        'url_aprovar':   url_aprovar,
        'url_rejeitar':  url_rejeitar,
    })
    corpo_texto = strip_tags(corpo_html)

    enviados = 0
    for staff in staff_users:
        try:
            send_mail(
                subject=assunto,
                message=corpo_texto,
                html_message=corpo_html,
                from_email=FROM_EMAIL,
                recipient_list=[staff.email],
                fail_silently=True,
            )
            enviados += 1
        except Exception:
            pass

    return enviados


def notificar_usuario_aprovado(usuario) -> bool:
    """
    Envia e-mail de boas-vindas ao usuário informando que a conta foi aprovada.
    Retorna True se enviado com sucesso.
    """
    if not usuario.email:
        return False

    nome_completo = usuario.get_full_name() or usuario.username
    assunto = '[Gestão de Rebanhos] Sua conta foi aprovada! ✅'

    corpo_html = render_to_string('emails/conta_aprovada.html', {
        'usuario':      usuario,
        'nome_completo': nome_completo,
        'login_url':    settings.LOGIN_URL,
    })
    corpo_texto = strip_tags(corpo_html)

    try:
        send_mail(
            subject=assunto,
            message=corpo_texto,
            html_message=corpo_html,
            from_email=FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=True,
        )
        return True
    except Exception:
        return False


def notificar_usuario_rejeitado(usuario) -> bool:
    """
    Envia e-mail informando que o cadastro foi rejeitado.
    Retorna True se enviado com sucesso.
    """
    if not usuario.email:
        return False

    nome_completo = usuario.get_full_name() or usuario.username
    assunto = '[Gestão de Rebanhos] Cadastro não aprovado'

    corpo_html = render_to_string('emails/conta_rejeitada.html', {
        'usuario':       usuario,
        'nome_completo': nome_completo,
    })
    corpo_texto = strip_tags(corpo_html)

    try:
        send_mail(
            subject=assunto,
            message=corpo_texto,
            html_message=corpo_html,
            from_email=FROM_EMAIL,
            recipient_list=[usuario.email],
            fail_silently=True,
        )
        return True
    except Exception:
        return False