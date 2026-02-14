"""
Core Views - Dashboard e views principais.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


# @login_required  # Descomentar quando implementar autenticação
def dashboard_view(request):
    """
    Dashboard principal - Painel de Rebanho.
    
    Exibe:
    - Resumo de saldos por fazenda
    - Movimentações recentes
    - Alertas/notificações
    - Cards com estatísticas principais
    """
    context = {
        'page_title': 'Dashboard - Painel de Rebanho',
    }
    
    return render(request, 'core/dashboard.html', context)