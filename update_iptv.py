import requests
import json

def main():
    print("[1/3] Fetching Master Database from official iptv-org grouped API...")
    
    # 🌍 এটি হলো iptv-org এর আসল মাস্টার রিলেশন ডাটাবেজ (যেখানে দেশ, লোগো, ক্যাটাগরি সব রেডিমেড থাকে)
    api_url = "https://iptv-org.github.io/api/streams.json"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(api_url, headers=headers, timeout=30)
        if res.status_code != 200:
            print(f"❌ Connection failed: {res.status_code}")
            return
        streams_data = res.json()
        print(f"✅ Successfully loaded {len(streams_data)} global raw streams.")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    print("[2/3] Mapping into Clean 3-Tier OTT Architecture (No Garbage Codes)...")
    
    final_db = {
        "Countries": {},          
        "Global Channels": {},    
        "All Channels": []        
    }
    
    m3u_output = "#EXTM3U\n"
    success_count = 0

    # 🗺️ দেশের ফালতু ২ অক্ষরের কোডকে আসল নামে রূপান্তর করার জন্য একটি ডিকশনারি
    country_map = {
        "BD": "Bangladesh", "IN": "India", "US": "United States", "UK": "United Kingdom",
        "GB": "United Kingdom", "PK": "Pakistan", "SA": "Saudi Arabia", "AE": "UAE",
        "CA": "Canada", "AU": "Australia", "FR": "France", "DE": "Germany",
        "IT": "Italy", "JP": "Japan", "CN": "China", "RU": "Russia", "BR": "Brazil"
    }

    for stream in streams_data:
        url = stream.get("url")
        channel_id = stream.get("channel") # মূল চ্যানেল আইডি (যেমন: attnbangla.bd)
        
        if not url or not channel_id:
            continue

        # 🖼️ ১০০% জেনুইন লোগো ফিল্টারিং
        # প্রথমে এপিআই এর লোগো দেখবে, না থাকলে গিটহাবের র-লোগো ডিরেক্টরি থেকে অরিজিনাল লোগো আনবে
        logo = stream.get("logo")
        if not logo:
            logo = f"https://iptv-org.github.io/images/channels/{channel_id}.png"

        # 🌍 দেশের নাম ফিক্সিং লজিক
        raw_country = "Global"
        if "." in channel_id:
            parts = channel_id.split(".")
            possible_code = parts[-1].upper() # আইডির শেষের অংশ সাধারণত দেশের কোড হয়
            if len(possible_code) == 2:
                raw_country = possible_code

        # যদি আমাদের ম্যাপে দেশ থাকে তবে পুরো নাম বসবে, নাহলে কোডটাই সুন্দর করে বসবে
        country_name = country_map.get(raw_country, raw_country)
        if country_name == "Global" and stream.get("country"):
            country_name = country_map.get(stream.get("country").upper(), stream.get("country").title())

        # 🗂️ ক্যাটাগরি ফিক্সিং
        # এপিআই থেকে ক্যাটাগরি লিস্ট আকারে আসে, না থাকলে 'General'
        categories = stream.get("categories", [])
        category_name = str(categories[0]).capitalize() if categories else "General"
        if category_name == "None" or not category_name:
            category_name = "General"

        # চ্যানেলের সুন্দর নাম (আইডি থেকে ডট এবং ফালতু এক্সটেনশন রিমুভ)
        clean_name = channel_id.split(".")[0].replace("-", " ").title()

        channel_payload = {
            "name": clean_name,
            "logo": logo,
            "url": url,
            "category": category_name,
            "country": country_name
        }

        # স্তর ৩: All Channels
        final_db["All Channels"].append(channel_payload)

        # স্তর ১: Countries
        if country_name != "Global":
            if country_name not in final_db["Countries"]:
                final_db["Countries"][country_name] = {}
            if category_name not in final_db["Countries"][country_name]:
                final_db["Countries"][country_name][category_name] = []
            final_db["Countries"][country_name][category_name].append({
                "name": clean_name, "logo": logo, "url": url
            })

        # স্তর ২: Global Channels
        if category_name not in final_db["Global Channels"]:
            final_db["Global Channels"][category_name] = []
        final_db["Global Channels"][category_name].append({
            "name": clean_name, "logo": logo, "url": url, "country": country_name
        })

        # M3U জেনারেশন
        m3u_output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category_name}",{clean_name}\n{url}\n'
        success_count += 1

    print(f"[3/3] Saving databases. Successfully mapped items: {success_count}")

    if success_count > 0:
        with open("channels.json", "w", encoding="utf-8") as f:
            json.dump(final_db, f, ensure_ascii=False, indent=2)
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_output)
        print("🎉 SUCCESS! Clean Database Compiled Flawlessly!")

if __name__ == "__main__":
    main()
    
