"""READ-ONLY check of the Meta secrets (GET requests only, nothing is posted).
Prints names and yes/no results only. The token is never printed (any error text is scrubbed first)."""
import os, sys
import requests

G = "https://graph.facebook.com/v21.0"
TOK = os.environ.get("META_PAGE_TOKEN", "").strip()
PAGE = os.environ.get("FB_PAGE_ID", "").strip()
IG = os.environ.get("IG_USER_ID", "").strip()

def scrub(s):
    s = str(s)
    return s.replace(TOK, "<token>") if TOK else s

def get(path, **params):
    r = requests.get(f"{G}/{path}", params={**params, "access_token": TOK}, timeout=60)
    try:
        j = r.json()
    except Exception:
        j = {"error": {"message": "non-JSON answer, HTTP %s" % r.status_code}}
    return r.status_code, j

def err(j):
    e = j.get("error", {})
    return "code=%s subcode=%s type=%s msg=%s" % (e.get("code"), e.get("error_subcode"), e.get("type"), scrub(e.get("message", ""))[:240])

def main():
    ok = True
    for name, val in (("META_PAGE_TOKEN", TOK), ("FB_PAGE_ID", PAGE), ("IG_USER_ID", IG)):
        print("secret %-16s %s" % (name, "present" if val else "MISSING"))
        ok = ok and bool(val)
    if not ok:
        print("::error::a Meta secret is missing"); return 1

    # 1. the token itself: a Page token answers /me with the Page
    s, j = get("me", fields="id,name")
    if s != 200:
        print("::error::META token check FAILED: " + err(j)); return 1
    print("token works. /me is: %s (id ends ...%s)" % (j.get("name"), str(j.get("id"))[-4:]))
    print("/me id equals FB_PAGE_ID: %s" % (str(j.get("id")) == PAGE))

    # 2. the Facebook Page
    s, j = get(PAGE, fields="name,fan_count,instagram_business_account")
    if s != 200:
        print("::error::Facebook Page read FAILED: " + err(j)); ok = False
    else:
        print("Facebook Page: %s, followers/likes: %s" % (j.get("name"), j.get("fan_count")))
        linked = (j.get("instagram_business_account") or {}).get("id")
        print("Page has a linked Instagram account: %s; it equals IG_USER_ID: %s" % (bool(linked), str(linked) == IG))

    # 3. the Instagram account
    s, j = get(IG, fields="username,media_count")
    if s != 200:
        print("::error::Instagram account read FAILED: " + err(j)); ok = False
    else:
        print("Instagram account: @%s, posts: %s" % (j.get("username"), j.get("media_count")))

    # 4. Instagram publishing quota (read-only)
    s, j = get(f"{IG}/content_publishing_limit", fields="quota_usage,config")
    if s == 200 and j.get("data"):
        d = j["data"][0]
        print("Instagram publish quota used (24h): %s of %s" % (d.get("quota_usage"), (d.get("config") or {}).get("quota_total")))
    else:
        print("Instagram publish quota: could not read (%s)" % err(j))

    # 5. granted permissions (only works for some token types; informational)
    s, j = get("me/permissions")
    if s == 200 and j.get("data"):
        print("granted permissions:", ", ".join(sorted(x["permission"] for x in j["data"] if x.get("status") == "granted")))
    else:
        print("permission list not available for this token type (normal for a Page token)")
    print("RESULT:", "OK" if ok else "PROBLEM")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
