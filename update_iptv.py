import json
import os
import requests
import pycountry

CHANNELS_API = "https://iptv-org.github.io/api/channels.json"
STREAMS_API = "https://iptv-org.github.io/api/streams.json"

def get_country_name(code):
    """২ অক্ষরের আইএসও কোড থেকে ডাইনামিকালি দেশের সুন্দর নাম বের করার ফাংশন"""
    if not code:
        return None
    try:
        country = pycountry.countries.get(alpha_2=code.upper())
        if country:
            name = country.name
            # দেশের অফিশিয়াল নাম অনেক বড় হলে (যেমন: "Iran, Islamic Republic of") তা ছোট করা
            if " , " in name:
                name = name.split(" , ")[0]
            if " (" in name:
                name = name.split(" (")[0]
            return name
    except Exception:
        pass
    return None

def is_stream_alive(url):
    """লিংকটি সচল নাকি ডেড তা ২ সেকেন্ডের টাইমআউট দিয়ে রিয়েল-টাইমে চেক করার ফাংশন"""
    try:
        # শুধু হেডার চেক করবে (পুরো ভিডিও ডাউনলোড করবে না, তাই ফাস্ট হবে)
        response = requests.head(url, timeout=2.0, allow_redirects=True)
        if response.status_code == 200:
            return True
        
        # কিছু টিভি সার্ভার HEAD রিকোয়েস্ট ব্লক করে, তাদের জন্য GET ট্রাই করবে সামান্য ডাটার জন্য
        if response.status_code in [403, 405]:
            response_get = requests.get(url, timeout=2.0, stream=True)
            if response_get.status_code == 200:
                return True
    except Exception:
        pass
    return False

def create_m3u_content(channel_list):
    """প্লেলিস্ট ফাইল জেনারেট করার জন্য স্ট্যান্ডার্ড M3U ফরম্যাট টেমপ্লেট"""
    m3u_text = "#EXTM3U\n"
    for ch in channel_list:
        m3u_text += f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch.get("country", "")} - {ch.get("category", "")}",{ch["name"]}\n'
        m3u_text += f'{ch["url"]}\n'
    return m3u_text

def fetch_and_generate_dynamic_data():
    print("Fetching global databases from iptv-org...")
    channels = requests.get(CHANNELS_API).json()
    streams = requests.get(STREAMS_API).json()

    # সচল স্ট্রিমগুলোর একটি আইডি ম্যাপ তৈরি করা
    stream_map = {stream['channel']: stream['url'] for stream in streams if 'channel' in stream and 'url' in stream}
    
    main_json_data = {}
    global_category_data = {}
    all_flat_channels = []

    print("Verifying live streams and sorting by country/category (Removing dead links)...")
    checked_count = 0
    
    for ch in channels:
        country_code = ch.get('country')
        ch_id = ch.get('id')

        # শুধু স্ট্রিম লিংক যুক্ত সচল চ্যানেলগুলো প্রসেস করা হবে
        if ch_id in stream_map:
            url = stream_map[ch_id]
            
            # 🔴 লাইভ ডেড লিংক চেকার (কোনো লিংক রেসপন্স না করলে বাফারিং কমানোর জন্য বাদ যাবে)
            if not is_stream_alive(url):
                continue 
                
            country_name = get_country_name(country_code)
            if not country_name:
                continue 
                
            category = ch.get('categories')[0].title() if ch.get('categories') else 'Other'
            
            channel_info = {
                "id": ch_id,
                "name": ch.get('name'),
                "logo": ch.get('logo'),
                "category": category,
                "country": country_name,
                "url": url
            }

            all_flat_channels.append(channel_info)
            checked_count += 1

            # ১. ইন্ডিভিজুয়াল দেশভিত্তিক স্ট্রাকচার তৈরি
            if country_name not in main_json_data:
                main_json_data[country_name] = {}
            if category not in main_json_data[country_name]:
                main_json_data[country_name][category] = []
            main_json_data[country_name][category].append(channel_info)

            # ২. গ্লোবাল ক্যাটেগরিভিত্তিক স্ট্রাকচার তৈরি
            if category not in global_category_data:
                global_category_data[category] = []
            global_category_data[category].append(channel_info)

    print(f"Verification done. Total active verified channels: {checked_count}")

    print("Writing core root files...")
    with open('channels.json', 'w', encoding='utf-8') as f:
        json.dump(main_json_data, f, ensure_ascii=False, indent=4)
        
    with open('channels.m3u', 'w', encoding='utf-8') as f:
        f.write(create_m3u_content(all_flat_channels))

    print("Generating country-wise folders and category files...")
    for country, categories in main_json_data.items():
        # ফোল্ডারের নামের স্লাশ বা ব্যাকস্লাশ হ্যান্ডেল করা
        safe_country_name = country.replace('/', '_').replace('\\', '_')
        os.makedirs(safe_country_name, exist_ok=True)
        country_all_channels = []
        
        for category, ch_list in categories.items():
            file_name = f"{category.replace(' ', '_')}"
            
            # দেশের ভেতর আলাদা ক্যাটেগরির JSON
            with open(f"{safe_country_name}/{file_name}.json", 'w', encoding='utf-8') as f:
                json.dump(ch_list, f, ensure_ascii=False, indent=4)
                
            # দেশের ভেতর আলাদা ক্যাটেগরির M3U
            with open(f"{safe_country_name}/{file_name}.m3u", 'w', encoding='utf-8') as f:
                f.write(create_m3u_content(ch_list))
                
            country_all_channels.extend(ch_list)
            
        # দেশের ভেতর সম্মিলিত "all.json" এবং "all.m3u"
        with open(f"{safe_country_name}/all.json", 'w', encoding='utf-8') as f:
            json.dump(country_all_channels, f, ensure_ascii=False, indent=4)
            
        with open(f"{safe_country_name}/all.m3u", 'w', encoding='utf-8') as f:
            f.write(create_m3u_content(country_all_channels))

    print("Generating Global folder with cross-country categories...")
    global_folder = "Global"
    os.makedirs(global_folder, exist_ok=True)
    
    # গ্লোবাল ফোল্ডারের ভেতর ক্যাটেগরি অনুযায়ী কম্বাইনড ফাইল তৈরি
    for category, ch_list in global_category_data.items():
        file_name = f"{category.replace(' ', '_')}"
        with open(f"{global_folder}/{file_name}.json", 'w', encoding='utf-8') as f:
            json.dump(ch_list, f, ensure_ascii=False, indent=4)
            
        with open(f"{global_folder}/{file_name}.m3u", 'w', encoding='utf-8') as f:
            f.write(create_m3u_content(ch_list))

    # গ্লোবাল ফোল্ডারের ভেতর সব দেশের সব চ্যানেল একসাথে ("all.json" ও "all.m3u")
    with open(f"{global_folder}/all.json", 'w', encoding='utf-8') as f:
        json.dump(all_flat_channels, f, ensure_ascii=False, indent=4)
        
    with open(f"{global_folder}/all.m3u", 'w', encoding='utf-8') as f:
        f.write(create_m3u_content(all_flat_channels))

    print("All tasks completed successfully! Live data pipeline is fully operational.")

if __name__ == "__main__":
    fetch_and_generate_dynamic_data()
      
