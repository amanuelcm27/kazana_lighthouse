import requests
from bs4 import BeautifulSoup

class StaticScraper:
    def __init__(self, url):
        self.url = url

    def fetch_page(self, url=None):
        """Fetch HTML content from a URL (defaults to seed URL)."""
        target_url = url or self.url
        response = requests.get(target_url)
        response.raise_for_status()
        return response.text

    def find_hub_links(self, html):
        """Find procurement/project-related hub links on the seed page."""
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]

            if any(word in text.lower() for word in ["tender", "procurement", "project", "opportunity"]):
                links.append({
                    "title": text,
                    "url": href if href.startswith("http") else self.url.rstrip("/") + "/" + href.lstrip("/")
                })
        return links

    def parse_opportunity_listings(self, html):
        """Dig into deeper pages and extract actual opportunity listings."""
        soup = BeautifulSoup(html, "html.parser")
        opportunities = []

        # Example: many listings are inside <a> or <li> with keywords
        for item in soup.find_all(["a", "li"]):
            text = item.get_text(strip=True)
            href = item.get("href")

            if text and any(word in text.lower() for word in ["tender", "procurement", "contract", "opportunity", "rfp", "project"]):
                opportunities.append({
                    "title": text,
                    "url": href if href and href.startswith("http") else None
                })
        return opportunities

    def run(self):
        # Step 1: Fetch main page
        main_html = self.fetch_page()

        # Step 2: Find hub links
        hub_links = self.find_hub_links(main_html)

        all_opportunities = []
        for hub in hub_links:
            try:
                print(f"Digging into: {hub['url']}")
                sub_html = self.fetch_page(hub["url"])
                listings = self.parse_opportunity_listings(sub_html)
                all_opportunities.extend(listings)
            except Exception as e:
                print(f"Failed to scrape {hub['url']}: {e}")

        return all_opportunities


if __name__ == "__main__":
    scraper = StaticScraper("https://www.worldbank.org/en/projects-operations/procurement")
    results = scraper.run()

    for opp in results[:15]:  # print first 15
        print(opp)
