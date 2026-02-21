# ==============================================================================
# gunicorn.conf.py — Configuração do Gunicorn
# Coloque este arquivo na raiz do projeto (/app/gunicorn.conf.py)
# O Gunicorn carrega automaticamente se o arquivo existir no diretório atual.
# ==============================================================================

import multiprocessing

# Binding
bind = "0.0.0.0:8000"

# Workers — regra: (2 × nº_cores) + 1
workers = 3
worker_class = "sync"
worker_tmp_dir = "/tmp/gunicorn"

# Timeouts
timeout = 120
graceful_timeout = 30
keepalive = 5

# Reciclagem de workers (evita memory leaks)
max_requests = 1000
max_requests_jitter = 100

# Logs para stdout/stderr (capturados pelo Docker)
accesslog = "-"
errorlog = "-"
loglevel = "info"

# SOLUÇÃO: desativa o Control Socket Server (Gunicorn 25.x)
# Esse recurso serve apenas para hot-reload sem downtime via SIGUSR2,
# que não é usado em ambientes Docker onde o ciclo de vida é gerenciado
# pelo Compose. Sem isso, o Gunicorn loga:
# "[Errno 13] Control server error: Permission denied"
# porque containers não-root não têm CAP_SYS_RESOURCE para fcntl.F_SETPIPE_SZ.
control_socket_disable = True

# Performance
sendfile = False