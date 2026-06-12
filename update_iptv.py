import json
import os
import requests
import pycountry
from concurrent.futures import ThreadPoolExecutor

CHANNELS_API = "https://iptv-org.github.io/api/channels.json"
STREAMS_API = "https://iptv-org.github.io/api/streams.json"
LOGOS_API = "https://iptv-org.github.io/api/logos.json"  # 🖼️ গ্লোবাল অফিশিয়াল লোগো ডাটাবেজ

def get_country_name(code):
    """২ অক্ষরের আইএসও কোড থেকে ডাইনামিকালি দেশের সুন্দর নাম বের করার ফাংশন"""
    if not code:
        return None
    try:
        country = pycountry.countries.get(alpha_2=code.upper())
        if country:
            name = country.name
            if " , " in name:
                name = name.split(" , ")[0]
            if " (" in name:
                name = name.split(" (")[0]
            return name
    except Exception:
        pass
    return None

def check_single_stream(item):
    """একটি নির্দিষ্ট চ্যানেল লিংক সচল আছে কিনা তা ২ সেকেন্ড টাইমআউটে একসাথে চেক করার ফাংশন"""
    ch, url = item
    try:
        # শুধু হেডার চেক করবে (পুরো ভিডিও ডাউনলোড করবে না, তাই ফাস্ট হবে)
        response = requests.head(url, timeout=2.0, allow_redirects=True)
        if response.status_code == 200:
            return ch, url, True
        
        # কিছু সার্ভার HEAD রিকোয়েস্ট ব্লক করলে তাদের জন্য নিরাপদ GET ট্রাই করবে
        if response.status_code in [403, 405]:
            response_get = requests.get(url, timeout=2.0, stream=True)
            if response_get.status_code == 200:
                return ch, url, True
    except Exception:
        pass
    return ch, url, False

def create_m3u_content(channel_list):
    """M3U প্লেলিস্ট ফরম্যাট টেমপ্লেট"""
    m3u_text = "#EXTM3U\n"
    for ch in channel_list:
        m3u_text += f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-logo="{ch["logo"]}" group-title="{ch.get("country", "")} - {ch.get("category", "")}",{ch["name"]}\n'
        m3u_text += f'{ch["url"]}\n'
    return m3u_text

def fetch_and_generate_dynamic_data():
    print("Fetching global databases and logos from iptv-org...")
    channels = requests.get(CHANNELS_API).json()
    streams = requests.get(STREAMS_API).json()
    
    # 🎯 [FIXED] লোগো ডাটাবেজের সঠিক কি 'channel' দিয়ে মেমরিতে আইডি ম্যাপ তৈরি করা হলো
    try:
        logos_list = requests.get(LOGOS_API).json()
        logo_map = {logo['channel']: logo['url'] for logo in logos_list if 'channel' in logo and 'url' in logo}
        print("Logo database mapped successfully.")
    except Exception as e:
        print(f"Logo mapping failed: {e}")
        logo_map = {}

    stream_map = {stream['channel']: stream['url'] for stream in streams if 'channel' in stream and 'url' in stream}
    
    # প্যারালাল চেকিংয়ের জন্য টাস্ক লিস্ট
    tasks = []
    for ch in channels:
        ch_id = ch.get('id')
        if ch_id in stream_map:
            tasks.append((ch, stream_map[ch_id]))

    print(f"Total links found: {len(tasks)}. Starting parallel verification (100 threads)...")
    
    verified_channels_map = {}
    
    # 🚀 একসাথে ১০০টি লিংক প্যারালালে চেক করা হবে (১০ মিনিটের মধ্যে পুরো বিশ্ব ফিল্টার হবে)
    with ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(check_single_stream, tasks)
        for ch, url, is_alive in results:
            if is_alive:
                verified_channels_map[ch['id']] = url

    main_json_data = {}
    global_category_data = {}
    all_flat_channels = []

    print("Sorting verified active channels and auto-injecting correct logos...")
    for ch in channels:
        ch_id = ch.get('id')
        
        # কেবল শতভাগ লাইভ ভেরিফাইড সচল চ্যানেলগুলো প্রসেস হবে
        if ch_id in verified_channels_map:
            url = verified_channels_map[ch_id]
            country_code = ch.get('country')
            country_name = get_country_name(country_code)
            
            if not country_name:
                continue 
                
            category = ch.get('categories')[0].title() if ch.get('categories') else 'Other'
            
            # 🎯 প্রথমে চ্যানেলের নিজস্ব লোগো দেখবে, না থাকলে গ্লোবাল ডাটাবেজ থেকে আইডি মিলিয়ে অরিジナাল ছবি বসাবে
            logo_url = ch.get('logo')
            if not logo_url or logo_url.strip() == "":
                logo_url = logo_map.get(ch_id, "")
            
            # [FIXED] লোগো একদম না থাকলে খালি স্ট্রিং রাখবে, ফ্রন্টএন্ডের জাভাস্ক্রিপ্ট চমৎকার কাস্টম বক্স বানাবে
            if not logo_url:
                logo_url = ""

            channel_info = {
                "id": ch_id,
                "name": ch.get('name'),
                "logo": logo_url,
                "category": category,
                "country": country_name,
                "url": url
            }

            all_flat_channels.append(channel_info)

            # ইন্ডিভিজুয়াল দেশভিত্তিক ডিকশনারি
            if country_name not in main_json_data:
                main_json_data[country_name] = {}
            if category not in main_json_data[country_name]:
                main_json_data[country_name][category] = []
            main_json_data[country_name][category].append(channel_info)

            # গ্লোবাল ক্যাটেগরিভিত্তিক ডিকশনারি
            if category not in global_category_data:
                global_category_data[category] = []
            global_category_data[category].append(channel_info)

    print(f"Generation ongoing. Total online channels saved: {len(all_flat_channels)}")

    # মেইন রুট ফাইলস তৈরি (ওভাররাইট)
    with open('channels.json', 'w', encoding='utf-8') as f:
        json.dump(main_json_data, f, ensure_ascii=False, indent=4)
    with open('channels.m3u', 'w', encoding='utf-8') as f:
        f.write(create_m3u_content(all_flat_channels))

    # দেশভিত্তিক ফ্রেশ ফোল্ডার জেনারেশন
    for country, categories in main_json_data.items():
        safe_country_name = country.replace('/', '_').replace('\\', '_')
        os.makedirs(safe_country_name, exist_ok=True)
        country_all_channels = []
        
        for category, ch_list in categories.items():
            file_name = f"{category.replace(' ', '_')}"
            with open(f"{safe_country_name}/{file_name}.json", 'w', encoding='utf-8') as f:
                json.dump(ch_list, f, ensure_ascii=False, indent=4)
            with open(f"{safe_country_name}/{file_name}.m3u", 'w', encoding='utf-8') as f:
                f.write(create_m3u_content(ch_list))
            country_all_channels.extend(ch_list)
            
        with open(f"{safe_country_name}/all.json", 'w', encoding='utf-8') as f:
            json.dump(country_all_channels, f, ensure_ascii=False, indent=4)
        with open(f"{safe_country_name}/all.m3u", 'w', encoding='utf-8') as f:
            f.write(create_m3u_content(country_all_channels))

    # গ্লোবাল ফ্রেশ ফোল্ডার জেনারেশন
    global_folder = "Global"
    os.makedirs(global_folder, exist_ok=True)
    for category, ch_list in global_category_data.items():
        file_name = f"{category.replace(' ', '_')}"
        with open(f"{global_folder}/{file_name}.json", 'w', encoding='utf-8') as f:
            json.dump(ch_list, f, ensure_ascii=False, indent=4)
        with open(f"{global_folder}/{file_name}.m3u", 'w', encoding='utf-8') as f:
            f.write(create_m3u_content(ch_list))

    with open(f"{global_folder}/all.json", 'w', encoding='utf-8') as f:
        json.dump(all_flat_channels, f, ensure_ascii=False, indent=4)
    with open(f"{global_folder}/all.m3u", 'w', encoding='utf-8') as f:
        f.write(create_m3u_content(all_flat_channels))

    print("Pipeline compilation successful. All database tables are perfectly built!")

if __name__ == "__main__":
    fetch_and_generate_dynamic_data()
    
