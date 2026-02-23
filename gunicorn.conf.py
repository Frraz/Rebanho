# ==============================================================================
# gunicorn.conf.py — Rebanho (Gestão de Rebanhos)
# Servidor: 2 vCPUs / 7.8GB RAM — dividido entre 4 sistemas Django
# Rebanho tem Celery, budget de CPU do web é menor que sistemas sem Celery
# ==============================================================================

# ── Bind ───────────────────────────────────────────────────────────────────────
bind = "0.0.0.0:8000"

# ── Workers ────────────────────────────────────────────────────────────────────
# 2 workers + 2 threads = boa concorrência sem estourar CPU compartilhada
workers = 2
worker_class = "sync"
threads = 2
worker_connections = 100

# ── Timeouts ───────────────────────────────────────────────────────────────────
timeout = 30
graceful_timeout = 20
keepalive = 2

# ── Processo ───────────────────────────────────────────────────────────────────
max_requests = 500
max_requests_jitter = 50
preload_app = True

# ── Logging ────────────────────────────────────────────────────────────────────
accesslog = "-"
errorlog  = "-"
loglevel  = "warning"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Segurança ──────────────────────────────────────────────────────────────────
forwarded_allow_ips = "127.0.0.1"
proxy_protocol = False

# ── Control socket ─────────────────────────────────────────────────────────────
# Desativa o socket de controle — não utilizado em Docker e causa
# "[Errno 13] Control server error" em containers sem CAP_SYS_RESOURCE
control_socket_disable = True

# ── Performance ────────────────────────────────────────────────────────────────
sendfile = False
