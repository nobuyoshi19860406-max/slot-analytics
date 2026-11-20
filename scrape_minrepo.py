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

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://min-repo.com/",
})

def get_article_links(store_url, max_pages=1):
    links = []
    for page in range(1, max_pages + 1):
        url = store_url if page == 1 else f"{store_url}page/{page}/"
        try:
            res = SESSION.get(url, timeout=20)
            print(f"一覧ステータス ({url}): {res.status_code}")
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if re.match(r"https://min-repo\.com/\d+/?$", href):
                    if href not in links:
                        links.append(href)
        except Exception as e:
            print(f"一覧取得エラー: {e}")
        time.sleep(2)
    return links[:3]  # まずは直近3記事までに絞って高速化

def parse_article_data(article_url, store_name):
    try:
        res = SESSION.get(article_url, timeout=20)
        print(f"記事ステータス ({article_url}): {res.status_code}")
        if res.status_code != 200:
            return []
    except Exception as e:
        print(f"記事取得エラー: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    title_el = soup.find(["h1", "h2"])
    title_text = title_el.get_text(" ", strip=True) if title_el else ""
    date_match = re.search(r"(\d{4})[/年\-](\d{1,2})[/月\-](\d{1,2})", title_text)
    if not date_match:
        print(f"日付が見つかりません: {title_text[:50]}")
        return []

    date_str = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    records = []

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not headers:
            first_tr = table.find("tr")
            if first_tr:
                headers = [c.get_text(strip=True) for c in first_tr.find_all(["th", "td"])]

        if any("台番" in h for h in headers) and any("差枚" in h for h in headers):
            idx_machine = next((i for i, h in enumerate(headers) if "機種" in h), -1)
            idx_unit = next((i for i, h in enumerate(headers) if "台番" in h), -1)
            idx_games = next((i for i, h in enumerate(headers) if "G数" in h or "ゲーム" in h), -1)
            idx_diff = next((i for i, h in enumerate(headers) if "差枚" in h), -1)
            idx_bb = next((i for i, h in enumerate(headers) if "BB" in h or "BIG" in h), -1)
            idx_rb = next((i for i, h in enumerate(headers) if "RB" in h or "REG" in h), -1)

            for tr in table.find_all("tr")[1:]:
                cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if idx_unit == -1 or idx_diff == -1 or len(cols) <= max(idx_unit, idx_diff):
                    continue
                try:
                    unit_no = int(re.sub(r"\D", "", cols[idx_unit]))
                    diff_raw = cols[idx_diff].replace(",", "").replace("＋", "+").replace("－", "-").replace("−", "-")
                    diff_val = int(re.sub(r"[^\d\-+]", "", diff_raw))
                    games_val = int(re.sub(r"\D", "", cols[idx_games])) if idx_games != -1 and idx_games < len(cols) and cols[idx_games] else 0
                    bb_val = int(re.sub(r"\D", "", cols[idx_bb])) if idx_bb != -1 and idx_bb < len(cols) and cols[idx_bb] else 0
                    rb_val = int(re.sub(r"\D", "", cols[idx_rb])) if idx_rb != -1 and idx_rb < len(cols) and cols[idx_rb] else 0
                    machine_name = cols[idx_machine] if idx_machine != -1 and idx_machine < len(cols) else "不明機種"

                    records.append({
                        "店舗名": store_name,
                        "日付": date_str,
                        "台番": unit_no,
                        "機種名": machine_name,
                        "G数": games_val,
                        "BB": bb_val,
                        "RB": rb_val,
                        "差枚": diff_val,
                    })
                except ValueError:
                    continue
    return records

def main():
    if os.path.exists(OUTPUT_CSV):
        df_existing = pd.read_csv(OUTPUT_CSV)
        existing_keys = set(zip(df_existing["店舗名"], df_existing["日付"]))
    else:
        df_existing = pd.DataFrame(columns=["店舗名", "日付", "台番", "機種名", "G数", "BB", "RB", "差枚"])
        existing_keys = set()

    new_records = []
    for store_name, store_url in TARGET_STORES.items():
        print(f"[{store_name}] 記事一覧を取得中...")
        links = get_article_links(store_url, max_pages=1)
        print(f"  見つかった記事数: {len(links)}")
        for link in links:
            rows = parse_article_data(link, store_name)
            if rows:
                sample_key = (rows[0]["店舗名"], rows[0]["日付"])
                if sample_key not in existing_keys:
                    new_records.extend(rows)
                    existing_keys.add(sample_key)
                    print(f"  -> {rows[0]['日付']} ({len(rows)}台分) を追加")
                else:
                    print(f"  -> {rows[0]['日付']} は取得済み")
            time.sleep(2)

    if new_records:
        df_new = pd.DataFrame(new_records)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
        df_all.sort_values(by=["店舗名", "日付", "台番"], inplace=True)
        df_all.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"完了: 新規 {len(new_records)} 件を保存しました。")
    else:
        # 初回でもファイルが無いと分かりにくいので空ヘッダは作らずメッセージだけ出す
        print("新規データはありませんでした（アクセス制限または取得対象0件の可能性あり）。")

if __name__ == "__main__":
    main()
