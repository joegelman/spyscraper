from ci.browser import with_browser

def run(browser):
    page = browser.new_page()
    page.goto("https://example.com", wait_until="domcontentloaded")
    print(page.title())
    page.close()

with_browser(run)

