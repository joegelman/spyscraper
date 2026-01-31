from ci.browser import with_browser
from ci.fetch import fetch_http, fetch_rendered, needs_browser

url = "https://www.sardine.ai/"

r = fetch_http(url)
print("http:", r.links_count, len(r.text), r.url)

def run(browser):
    rr = fetch_rendered(url, browser)
    print("rendered:", rr.links_count, len(rr.text))

if needs_browser(r):
    with_browser(run)
else:
    print("browser not needed for this page")

