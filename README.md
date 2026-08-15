# 🚀 Grok Register — CPA Farming Pipeline

Automated Grok account registration + CPA token conversion pipeline.

## Features

- 🔄 **Register → SSO → CPA** (fully automated)
- 📧 **CloudMail** email provisioning (bangdodo.bond, elf.biz.id, sakithati.bond)
- 🤖 **Boterdrop-Solver** (Camoufox) for Cloudflare Turnstile
- 🌐 **Webshare proxy** with auto-fallback
- ⚡ **Multi-threaded** farming (3-5 workers)

## Quick Start

```bash
# Clone
git clone https://github.com/elman14/grok-register.git
cd grok-register

# Setup
cp .env.example .env
# Edit .env with your tokens
uv sync

# Farm
python farm_cpa.py --threads 3 --count 10000
```

## File Structure

### Core Pipeline
| File | Description |
|------|-------------|
| `farm_cpa.py` | Main farming script (Register + CPA) |
| `grok.py` | Account registration module |
| `sso_to_cpa.py` | SSO → CPA token conversion |
| `email_service.py` | CloudMail email provisioning |
| `YesCaptcha_service.py` | Boterdrop-Solver integration |

### Tools
| File | Description |
|------|-------------|
| `grok_free.py` | Free Grok registration |
| `auto_replenish.py` | Auto-replenish tokens |
| `clash_rotator.py` | Proxy rotation |
| `device_mint.py` | Device code flow mint |
| `device_consent.py` | Device consent auto-approve |
| `token_daemon.py` | Token daemon |
| `turnstile_solver_local.py` | Local Turnstile solver |
| `poll_tokens.py` | Poll device code tokens |

### Config
| File | Description |
|------|-------------|
| `.env.example` | Config template |
| `.gitignore` | Git ignore rules |
| `pyproject.toml` | Python dependencies |

## Environment Variables

```env
# Proxy (required)
GROK_PROXY="http://user:pass@proxy:port"

# CloudMail
CLOUDMAIL_BASE_URL="https://..."
CLOUDMAIL_PUBLIC_TOKEN="..."

# Threads
THREADS=3
```

## Security

- ⚠️ Never commit `.env` (contains secrets)
- ⚠️ Never commit `keys/` (contains tokens)
- Both are in `.gitignore`

## License

MIT
