#!/usr/bin/env python3
"""
tweet_to_square_ci.py
---------------------
Phien ban CHAY MOT LAN roi thoat — danh cho GitHub Actions (cron).
Moi lan chay: doc tweet MOI tu tai khoan X cua ban -> dang len Binance Square
-> cap nhat file state/last_id.txt (workflow se commit lai file nay).

BAO MAT: tat ca key doc tu BIEN MOI TRUONG (GitHub Secrets). KHONG hardcode key.
"""
import os
import sys
import requests
from pathlib import Path
from requests_oauthlib import OAuth1

# ---------- Cau hinh (doc tu bien moi truong) ----------
USERNAME    = os.environ.get("TWITTER_USERNAME", "").lstrip("@")
EXCLUDE     = os.environ.get("EXCLUDE", "retweets,replies")   # de "" neu muon dang ca reply/retweet
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "10"))
X_API_BASE  = os.environ.get("X_API_BASE", "https://api.twitter.com/2")  # neu loi: doi sang https://api.x.com/2
SQUARE_URL  = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"
STATE_FILE  = Path(os.environ.get("STATE_FILE", "state/last_id.txt"))


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"[LOI] Thieu bien moi truong/secret: {name}")
    return v


if not USERNAME:
    sys.exit("[LOI] Chua dat TWITTER_USERNAME (sua trong file workflow sync.yml).")

oauth = OAuth1(
    env("TWITTER_API_KEY"), env("TWITTER_API_SECRET"),
    env("TWITTER_ACCESS_TOKEN"), env("TWITTER_ACCESS_SECRET"),
)
SQUARE_KEY = env("BINANCE_SQUARE_OPENAPI_KEY")


def read_state():
    try:
        return STATE_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def write_state(v):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(v))


def get_user_id(u):
    r = requests.get(f"{X_API_BASE}/users/by/username/{u}", auth=oauth, timeout=30)
    if r.status_code != 200:
        sys.exit(f"[LOI] Khong lay duoc user id ({r.status_code}): {r.text[:300]}")
    return r.json()["data"]["id"]


def get_new_tweets(uid, since):
    params = {"max_results": MAX_RESULTS, "tweet.fields": "created_at"}
    if EXCLUDE:
        params["exclude"] = EXCLUDE
    if since:
        params["since_id"] = since
    r = requests.get(f"{X_API_BASE}/users/{uid}/tweets", params=params, auth=oauth, timeout=30)
    if r.status_code != 200:
        print(f"[!] Loi doc tweet ({r.status_code}): {r.text[:200]}")
        return []
    return list(reversed(r.json().get("data", [])))  # dao moi->cu thanh cu->moi


def post_to_square(text):
    headers = {
        "X-Square-OpenAPI-Key": SQUARE_KEY,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill",
    }
    r = requests.post(SQUARE_URL, headers=headers, json={"bodyTextOnly": text}, timeout=30)
    try:
        j = r.json()
    except Exception:
        print(f"[!] Square tra ve khong phai JSON ({r.status_code})")
        return
    if j.get("code") == "000000":
        pid = (j.get("data") or {}).get("id")
        print(f"[OK] Da dang: https://www.binance.com/square/post/{pid}" if pid
              else "[OK] Co ve da dang (khong co link tra ve).")
    else:
        print(f"[!] Square tu choi: code={j.get('code')} msg={j.get('message')}")


def main():
    uid = get_user_id(USERNAME)
    last = read_state()

    # Lan dau (chua co state): lay moc tu tweet moi nhat, KHONG dang lai tweet cu.
    if last is None:
        base = get_new_tweets(uid, None)
        if base:
            write_state(base[-1]["id"])
            print(f"[i] Lan dau chay: dat moc tu tweet moi nhat (id={base[-1]['id']}).")
            print("    Tu gio chi tweet MOI sau thoi diem nay moi duoc dang.")
        else:
            print("[i] Lan dau chay: chua thay tweet nao.")
        return

    tweets = get_new_tweets(uid, last)
    if not tweets:
        print("[i] Khong co tweet moi.")
        return
    for tw in tweets:
        t = tw.get("text", "").strip()
        print(f"-> Tweet moi: {t[:80]}")
        post_to_square(t)
        write_state(tw["id"])  # cap nhat sau MOI bai -> khong dang trung neu chay loi giua chung


if __name__ == "__main__":
    main()
