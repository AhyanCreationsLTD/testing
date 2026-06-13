import requests
import json
import re
import concurrent.futures

# 🌐 ৫/৬টি প্রীমিয়াম ওপেন সোর্স সোর্স লিস্ট
SOURCES = [
    {"type": "json", "url": "https://iptv-org.github.io/api/channels.json"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/Free-IPTV/countries/master/IPTV_PRO.m3u", "default_country": "Global", "default_category": "General"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/dtv-data/web-tv/main/playlist.m3u", "default_country": "Global", "default_category": "News"},
    {"type": "m3u", "url": "https://raw.githubusercontent.com/Clearve/iptv/main/iptv.m3u", "default_country": "Global", "default_category": "Entertainment"}
]

# M3U পার্সার ইঞ্জিন
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
            "category": category.capitalize(),
            "country": default_country
        })
    return channels

# হাই-স্পীড লাইভ লিঙ্ক ভেরিফায়ার (HEAD + GET fallback)
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
    print("[1/5] Extracting multidimensional data from 5+ repos...")
    
    for src in SOURCES:
        try:
            res = requests.get(src["url"], timeout=15)
            if res.status_code != 200: continue
            
            if src["type"] == "json":
                data = res.json()
                for ch in data:
                    country_name = ch.get("country", "Global")
                    if not country_name: country_name = "Global"
                    country_name = country_name.replace("_", " ").title()
                    
                    categories = ch.get("categories", ["General"])
                    category_name = categories[0].capitalize() if categories else "General"
                    
                    raw_list.append({
                        "name": ch.get("name", "Unknown TV"),
                        "logo": ch.get("logo", ""),
                        "url": ch.get("url", ""),
                        "category": category_name,
                        "country": country_name
                    })
            elif src["type"] == "m3u":
                m3u_channels = parse_m3u(res.text, src["default_country"], src["default_category"])
                raw_list.extend(m3u_channels)
                
        except Exception as e:
            print(f"⚠️ Error parsing {src['url']}: {e}")

    print(f"[2/5] Raw pool size: {len(raw_list)}")

    # ডুপ্লিকেট ইউআরএল ফিল্টার
    unique_urls = set()
    deduped_list = []
    for ch in raw_list:
        if ch["url"] and ch["url"] not in unique_urls:
            unique_urls.add(ch["url"])
            deduped_list.append(ch)
            
    print(f"[3/5] Cleaned pool size: {len(deduped_list)}")
    print("[4/5] Running massive parallel thread verification...")

    working_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check_stream_status, deduped_list)
        for result in results:
            if result:
                working_channels.append(result)

    print(f"✅ Verified Active Channels: {len(working_channels)}")
    print("[5/5] Re-architecting 3-tier structure & multi-format export...")

    # 💎 আপনার নতুন ৩-স্তরের ডাটাবেজ স্ট্রাকচার জেনারেশন
    final_database = {
        "Countries": {},          # ১. প্রতিটা দেশের নাম এবং তাদের category অনুযায়ী চ্যানেল
        "Global Channels": {},    # ২. একটা Global Channels with category
        "All Channels": []        # ৩. একটা সকল চ্যানেলের মেগা-লিস্ট
    }

    # কাস্টম M3U রাইটার স্ট্রিং বাফার
    m3u_content = "#EXTM3U\n"

    for ch in working_channels:
        name = ch["name"]
        logo = ch["logo"]
        url = ch["url"]
        category = ch["category"]
        country = ch["country"]

        # ৩. অল চ্যানেল মেগা-লিস্টে পুশ
        channel_min_payload = {"name": name, "logo": logo, "url": url, "category": category, "country": country}
        final_database["All Channels"].append(channel_min_payload)

        # ১. দেশের নাম ও ক্যাটাগরি অনুযায়ী সাজানো
        if country != "Global":
            if country not in final_database["Countries"]:
                final_database["Countries"][country] = {}
            if category not in final_database["Countries"][country]:
                final_database["Countries"][country][category] = []
            final_database["Countries"][country][category].append({"name": name, "logo": logo, "url": url})

        # ২. গ্লোবাল চ্যানেল ক্যাটাগরি অনুযায়ী সাজানো (সব দেশের চ্যানেলই এখানে ক্যাটাগরি অনুযায়ী মার্জ হবে)
        if category not in final_database["Global Channels"]:
            final_database["Global Channels"][category] = []
        final_database["Global Channels"][category].append({"name": name, "logo": logo, "url": url, "country": country})

        # 📄 একই সাথে আপনার নির্দেশিত .m3u ফরম্যাট বাফার তৈরি
        m3u_content += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="{category}",{name}\n{url}\n'

    # 💾 JSON ফাইল সেভ
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(final_database, f, ensure_ascii=False, indent=2)

    # 💾 M3U ফাইল সেভ
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print("🎉 System Optimized! channels.json & playlist.m3u compiled in 3-Tier Luxury Architecture!")

if __name__ == "__main__":
    main()
    
