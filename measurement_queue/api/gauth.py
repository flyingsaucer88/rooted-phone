"""Google service-account access tokens, pure Python.

google-auth is not installable on this device: it hard-requires `cryptography`,
whose Termux build targets python3.14 while the automation runs on python3.13,
and whose wheel needs a Rust toolchain on armv7l.  Minting the assertion by hand
with `rsa` (pure Python) keeps the existing interpreter untouched.

Read-only by construction: the only scopes this module will request are the
Google *.readonly scopes, and the token request itself goes through the guard.
"""
import base64, json, os, time

READONLY_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=")


def _load_key(pem_text):
    """Accept a PKCS#8 ('BEGIN PRIVATE KEY') or PKCS#1 service-account key."""
    import rsa
    if "BEGIN RSA PRIVATE KEY" in pem_text:
        return rsa.PrivateKey.load_pkcs1(pem_text.encode())
    body = "".join(l for l in pem_text.splitlines() if "-----" not in l)
    der = base64.b64decode(body)
    from pyasn1.codec.der import decoder
    info, _ = decoder.decode(der)
    return rsa.PrivateKey.load_pkcs1(bytes(info[2]), format="DER")


def sign_assertion(sa, scopes=None, now=None):
    """Build the RS256 JWT bearer assertion for a service-account key dict."""
    import rsa
    now = int(now or time.time())
    scopes = scopes or READONLY_SCOPES
    for s in scopes:
        if not s.endswith(".readonly"):
            raise ValueError("refusing non-readonly scope: %s" % s)
    header = {"alg": "RS256", "typ": "JWT", "kid": sa.get("private_key_id")}
    claims = {"iss": sa["client_email"], "scope": " ".join(scopes),
              "aud": TOKEN_URI, "iat": now, "exp": now + 3600}
    signing_input = _b64u(json.dumps(header).encode()) + b"." + _b64u(json.dumps(claims).encode())
    sig = rsa.sign(signing_input, _load_key(sa["private_key"]), "SHA-256")
    return (signing_input + b"." + _b64u(sig)).decode()


class GoogleToken:
    """Caches one access token for its lifetime; refreshes a minute early."""

    def __init__(self, sa, guard, scopes=None):
        self.sa, self.guard, self.scopes = sa, guard, (scopes or READONLY_SCOPES)
        self._tok, self._exp = None, 0

    @property
    def identity(self):
        return self.sa.get("client_email", "unknown-service-account")

    def token(self):
        if self._tok and time.time() < self._exp - 60:
            return self._tok
        r = self.guard.call(
            "google", "oauth2.token", "POST", TOKEN_URI,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                  "assertion": sign_assertion(self.sa, self.scopes)})
        if r.status_code != 200:
            raise RuntimeError("google token mint failed: HTTP %s" % r.status_code)
        d = r.json()
        self._tok, self._exp = d["access_token"], time.time() + int(d.get("expires_in", 3600))
        return self._tok

    def headers(self):
        return {"Authorization": "Bearer " + self.token()}


def demo():
    """Round-trip the assertion against a throwaway key; no network, no secrets."""
    import rsa
    key = os.environ.get("GAUTH_DEMO_KEY")
    if not key:
        print("gauth demo SKIPPED (set GAUTH_DEMO_KEY to a throwaway PKCS#8 PEM)")
        return
    sa = {"client_email": "demo@example.iam.gserviceaccount.com",
          "private_key_id": "demo", "private_key": key}
    tok = sign_assertion(sa, now=1700000000)
    h, c, s = tok.split(".")
    pad = lambda x: x + "=" * (-len(x) % 4)
    assert json.loads(base64.urlsafe_b64decode(pad(h)))["alg"] == "RS256"
    claims = json.loads(base64.urlsafe_b64decode(pad(c)))
    assert claims["aud"] == TOKEN_URI and claims["exp"] - claims["iat"] == 3600
    assert all(x.endswith(".readonly") for x in claims["scope"].split())
    priv = _load_key(key)
    pub = rsa.PublicKey(priv.n, priv.e)
    rsa.verify(("%s.%s" % (h, c)).encode(), base64.urlsafe_b64decode(pad(s)), pub)
    try:
        sign_assertion(dict(sa), scopes=["https://www.googleapis.com/auth/analytics.edit"])
        raise AssertionError("write scope was not refused")
    except ValueError:
        pass
    print("gauth demo OK — RS256 assertion verifies, write scopes refused")


if __name__ == "__main__":
    demo()
