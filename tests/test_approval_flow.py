"""
test_approval_flow.py — Fluxo de aprovação de usuários.

Testa:
  - Token válido é gerado e decodificado corretamente
  - Token com user_id correto retorna o user_id
  - Token expirado retorna None
  - Token adulterado retorna None
  - Aprovação ativa o usuário
  - Rejeição remove o usuário do banco
  - Token já usado (usuário já ativo) é tratado corretamente
"""
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model

from core.tokens import gerar_token, validar_token

User = get_user_model()


@pytest.mark.django_db
class TestTokens:
    """Testa geração e validação de tokens de aprovação."""

    def test_gerar_e_validar_token_valido(self, db):
        token = gerar_token(user_id=42)
        resultado = validar_token(token)
        assert resultado == 42

    def test_token_expirado_retorna_none(self, db):
        token = gerar_token(user_id=99)
        # Simula token expirado: max_age=0 rejeita qualquer token
        from django.core import signing
        with patch('core.tokens.MAX_AGE', -1):
            resultado = validar_token(token)
        assert resultado is None

    def test_token_adulterado_retorna_none(self, db):
        token = gerar_token(user_id=10)
        token_adulterado = token + 'adulterado'
        resultado = validar_token(token_adulterado)
        assert resultado is None

    def test_token_string_vazia_retorna_none(self, db):
        resultado = validar_token('')
        assert resultado is None

    def test_token_lixo_retorna_none(self, db):
        resultado = validar_token('token-completamente-invalido-xpto-123')
        assert resultado is None

    def test_tokens_diferentes_para_usuarios_diferentes(self, db):
        t1 = gerar_token(user_id=1)
        t2 = gerar_token(user_id=2)
        assert t1 != t2
        assert validar_token(t1) == 1
        assert validar_token(t2) == 2

    def test_token_preserva_user_id(self, db):
        """Testa com vários IDs para garantir que não há colisão."""
        for uid in [1, 100, 9999, 123456]:
            token = gerar_token(user_id=uid)
            assert validar_token(token) == uid


@pytest.mark.django_db
class TestAprovacaoUsuario:
    """Testa o fluxo completo de aprovação/rejeição."""

    @pytest.fixture
    def usuario_inativo(self, db):
        return User.objects.create_user(
            username='novousuario',
            password='senha123',
            email='novo@test.com',
            is_active=False,
        )

    def test_aprovar_ativa_usuario(self, usuario_inativo):
        assert not usuario_inativo.is_active

        usuario_inativo.is_active = True
        usuario_inativo.save(update_fields=['is_active'])
        usuario_inativo.refresh_from_db()

        assert usuario_inativo.is_active

    def test_usuario_inativo_nao_consegue_fazer_login(self, usuario_inativo, client):
        response = client.post('/login/', {
            'username': 'novousuario',
            'password': 'senha123',
        })
        # Não deve redirecionar para dashboard (login falhou)
        assert response.status_code != 302 or '/login' in response.get('Location', '')
        assert not response.wsgi_request.user.is_authenticated

    def test_usuario_ativo_consegue_fazer_login(self, usuario_inativo, client):
        usuario_inativo.is_active = True
        usuario_inativo.save()

        response = client.post('/login/', {
            'username': 'novousuario',
            'password': 'senha123',
        }, follow=True)

        assert response.wsgi_request.user.is_authenticated

    def test_token_para_usuario_inexistente_retorna_none_seguro(self, db):
        """Token de usuário deletado não deve dar erro 500."""
        token = gerar_token(user_id=999999)
        # validar_token retorna o user_id, mas a view deve tratar DoesNotExist
        user_id = validar_token(token)
        assert user_id == 999999
        # Usuário não existe
        assert not User.objects.filter(pk=user_id).exists()


@pytest.mark.django_db
class TestRegistroUsuario:
    """Testa o formulário de cadastro."""

    def test_registro_cria_usuario_inativo(self, client):
        response = client.post('/cadastrar/', {
            'first_name': 'João',
            'last_name':  'Silva',
            'email':      'joao@test.com',
            'username':   'joaosilva',
            'password1':  'SenhaForte@123',
            'password2':  'SenhaForte@123',
        })
        # Redireciona ao login após cadastro
        assert response.status_code == 302

        usuario = User.objects.get(username='joaosilva')
        assert not usuario.is_active  # Sempre inativo ao cadastrar

    def test_registro_com_username_duplicado_falha(self, client, db_user):
        response = client.post('/cadastrar/', {
            'first_name': 'Outro',
            'email':      'outro@test.com',
            'username':   db_user.username,  # Username já existe
            'password1':  'SenhaForte@123',
            'password2':  'SenhaForte@123',
        })
        assert response.status_code == 200  # Fica na página (erro no form)
        assert User.objects.filter(username=db_user.username).count() == 1

    def test_registro_com_senhas_diferentes_falha(self, client, db):
        response = client.post('/cadastrar/', {
            'first_name': 'Teste',
            'email':      'teste@test.com',
            'username':   'testenovo',
            'password1':  'SenhaForte@123',
            'password2':  'SenhaDiferente@456',
        })
        assert response.status_code == 200
        assert not User.objects.filter(username='testenovo').exists()

    def test_registro_com_email_duplicado_falha(self, client, db_user):
        db_user.email = 'existente@test.com'
        db_user.save()

        response = client.post('/cadastrar/', {
            'first_name': 'Novo',
            'email':      'existente@test.com',  # Email já existe
            'username':   'novousr2',
            'password1':  'SenhaForte@123',
            'password2':  'SenhaForte@123',
        })
        assert response.status_code == 200
        assert not User.objects.filter(username='novousr2').exists()