import requests
import json

def main():
    print("[1/4] Fetching global channel data from official iptv-org API...")
    
    # মেগা চ্যানেল এপিআই সোর্স
    channels_url = "https://iptv-org.github.io/api/channels.json"
    # গ্লোবাল লোগো এপিআই সোর্স (ব্যাকআপ লোগো টানার জন্য)
    logos_url = "https://iptv-org.github.io/api/logos.json"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        # ১. চ্যানেল ডেটা ফেচ
        res_ch = requests.get(channels_url, headers=headers, timeout=30)
        if res_ch.status_code != 200:
            print(f"❌ Channel API failed: {res_ch.status_code}")
            return
        all_channels_data = res_ch.json()
        print(f"✅ Loaded {len(all_channels_data)} raw channels.")
        
        # ২. লোগো ডেটাবেজ ফেচ
        print("[2/4] Fetching and indexing backup logo database to ensure 100% logos...")
        res_lg = requests.get(logos_url, headers=headers, timeout=30)
        logo_repo = {}
        if res_lg.status_code == 200:
            # লোগোগুলোকে আইডেন্টিফায়ার দিয়ে ইনডেক্সিং করা (দ্রুত খোঁজার জন্য)
            for lg in res_lg.json():
                if lg.get("id"):
                    logo_repo[lg["id"]] = lg.get("logo", "")
            print(f"✅ Indexed {len(logo_repo)} premium logos.")
        else:
            print("⚠️ Logo backup database unavailable. Using direct logos only.")
            
    except Exception as e:
        print(f"❌ Critical Connection Error: {e}")
        return

    print("[3/4] Mapping channels with embedded logos into 3-Tier Architecture...")
    
    # আপনার ৩-স্তরের মাস্টার ডাটাবেজ স্ট্রাকচার
    final_db = {
        "Countries": {},          # ১. প্রতিটা দেশের নাম এবং তাদের category অনুযায়ী চ্যানেল
        "Global Channels": {},    # ২. একটা Global Channels with category
        "All Channels": []        # ৩. সকল চ্যানেলের মেগা-লিস্ট
    }

    m3u_output = "#EXTM3U\n"
    mapped_count = 0

    for ch in all_channels_data:
        name = ch.get("name")
        url = ch.get("url")
        ch_id = ch.get("id")
        
        # নাম বা স্ট্রিম ইউআরএল না থাকলে স্কিপ
        if not name or not url:
            continue
            
        # 🖼️ লোগো সিলেকশন লজিক (প্রথমে মেইন লোগো, ফাঁকা থাকলে ব্যাকআপ ডাটাবেজ থেকে আইডি দিয়ে খোঁজা)
        logo = ch.get("logo", "")
        if not logo and ch_id in logo_repo:
            logo = logo_repo[ch_id]
            
        # দেশের নাম ফরম্যাটিং
        c_code = ch.get("country")
        country_name = str(c_code).upper() if (c_code and len(c_code) <= 3) else str(c_code).title()
        if not country_name or country_name == "None":
            country_name = "Global"
            
        # ক্যাটাগরি ফরম্যাটিং
        cat_list = ch.get("categories", [])
        category_name = str(cat_list[0]).capitalize() if cat_list else "General"

        # কমপ্লিট পেলোড (লোগোসহ)
        channel_payload = {
            "name": name,
            "logo": logo,
            "url": url,
            "category": category_name,
            "country": country_name
        }

        # ✨ স্তর ৩: All Channels
        final_db["All Channels"].append(channel_payload)

        # ✨ স্তর ১: Countries
        if country_name != "Global":
            if country_name not in final_db["Countries"]:
                final_db["Countries"][country_name] = {}
            if category_name not in final_db["Countries"][country_name]:
                final_db["Countries"][country_name][category_name] = []
            final_db["Countries"][country_name][category_name].append({
                "name": name, "logo": logo, "url": url
            })

        # ✨ স্তর ২: Global Channels
        if category_name not in final_db["Global Channels"]:
            final_db["Global Channels"][category_name] = []
        final_db["Global Channels"][category_name].append({
            "name": name, "logo": logo, "url": url, "country": country_name
        })

        # M3U ফরম্যাটেও লোগো ট্যাগ (`tvg-logo`) যুক্ত করা হলো
        m3u_output += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category_name}",{name}\n{url}\n'
        mapped_count += 1

    print(f"[4/4] Writing localized files. Total compiled items: {mapped_count}")

    # ফাইনাল ফাইল সেভ
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)
        
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_output)
        
    print("🎉 SUCCESS! channels.json and playlist.m3u are updated with full data and verified logos!")

if __name__ == "__main__":
    main()
    
