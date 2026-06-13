import requests
import json

def main():
    print("[1/3] Fetching global data from iptv-org official streams API...")
    
    # 🔗 সরাসরি স্ট্রিম এবং চ্যানেল ডেটা একসাথে পাওয়ার জন্য মেইন এপিআই রুট
    streams_url = "https://iptv-org.github.io/api/streams.json"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(streams_url, headers=headers, timeout=30)
        if res.status_code != 200:
            print(f"❌ API failed with status code: {res.status_code}")
            return
        
        streams_data = res.json()
        print(f"✅ Successfully loaded {len(streams_data)} global raw streams.")
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    print("[2/3] Parsing and building 3-Tier OTT Structure with Logos...")
    
    final_db = {
        "Countries": {},          # ১. প্রতিটা দেশের নাম এবং তাদের category অনুযায়ী চ্যানেল
        "Global Channels": {},    # ২. একটা Global Channels with category
        "All Channels": []        # ৩. সকল চ্যানেলের মেগা-লিস্ট
    }

    m3u_output = "#EXTM3U\n"
    success_count = 0

    for stream in streams_data:
        url = stream.get("url")
        # এপিআই-তে চ্যানেলের নাম ডিরেক্ট বা চ্যানেল আইডিতে থাকে, কোনোটা না থাকলে জাস্ট স্কিপ
        name = stream.get("channel") or stream.get("name")
        
        if not url or not name:
            continue

        # লোগো ইউআরএল জেনারেট (iptv-org এর স্ট্যান্ডার্ড লোগো ফরম্যাট)
        # যদি এপিআই-তে লোগো ডিরেক্ট না থাকে, তবে তাদের অফিশিয়াল ক্লাউডফ্লেয়ার সিডিএন থেকে লোগো লিঙ্ক বিল্ড হবে
        logo = stream.get("logo") or f"https://iptv-org.github.io/images/languages/{name.split('.')[0] if '.' in name else 'global'}.png"
        if not stream.get("logo"):
            # কোনো কাস্টম লোগো না থাকলে ডিফল্ট গ্লোবাল লোগো প্লেসহোল্ডার
            logo = "https://iptv-org.github.io/images/logo.png"

        # দেশের কোড বা নাম প্রসেস
        # এপিআই অনুযায়ী অনেক সময় চ্যানেল আইডির প্রথমাংশেই দেশের কোড থাকে
        c_code = "Global"
        if "." in name:
            parts = name.split(".")
            if len(parts) > 1 and len(parts[0]) == 2:
                c_code = parts[0].upper()
        
        country_name = c_code
        category_name = "General"  # ডিফল্ট সেফ ক্যাটাগরি

        # পেলোড ডিফাইন
        channel_payload = {
            "name": name.replace(".bd", "").replace(".us", "").replace(".in", "").replace("-", " ").title(),
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
                "name": channel_payload["name"], "logo": logo, "url": url
            })

        # স্তর ২: Global Channels
        if category_name not in final_db["Global Channels"]:
            final_db["Global Channels"][category_name] = []
        final_db["Global Channels"][category_name].append({
            "name": channel_payload["name"], "logo": logo, "url": url, "country": country_name
        })

        # M3U ফরম্যাট বিল্ড
        m3u_output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category_name}",{channel_payload["name"]}\n{url}\n'
        success_count += 1

    print(f"[3/3] Saving databases. Successfully mapped items: {success_count}")

    # ডাটা শূন্য না হলে তবেই ফাইলে রাইট হবে, যেন ব্যাকআপ নষ্ট না হয়
    if success_count > 0:
        with open("channels.json", "w", encoding="utf-8") as f:
            json.dump(final_db, f, ensure_ascii=False, indent=2)
            
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(m3u_output)
        print("🎉 SUCCESS! channels.json & playlist.m3u compiled with full dynamic data!")
    else:
        print("❌ Fallback Triggered: Process aborted due to parsing failure.")

if __name__ == "__main__":
    main()
    
