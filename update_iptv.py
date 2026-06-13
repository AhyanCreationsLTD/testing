import requests
import json
import re
import concurrent.futures

# 🌐 ৫/৬টি বড় এবং পপুলার ওপেন সোর্স আইপিটিভি রিপোজিটরির সোর্স লিস্ট
SOURCES = [
    {"type": "json", "url": "https://iptv-org.github.io/api/channels.json"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/Free-IPTV/countries/master/IPTV_PRO.m3u", "default_country": "Global", "default_category": "General"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/dtv-data/web-tv/main/playlist.m3u", "default_country": "Global", "default_category": "News"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/Clearve/iptv/main/iptv.m3u", "default_country": "Global", "default_category": "Entertainment"}
]

def parse_m3u(m3u_text, default_country, default_category):
    channels = []
    pattern = r'#EXTINF:-1\s*(?:tvg-name="([^"]+)")?(?:.*?tvg-logo="([^"]+)")?(?:.*?group-title="([^"]+)")?,(.*)\n(https?://[^\s]+)'
    matches = re.findall(pattern, m3u_text, re.IGNORECASE)
    
    for match in matches:
        tvg_name, tvg_logo, group_title, display_name, stream_url = match
        name = tvg_name.strip() if tvg_name else display_name.strip()
        category = group_title.strip() if group_title else default_category
        
        channels.append({
            "name": name,
            "logo": tvg_logo.strip() if tvg_logo else "",
            "url": stream_url.strip(),
            "category": category,
            "country": default_country
        })
    return channels

def check_stream_status(channel):
    try:
        response = requests.head(channel["url"], timeout=2.0, allow_redirects=True)
        if response.status_code in [200, 201, 202, 301, 302]:
            return channel
    except:
        try:
            response = requests.get(channel["url"], timeout=2.0, stream=True)
            if response.status_code == 200:
                return channel
        except:
            pass
    return None

def main():
    raw_list = []
    print("[1/4] Gathering streams from 5+ premium open-source repos...")
    
    for src in SOURCES:
        try:
            res = requests.get(src["url"], timeout=15)
            if res.status_code != 200: continue
            
            if src["type"] == "json":
                data = res.json()
                for ch in data:
                    country_name = ch.get("country", "Global")
                    if not country_name: country_name = "Global"
                    
                    categories = ch.get("categories", ["General"])
                    category_name = categories[0] if categories else "General"
                    
                    raw_list.append({
                        "name": ch.get("name", "Unknown TV"),
                        "logo": ch.get("logo", ""),
                        "url": ch.get("url", ""),
                        "category": category_name.capitalize(),
                        "country": country_name.replace("_", " ").title()
                    })
            elif src["type"] == "m3u":
                m3u_channels = parse_m3u(res.text, src["default_country"], src["default_category"])
                raw_list.extend(m3u_channels)
                
        except Exception as e:
            print(f"⚠️ Error reading source {src['url']}: {e}")

    print(f"[2/4] Total raw channels fetched: {len(raw_list)}")

    unique_urls = set()
    deduped_list = []
    for ch in raw_list:
        if ch["url"] and ch["url"] not in unique_urls:
            unique_urls.add(ch["url"])
            deduped_list.append(ch)
            
    print(f"[3/4] Deduplicated list size: {len(deduped_list)}")
    print("[4/4] Mass-testing dead links using high-speed Multi-Threading...")

    working_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check_stream_status, deduped_list)
        for result in results:
            if result:
                working_channels.append(result)

    print(f"✅ Live Verification Complete! Active Channels: {len(working_channels)}")

    final_database = {}
    for ch in working_channels:
        country = ch["country"]
        category = ch["category"]
        
        if country not in final_database:
            box = final_database[country] = {}
        if category not in final_database[country]:
            final_database[country][category] = []
            
        final_database[country][category].append({
            "name": ch["name"],
            "logo": ch["logo"],
            "url": ch["url"]
        })

    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(final_database, f, ensure_ascii=False, indent=2)
        
    print("🎉 Master database successfully generated and saved to channels.json!")

if __name__ == "__main__":
    main()
                                    
