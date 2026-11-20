import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os

TARGET_STORES = {
    "オーギヤ彦根店": "https://min-repo.com/tag/%e3%82%aa%e3%83%bc%e3%82%ae%e3%83%a4%e5%bd%a6%e6%a0%b9%e5%ba%97/",
    "イチバン近江八幡店SLOT333": "https://min-repo.com/tag/%e3%82%a4%e3%83%81%e3%83%90%e3%83%b3%e8%bf%91%e6%b1%9f%e5%85%ab%e5%b9%a1%e5%ba%97slot333/",
}

OUTPUT_CSV = "slot_data_all.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_article_links(store_url, max_pages=2):
    links = []
    for page in range(1, max_pages + 1):
        url = store_url if page == 1 else f"{store_url}page/{page}/"
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select("h2 a, .entry-title a, article a"):
                href = a.get("href")
                if href and re.match(r"https://min-repo\.com/\d+/", href):
                    if href not in links:
                        links.append(href)
        except Exception as e:
            print(f"一覧取得エラー: {e}")
        time.sleep(2)
    return links

def parse_article_data(article_url, store_name):
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return []
    except Exception as e:
        print(f"記事取得エラー: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    title_el = soup.select_one("h1")
    title_text = title_el.get_text(strip=True) if title_el else ""
    date_match = re.search(r"(\d{4})[/年](\d{1,2})[/月](\d{1,2})", title_text)
    if not date_match:
        return []

    date_str = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    records = []

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "台番" in headers and "差枚" in headers:
            idx_machine = headers.index("機種名") if "機種名" in headers else -1
            idx_unit = headers.index("台番")
            idx_games = headers.index("G数") if "G数" in headers else -1
            idx_diff = headers.index("差枚")
            idx_bb = headers.index("BB") if "BB" in headers else -1
            idx_rb = headers.index("RB") if "RB" in headers else -1

            for tr in table.find_all("tr")[1:]:
                cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if len(cols) <= max(idx_unit, idx_diff):
                    continue
                try:
                    unit_no = int(re.sub(r"\D", "", cols[idx_unit]))
                    diff_val = int(re.sub(r"[^\d\-+]", "", cols[idx_diff].replace(",", "")))
                    games_val = int(re.sub(r"\D", "", cols[idx_games])) if idx_games != -1 and cols[idx_games] else 0
                    bb_val = int(re.sub(r"\D", "", cols[idx_bb])) if idx_bb != -1 and cols[idx_bb] else 0
                    rb_val = int(re.sub(r"\D", "", cols[idx_rb])) if idx_rb != -1 and cols[idx_rb] else 0
                    machine_name = cols[idx_machine] if idx_machine != -1 else "不明機種"

                    records.append({
                        "店舗名": store_name,
                        "日付": date_str,
                        "台番": unit_no,
                        "機種名": machine_name,
                        "G数": games_val,
                        "BB": bb_val,
                        "RB": rb_val,
                        "差枚": diff_val
                    })
                except ValueError:
                    continue
    return records

def main():
    if os.path.exists(OUTPUT_CSV):
        df_existing = pd.read_csv(OUTPUT_CSV)
        existing_keys = set(zip(df_existing["店舗名"], df_existing["日付"]))
    else:
        df_existing = pd.DataFrame()
        existing_keys = set()

    new_records = []
    for store_name, store_url in TARGET_STORES.items():
        print(f"[{store_name}] 記事一覧を取得中...")
        links = get_article_links(store_url, max_pages=2)
        for link in links:
            rows = parse_article_data(link, store_name)
            if rows:
                sample_key = (rows[0]["店舗名"], rows[0]["日付"])
                if sample_key not in existing_keys:
                    new_records.extend(rows)
                    existing_keys.add(sample_key)
                    print(f"  -> {rows[0]['日付']} ({len(rows)}台分) を追加")
            time.sleep(3)

    if new_records:
        df_new = pd.DataFrame(new_records)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
        df_all.sort_values(by=["店舗名", "日付", "台番"], inplace=True)
        df_all.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"完了: 新規 {len(new_records)} 件を保存しました。")
    else:
        print("新規データはありませんでした。")

if __name__ == "__main__":
    main()
