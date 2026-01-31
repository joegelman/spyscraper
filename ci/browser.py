# ci/browser.py
from playwright.sync_api import sync_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def with_browser(fn, headless: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME,
            headless=headless,
        )
        try:
            return fn(browser)
        finally:
            browser.close()

