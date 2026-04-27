#!/usr/bin/env python3
"""
mark-read: list-unread-gmail で表示した番号のメールを既読にする。
list-unread-gmail が保存したキャッシュ /tmp/gmail_unread_list.json を参照する。
"""
import json
import sys
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print(json.dumps({
        "error": "playwright module not found. Install with: pip3 install playwright && playwright install chromium"
    }, ensure_ascii=False))
    sys.exit(1)

CDP_URL = "http://127.0.0.1:9222"
CACHE_FILE = "/tmp/gmail_unread_list.json"


def load_cache() -> list[dict]:
    p = Path(CACHE_FILE)
    if not p.exists():
        print("ERROR: メールリストが見つかりません。先に /list-unread-gmail を実行してください。", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def mark_email_read(page, email: dict) -> None:
    """対象メールを開いて既読にする。"""
    subject = email["subject"]
    thread_id = email.get("thread_id", "")

    # Gmail の Important ページに移動
    page.goto("https://mail.google.com/mail/u/0/#imp", wait_until="domcontentloaded", timeout=15000)

    try:
        page.wait_for_selector("div[role='main']", timeout=10000)
    except PlaywrightTimeout:
        print("ERROR: Gmailの読み込みがタイムアウトしました。", file=sys.stderr)
        sys.exit(1)

    clicked = False

    # thread_id がある場合は属性で直接クリック
    if thread_id:
        row = page.query_selector(f"tr[data-thread-id='{thread_id}']")
        if row:
            row.click()
            clicked = True

    # フォールバック: 件名テキストで探す
    if not clicked:
        rows = page.query_selector_all("tr.zE")
        for row in rows:
            subj_el = row.query_selector("span.bqe, span.bog")
            if subj_el and subject in subj_el.inner_text():
                row.click()
                clicked = True
                break

    if not clicked:
        print(f"ERROR: メール「{subject}」が見つかりませんでした。既読済みの可能性があります。", file=sys.stderr)
        sys.exit(1)

    # メール本文が表示されるまで待つ（開いた時点で既読になる）
    try:
        page.wait_for_selector("div.a3s", timeout=8000)
    except PlaywrightTimeout:
        pass  # 開けていれば問題なし

    print(f"既読にしました: [{email['no']}] {subject}")


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 main.py <番号>")
        print("例: python3 main.py 3")
        sys.exit(1)

    try:
        no = int(sys.argv[1])
    except ValueError:
        print(f"ERROR: 番号を整数で指定してください (指定値: {sys.argv[1]})", file=sys.stderr)
        sys.exit(1)

    emails = load_cache()
    target = next((e for e in emails if e["no"] == no), None)
    if target is None:
        print(f"ERROR: 番号 {no} のメールが見つかりません。", file=sys.stderr)
        print(f"有効な番号: {[e['no'] for e in emails]}", file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"ERROR: ブラウザに接続できません ({CDP_URL}): {e}", file=sys.stderr)
            sys.exit(1)

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        mark_email_read(page, target)


if __name__ == "__main__":
    main()
