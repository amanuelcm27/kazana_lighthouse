from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
load_dotenv() 

 
API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("GOOGLE_CX")

def google_search(query, num_results=10):
    service = build("customsearch", "v1", developerKey=API_KEY)
    
    res = service.cse().list(
        q=query,
        cx=SEARCH_ENGINE_ID,
        num=num_results  # max 10 per request
    ).execute()
    
    results = []
    for item in res.get("items", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet")
        })
    return results

if __name__ == "__main__":
    query = "site:worldbank.org procurement OR tender OR project"
    search_results = google_search(query, num_results=10)
    
    for r in search_results:
        print(r)
