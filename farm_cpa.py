#!/usr/bin/env python3
"""
Farm + CPA: Register -> SSO -> OAuth CPA -> Save + Inject 9Router
Single flow: register account then immediately convert to CPA.
"""
import os, sys, json, time, re, base64, secrets, hashlib, urllib.parse, sqlite3, uuid, argparse, random, string, struct, threading, concurrent.futures
from datetime import datetime, timezone
from curl_cffi import requests as cf_requests
from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --- Config ---
site_url = "https://accounts.x.ai"
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
PROXY_LIST = [
    os.getenv("GROK_PROXY", "http://pkcgnrie-rotate:yzoezfvrdxv4@p.webshare.io:80"),
]
_proxy_idx = 0
_proxy_raw = PROXY_LIST[0] if PROXY_LIST[0].strip() else PROXY_LIST[1]
PROXIES = {"http": _proxy_raw, "https": _proxy_raw} if _proxy_raw.strip() else None
import threading as _threading
_proxy_lock = _threading.Lock()

def get_proxy():
    global _proxy_idx, _proxy_raw, PROXIES
    with _proxy_lock:
        return PROXIES

def switch_proxy(reason=""):
    global _proxy_idx, _proxy_raw, PROXIES
    with _proxy_lock:
        _proxy_idx = (_proxy_idx + 1) % len(PROXY_LIST)
        _proxy_raw = PROXY_LIST[_proxy_idx]
        PROXIES = {"http": _proxy_raw, "https": _proxy_raw} if _proxy_raw.strip() else None
        print(f"[PROXY] Switched to: {_proxy_raw[:40]}... ({reason})")

def test_current_proxy():
    try:
        r = cf_requests.get("https://auth.x.ai", impersonate="chrome120",
                            proxies=PROXIES or {}, timeout=10)
        return r.status_code in (403, 404, 200)
    except:
        return False
CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
REDIRECT_URI = "http://127.0.0.1:56121/callback"
TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
AUTHORIZE_URL = "https://auth.x.ai/oauth2/authorize"
SCOPE = "openid profile email offline_access grok-cli:access api:access"
KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
AUTH_DIR = os.path.join(KEYS_DIR, "auths")
DB_PATH = os.path.expanduser("~/.9router/db/data.sqlite")

config = {
    "site_key": "0x4AAAAAAAhr9JGVDZbrZOo0",
    "action_id": None,
    "state_tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22(app)%22%2C%7B%22children%22%3A%5B%22(auth)%22%2C%7B%22children%22%3A%5B%22(sign-up)%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2C%22%2Fsign-up%22%2C%22refresh%22%5D%7D%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D"
}

EMAIL_PROVIDER = "cloudmail"

# ===========================================================
# PART 1: Registration
# ===========================================================

def generate_random_name():
    length = random.randint(4, 6)
    return random.choice(string.ascii_uppercase) + ''.join(random.choice(string.ascii_lowercase) for _ in range(length - 1))

def generate_random_string(length=15):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def encode_grpc_message(field_id, string_value):
    key = (field_id << 3) | 2
    value_bytes = string_value.encode('utf-8')
    payload = struct.pack('B', key) + struct.pack('B', len(value_bytes)) + value_bytes
    return b'\x00' + struct.pack('>I', len(payload)) + payload

def encode_grpc_message_verify(email, code):
    p1 = struct.pack('B', (1 << 3) | 2) + struct.pack('B', len(email)) + email.encode('utf-8')
    p2 = struct.pack('B', (2 << 3) | 2) + struct.pack('B', len(code)) + code.encode('utf-8')
    payload = p1 + p2
    return b'\x00' + struct.pack('>I', len(payload)) + payload

JS_PATTERN = re.compile(r'/_next/static/chunks/[^\\"\s>]+\.js')
ACTION_PATTERN = re.compile(r'7f[a-fA-F0-9]{40}')

def init_action_id():
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".action_id.cache")
    start_url = f"{site_url}/sign-up"
    print("[*] Initializing action ID...")
    try:
        sess_kwargs = {"impersonate": "chrome120"}
        proxy = get_proxy()
        if proxy:
            sess_kwargs["proxies"] = proxy
        with cf_requests.Session(**sess_kwargs) as s:
            html = s.get(start_url, timeout=15).text
            key_match = re.search(r'sitekey":"(0x4[a-zA-Z0-9_-]+)"', html)
            if key_match:
                config["site_key"] = key_match.group(1)
            tree_match = re.search(r'next-router-state-tree":"([^"]+)"', html)
            if tree_match:
                config["state_tree"] = tree_match.group(1)

            js_urls = []
            for m in re.finditer(r"/_next/static/chunks/[^\s\"'>]+\.js", html):
                url = m.group(0)
                full = urllib.parse.urljoin(start_url, url)
                js_urls.append(full)

            print(f"[*] Scanning {len(js_urls)} JS files for Action ID...")
            for url in js_urls:
                try:
                    js_text = s.get(url, timeout=10).text
                    m = ACTION_PATTERN.search(js_text)
                    if m:
                        config["action_id"] = m.group(0)
                        with open(cache_file, "w") as f:
                            f.write(config["action_id"])
                        print(f"[+] Action ID: {config['action_id']}")
                        return True
                except:
                    pass
    except Exception as e:
        print(f"[-] Init error: {e}")

    if os.path.exists(cache_file):
        cached = open(cache_file).read().strip()
        if re.match(r"^7f[a-fA-F0-9]{40}$", cached):
            config["action_id"] = cached
            print(f"[+] Cached Action ID: {cached}")
            return True
    return False


def register_account(email_service, turnstile_service):
    """Register a single account. Returns (email, password, sso) or None."""
    sess_kwargs = {"impersonate": "chrome120", "proxies": get_proxy() or {}}
    try:
        with cf_requests.Session(**sess_kwargs) as session:
            try:
                session.get(site_url, timeout=10)
            except Exception as e:
                if "proxy" in str(e).lower() or "connect" in str(e).lower():
                    switch_proxy(str(e)[:60])
                pass

            password = generate_random_string()

            try:
                jwt_token, email = email_service.create_email()
            except Exception as e:
                print(f"[-] Email create error: {e}")
                return None

            if not email:
                print("[-] Email returned empty")
                return None

            print(f"[*] Registering: {email}")

            # Send verification code
            url = f"{site_url}/auth_mgmt.AuthManagement/CreateEmailValidationCode"
            data = encode_grpc_message(1, email)
            headers = {
                "content-type": "application/grpc-web+proto",
                "x-grpc-web": "1",
                "x-user-agent": "connect-es/2.1.1",
                "origin": site_url,
                "referer": f"{site_url}/sign-up?redirect=grok-com"
            }
            try:
                res = session.post(url, data=data, headers=headers, timeout=15)
                if res.status_code != 200:
                    print(f"[-] {email} Send code failed: {res.status_code}")
                    return None
            except Exception as e:
                print(f"[-] {email} Send code error: {e}")
                return None

            # Fetch verification code
            verify_code = None
            for _ in range(12):
                time.sleep(5)
                content = email_service.fetch_first_email(jwt_token)
                if content:
                    match = re.search(r"([A-Z0-9]{3}-[A-Z0-9]{3})", content)
                    if match:
                        verify_code = match.group(1).replace("-", "")
                        break
            if not verify_code:
                print(f"[-] {email} No verification code")
                return None

            # Solve Turnstile
            ts_token = None
            for attempt in range(3):
                task_id = turnstile_service.create_task(site_url, config["site_key"])
                ts_token = turnstile_service.get_response(task_id)
                if ts_token and ts_token != "CAPTCHA_FAIL":
                    break
                print(f"[-] {email} CAPTCHA retry {attempt+1}/3...")
                time.sleep(2)
            if not ts_token or ts_token == "CAPTCHA_FAIL":
                print(f"[-] {email} All CAPTCHA attempts failed")
                return None

            # Submit registration
            submit_headers = {
                "user-agent": user_agent,
                "accept": "text/x-component",
                "content-type": "text/plain;charset=UTF-8",
                "origin": site_url,
                "referer": f"{site_url}/sign-up",
                "cookie": f"__cf_bm={session.cookies.get('__cf_bm','')}",
                "next-router-state-tree": config["state_tree"],
            }
            if config["action_id"]:
                submit_headers["next-action"] = config["action_id"]

            payload = [{
                "emailValidationCode": verify_code,
                "createUserAndSessionRequest": {
                    "email": email,
                    "givenName": generate_random_name(),
                    "familyName": generate_random_name(),
                    "clearTextPassword": password,
                    "tosAcceptedVersion": "$undefined"
                },
                "turnstileToken": ts_token,
                "promptOnDuplicateEmail": True
            }]

            res = session.post(f"{site_url}/sign-up", json=payload, headers=submit_headers)

            if res.status_code == 200:
                sso = None
                for pat in [
                    r'(https://[^"\s]+set-cookie\?q=[^:"\s]+)',
                    r'(https://[^"\s]+set-cookie[^"\s]+)',
                ]:
                    m = re.search(pat, res.text)
                    if m:
                        sso_url = m.group(0).rstrip("1:").rstrip("2:").rstrip("3:")
                        try:
                            session.get(sso_url, allow_redirects=True, timeout=15)
                        except:
                            pass
                        sso = session.cookies.get("sso")
                        if sso:
                            break
                if not sso:
                    sso = session.cookies.get("sso")
                if not sso:
                    set_cookie = res.headers.get("set-cookie", "")
                    for c in set_cookie.split(","):
                        if "sso=" in c:
                            sso_val = c.split("sso=")[1].split(";")[0]
                            if sso_val:
                                sso = sso_val
                                break

                if sso:
                    print(f"[OK] Registered: {email}")
                    return (email, password, sso)
                else:
                    print(f"[-] {email} No SSO in response")
            else:
                print(f"[-] {email} Submit failed ({res.status_code})")

    except Exception as e:
        print(f"[-] Exception: {str(e)[:80]}")
    return None


# ===========================================================
# PART 2: SSO -> CPA
# ===========================================================

def _handle_consent(sess, location, sso_token, code_verifier, email=""):
    try:
        r = sess.get(location, allow_redirects=True, timeout=30,
                     headers={"User-Agent": user_agent})
    except Exception as e:
        print(f"  [{email}] Consent load failed: {e}")
        return None

    body = r.text
    action_match = re.search(r'action="([^"]+)"', body)
    inputs = re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*?)"', body, re.I)

    if not action_match:
        parsed = urllib.parse.urlparse(r.url)
        code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
        if code:
            return code
        return None

    form_action = action_match.group(1)
    form_data = {name: val for name, val in inputs}
    form_data["action"] = "approve"

    if form_action.startswith("/"):
        parsed_base = urllib.parse.urlparse(r.url)
        form_action = f"{parsed_base.scheme}://{parsed_base.netloc}{form_action}"

    try:
        r2 = sess.post(form_action, data=form_data, allow_redirects=False, timeout=30)
    except Exception as e:
        print(f"  [{email}] Consent submit failed: {e}")
        return None

    loc = r2.headers.get("Location", "")
    if "code=" in loc:
        parsed_loc = urllib.parse.urlparse(loc)
        return urllib.parse.parse_qs(parsed_loc.query).get("code", [None])[0]
    return None


def sso_to_cpa(sso_token, email=""):
    """Convert SSO cookie to CPA OAuth token via PKCE flow."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    sess = cf_requests.Session(impersonate="chrome120")
    proxy = get_proxy()
    if proxy:
        sess.proxies = proxy
    sess.cookies.set("sso", sso_token, domain=".x.ai")

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": SCOPE,
        "state": secrets.token_urlsafe(16),
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    try:
        r = sess.get(auth_url, allow_redirects=False, timeout=30,
                     headers={"User-Agent": user_agent})
    except Exception as e:
        print(f"  [{email}] Auth request failed: {e}")
        return None

    code = None
    if r.status_code in (301, 302, 303, 307, 308):
        location = r.headers.get("Location", "")
        if location.startswith("/"):
            parsed_base = urllib.parse.urlparse(r.url)
            location = f"{parsed_base.scheme}://{parsed_base.netloc}{location}"
        if REDIRECT_URI in location or "code=" in location:
            parsed_loc = urllib.parse.urlparse(location)
            params_loc = urllib.parse.parse_qs(parsed_loc.query)
            code = params_loc.get("code", [None])[0]
        elif "/consent" in location:
            code = _handle_consent(sess, location, sso_token, code_verifier, email=email)

    if not code:
        print(f"  [{email}] [FAIL] No auth code")
        return None

    try:
        r = sess.post(TOKEN_ENDPOINT, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        }, timeout=30)
    except Exception as e:
        print(f"  [{email}] Token exchange failed: {e}")
        return None

    if r.status_code != 200:
        print(f"  [{email}] [FAIL] Token error: {r.status_code}")
        return None

    data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        print(f"  [{email}] [FAIL] No access_token")
        return None

    print(f"  [{email}] [OK] CPA token obtained (expires {data.get('expires_in', '?')}s)")
    return {
        "access_token": access_token,
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 21600),
        "id_token": data.get("id_token", ""),
        "token_type": data.get("token_type", "Bearer"),
    }


# ===========================================================
# PART 3: Save files
# ===========================================================

def save_sso(email, password, sso):
    os.makedirs(KEYS_DIR, exist_ok=True)
    with open(os.path.join(KEYS_DIR, "grok.txt"), "a") as f:
        f.write(sso + "\n")
    with open(os.path.join(KEYS_DIR, "accounts.txt"), "a") as f:
        f.write(f"{email}:{password}:{sso}\n")

def save_cpa(email, cpa_data):
    safe_email = email.replace("@", "_").replace(".", "_")
    path = os.path.join(AUTH_DIR, f"xai-{safe_email}.json")
    now = time.time()
    expires_in = cpa_data.get("expires_in", 21600)
    record = {
        "type": "xai", "auth_kind": "oauth",
        "access_token": cpa_data["access_token"],
        "refresh_token": cpa_data["refresh_token"],
        "token_type": cpa_data.get("token_type", "Bearer"),
        "expires_in": expires_in,
        "expired": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + expires_in)),
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "email": email,
        "base_url": "https://cli-chat-proxy.grok.com/v1",
        "token_endpoint": TOKEN_ENDPOINT,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "disabled": False, "mint_method": "pkce", "protocol_flow": "pkce",
        "headers": {
            "X-XAI-Token-Auth": "xai-grok-cli",
            "x-grok-client-version": "0.2.93",
            "x-grok-client-identifier": "grok-shell",
        },
    }
    if cpa_data.get("id_token"):
        record["id_token"] = cpa_data["id_token"]
    os.makedirs(AUTH_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path


# ===========================================================
# PART 4: Inject 9Router
# ===========================================================

def inject_9router(email, cpa_data, name="farm"):
    def decode_jwt(token):
        try:
            p = token.split(".")[1]
            p += "=" * ((4 - len(p) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(p).decode())
        except:
            return {}

    if not os.path.exists(DB_PATH):
        print(f"  [{email}] 9Router DB not found")
        return False

    jwt = decode_jwt(cpa_data["access_token"])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {r[0] for r in cur.execute(
        "SELECT email FROM providerConnections WHERE provider='grok-cli'"
    )}
    now = datetime.now(timezone.utc).isoformat()

    data = json.dumps({
        "accessToken": cpa_data["access_token"],
        "refreshToken": cpa_data["refresh_token"],
        "displayName": name,
        "providerSpecificData": {"email": email, "userId": jwt.get("sub", ""), "authMethod": "device_code"}
    })

    if email in existing:
        print(f"  [{email}] Already in 9Router, updating...")
        cur.execute("UPDATE providerConnections SET data=?, updatedAt=? WHERE provider='grok-cli' AND email=?", (data, now, email))
    else:
        max_p = cur.execute("SELECT MAX(priority) FROM providerConnections WHERE provider='grok-cli'").fetchone()[0] or 0
        cur.execute(
            """INSERT INTO providerConnections (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), "grok-cli", "oauth", name, email, max_p + 1, 1, data, now, now)
        )

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM providerConnections WHERE provider='grok-cli'").fetchone()[0]
    conn.close()
    print(f"  [{email}] Injected to 9Router (total: {total})")
    return True


# ===========================================================
# MAIN PIPELINE
# ===========================================================

def farm_one(email_service, turnstile_service, do_inject=False, name="farm"):
    """Full flow: Register -> Save SSO -> Convert CPA -> Save CPA -> Inject."""
    # Check proxy health at start
    if not test_current_proxy():
        switch_proxy("proxy health check failed")
    print("\n" + "=" * 50)
    print("[1/5] Registering...")
    result = register_account(email_service, turnstile_service)
    if not result:
        print("[FAIL] Registration failed")
        return False
    email, password, sso = result

    print("[2/5] Saving SSO...")
    save_sso(email, password, sso)

    print("[3/5] Converting SSO -> CPA...")
    cpa_data = sso_to_cpa(sso, email)
    if not cpa_data:
        print("[FAIL] CPA conversion failed")
        return False

    print("[4/5] Saving CPA...")
    path = save_cpa(email, cpa_data)
    print(f"  Saved: {path}")

    if do_inject:
        print("[5/5] Injecting to 9Router...")
        inject_9router(email, cpa_data, name=name)
    else:
        print("[5/5] Skipped 9Router injection")

    print(f"\n{'=' * 50}")
    print(f"[DONE] {email} -- Registered + CPA converted")
    print(f"{'=' * 50}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Farm + CPA Pipeline")
    parser.add_argument("--email-provider", default=os.getenv("EMAIL_PROVIDER", "cloudmail"))
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--count", type=int, default=0, help="Target (0=infinite)")
    parser.add_argument("--inject", action="store_true", help="Inject to 9Router")
    parser.add_argument("--name", default="farm", help="Display name in 9Router")
    args = parser.parse_args()

    global EMAIL_PROVIDER
    EMAIL_PROVIDER = args.email_provider

    print("=" * 60)
    print("  Farm + CPA Pipeline")
    print("=" * 60)
    print(f"  Provider: {EMAIL_PROVIDER}")
    print(f"  Threads:  {args.threads}")
    print(f"  Target:   {args.count if args.count else 'infinite'}")
    print(f"  Inject:   {'Yes' if args.inject else 'No'}")
    print("=" * 60)

    if not init_action_id():
        print("[-] Failed to get Action ID")
        return

    from email_service import EmailService
    from YesCaptcha_service import TurnstileService
    email_service = EmailService(proxies=PROXIES or {}, provider=EMAIL_PROVIDER)
    turnstile_service = TurnstileService()

    success = 0
    failed = 0
    target = args.count
    lock = threading.Lock()

    if args.threads <= 1:
        while target == 0 or success < target:
            try:
                if farm_one(email_service, turnstile_service, do_inject=args.inject, name=args.name):
                    with lock:
                        success += 1
                else:
                    with lock:
                        failed += 1
                with lock:
                    print(f"\n[Stats] OK={success} FAIL={failed} Target={target or 'inf'}")
                time.sleep(5)
            except KeyboardInterrupt:
                break
    else:
        stop = threading.Event()

        def worker():
            nonlocal success, failed
            while not stop.is_set():
                try:
                    if target > 0:
                        with lock:
                            if success >= target:
                                break
                    if farm_one(email_service, turnstile_service, do_inject=args.inject, name=args.name):
                        with lock:
                            success += 1
                    else:
                        with lock:
                            failed += 1
                    with lock:
                        print(f"\n[Stats] OK={success} FAIL={failed} Target={target or 'inf'}")
                    time.sleep(random.uniform(3, 8))
                except Exception as e:
                    print(f"[-] Worker error: {e}")
                    time.sleep(5)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as pool:
            futures = [pool.submit(worker) for _ in range(args.threads)]
            try:
                concurrent.futures.wait(futures)
            except KeyboardInterrupt:
                stop.set()

    print(f"\n{'=' * 60}")
    print(f"  FINAL: OK={success} FAIL={failed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
