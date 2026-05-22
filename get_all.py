import requests
import time
import hashlib
import urllib.parse
import json
import os
import datetime
from datetime import datetime as dt

import pandas as pd

# ========= 可配置区域 =========
KEYWORDS = [
    "异环",

]

# 开始日期(含)
START_DATE = datetime.datetime(2026, 5, 20)
# 结束日期(含) —— 将包含当天 00:00:00 ~ 23:59:59
END_DATE = datetime.datetime(2026, 5, 22)

# 主排序方式(先用这个抓):
#   ""         综合排序(默认)
#   "click"    最多播放
#   "pubdate"  最新发布
#   "dm"       最多弹幕
#   "stow"     最多收藏
# 每轮固定跑两种排序: 最新 + 最热(最多播放)
ORDERS_TO_RUN = ["pubdate", "click"]

# 每两小时执行一轮(秒)
RUN_INTERVAL_SECONDS = 1 * 60 * 60

# 每请求间隔秒数
REQUEST_INTERVAL = 1.0

# 输出路径(相对当前脚本目录)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "bilibili_search_result.json")
XLSX_PATH = os.path.join(BASE_DIR, "bilibili_search_result.xlsx")

# Cookie 若需要登录态可填写
COOKIE = ""
# ========= 配置结束 =========


HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "no-cache",
    "origin": "https://search.bilibili.com",
    "referer": "https://search.bilibili.com/",
    "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Google Chrome\";v=\"146\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
}
if COOKIE:
    HEADERS["cookie"] = COOKIE


def get_wbi_sign(params, salt="ea1db124af3c7062474693fa704f4ff8"):
    wts = int(time.time())
    params["wts"] = str(wts)
    sorted_keys = sorted(params.keys())
    query_parts = []
    for key in sorted_keys:
        val = str(params[key])
        val = val.replace("!", "").replace("*", "").replace("'", "").replace("(", "").replace(")", "")
        val = urllib.parse.quote(val, safe="")
        query_parts.append(f"{key}={val}")
    query_string = "&".join(query_parts)
    w_rid = hashlib.md5((query_string + salt).encode("utf-8")).hexdigest()
    return w_rid, wts


def daterange_days(start_date: datetime.datetime, end_date: datetime.datetime):
    """按天切分为 [(begin_ts, end_ts, label), ...]，end 含当天 23:59:59。"""
    start_day = datetime.datetime(start_date.year, start_date.month, start_date.day)
    end_day = datetime.datetime(end_date.year, end_date.month, end_date.day)
    if end_day < start_day:
        return []

    segments = []
    cur = start_day
    one_day = datetime.timedelta(days=1)
    while cur <= end_day:
        begin_ts = int(cur.timestamp())
        end_ts = int((cur + one_day).timestamp()) - 1
        segments.append((begin_ts, end_ts, cur.strftime("%Y-%m-%d")))
        cur += one_day
    return segments


def append_json(path, items):
    """实时追加写入 JSON(数组形式)，按链接/BVID 自动去重。"""
    existing = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if not isinstance(existing, list):
                    existing = []
        except Exception:
            existing = []

    seen_keys = set()
    for row in existing:
        key = row.get("bvid") or row.get("url") or row.get("aid")
        if key:
            seen_keys.add(str(key))

    new_items = []
    for row in items:
        key = row.get("bvid") or row.get("url") or row.get("aid")
        if not key:
            continue
        key = str(key)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        new_items.append(row)

    existing.extend(new_items)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return len(new_items), len(existing)


def search_one_segment(keyword, begin_ts, end_ts, order=""):
    """请求单个关键词 + 单个日期段内所有分页,返回结果 list。

    翻页终止策略(不再依赖 numPages):
        - numPages 是 ceil(numResults / page_size) 的理论值,而 numResults 被 B 站封顶在 ~300,
          实测 page_size=50 时 numPages=7,但 page=10 仍可返回 50 条,page=20 才返回 0。
          因此用 "返回空 / 本页全部重复 / 达到硬上限" 作为终止条件更稳。
    """
    url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
    time_format = "%Y-%m-%d %H:%M:%S"
    page = 1
    results = []
    seen_bvids = set()
    MAX_PAGE_HARD = 50

    while page <= MAX_PAGE_HARD:
        base_params = {
            "__refresh__": "true",
            "_extra": "",
            "ad_resource": "5654",
            "category_id": "",
            "context": "",
            "dynamic_offset": str((page - 1) * 30),
            "from_source": "",
            "from_spmid": "333.337",
            "gaia_vtoken": "",
            "highlight": "1",
            "keyword": keyword,
            "order": order,
            "page": str(page),
            "page_size": "42",
            "platform": "pc",
            "pubtime_begin_s": str(begin_ts),
            "pubtime_end_s": str(end_ts),
            "qv_id": "sEAYydeeGhZtBVQMhC5FbLK8W6D7hzsU",
            "search_type": "video",
            "single_column": "0",
            "source_tag": "3",
            "web_location": "1430654",
            "web_roll_page": "1",
        }
        if not order:
            base_params.pop("order")

        w_rid, wts = get_wbi_sign(dict(base_params))
        base_params["w_rid"] = w_rid
        base_params["wts"] = str(wts)

        try:
            response = requests.get(url, headers=HEADERS, params=base_params, timeout=15)
        except requests.RequestException as e:
            print(f"  [error] 请求失败: {e}")
            break

        if response.status_code != 200:
            print(f"  [error] HTTP {response.status_code}")
            break

        data = response.json()
        if data.get("code") != 0:
            print(f"  [warn] code={data.get('code')} msg={data.get('message')}")
            break

        data_block = data.get("data", {}) or {}
        items = data_block.get("result", []) or []
        num_results = data_block.get("numResults", 0)
        num_pages = data_block.get("numPages", 0)
        if not items:
            print(f"    page {page} -> 0 条,停止")
            break

        new_count = 0
        for item in items:
            bvid = item.get("bvid")
            if bvid and bvid in seen_bvids:
                continue
            if bvid:
                seen_bvids.add(bvid)
            new_count += 1
            pubdate_ts = item.get("pubdate")
            results.append({
                "keyword": keyword,
                "bvid": item.get("bvid"),
                "aid": item.get("aid"),
                "title": (item.get("title", "") or "").replace('<em class="keyword">', "").replace("</em>", ""),
                "author": item.get("author"),
                "mid": item.get("mid"),
                "play": item.get("play"),
                "video_review": item.get("video_review"),
                "favorites": item.get("favorites"),
                "like": item.get("like"),
                "duration": item.get("duration"),
                "pubdate_ts": pubdate_ts,
                "pubdate": dt.fromtimestamp(pubdate_ts).strftime(time_format) if pubdate_ts else "",
                "url": f"https://www.bilibili.com/video/{item.get('bvid')}" if item.get("bvid") else "",
            })

        print(
            f"    page {page}  本页{len(items)}条(新增{new_count}),"
            f"numResults={num_results} numPages={num_pages}"
        )
        # 本页全部重复 => 接口已经循环了,停
        if new_count == 0:
            break
        page += 1
        time.sleep(REQUEST_INTERVAL)

    return results


def export_xlsx(json_path, xlsx_path):
    if not os.path.exists(json_path):
        print("JSON 文件不存在,跳过 xlsx 导出")
        return
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        print("无数据,跳过 xlsx 导出")
        return

    df = pd.DataFrame(data)
    if "bvid" in df.columns:
        df = df.drop_duplicates(subset=["keyword", "bvid"], keep="first")
    df.to_excel(xlsx_path, index=False)
    print(f"已导出 xlsx: {xlsx_path} (共 {len(df)} 行)")


def run_once():
    segments = daterange_days(START_DATE, END_DATE)
    print(
        f"关键词数: {len(KEYWORDS)}, 日期段数: {len(segments)}, "
        f"本轮排序: {', '.join(ORDERS_TO_RUN)}"
    )

    fetched_total = 0
    stored_total = 0
    for kw in KEYWORDS:
        for begin_ts, end_ts, label in segments:
            for order in ORDERS_TO_RUN:
                print(f"[{kw}] {label}  ({begin_ts} ~ {end_ts})  order={order or '综合'}")
                results = search_one_segment(kw, begin_ts, end_ts, order=order)
                if results:
                    for r in results:
                        r["_source_order"] = order or "totalrank"
                    added_count, stored_rows = append_json(JSON_PATH, results)
                    fetched_total += len(results)
                    stored_total += added_count
                    print(
                        f"  => [{order or '综合'}] 抓取 {len(results)} 条,去重新增 {added_count} 条,"
                        f"JSON 累计 {stored_rows} 条"
                    )
                time.sleep(REQUEST_INTERVAL)

    print(
        f"\n本轮完成: 抓取总数 {fetched_total} 条, 去重新增 {stored_total} 条, JSON: {JSON_PATH}"
    )
    export_xlsx(JSON_PATH, XLSX_PATH)


def main():
    print("任务已启动: 立即执行 1 轮,之后每 1 小时自动执行 1 轮")
    while True:
        cycle_start = time.time()
        try:
            run_once()
        except Exception as e:
            print(f"[error] 本轮执行异常: {e}")

        elapsed = int(time.time() - cycle_start)
        sleep_seconds = max(0, RUN_INTERVAL_SECONDS - elapsed)
        next_time = dt.now() + datetime.timedelta(seconds=sleep_seconds)
        print(
            f"本轮耗时 {elapsed}s, 下次执行时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()

"""
B 站搜索排序参数(已通过浏览器 Network 抓包确认):
    综合排序(默认): 不传 order 参数(或 order=totalrank)
    最多播放      : order=click
    最新发布      : order=pubdate
    最多弹幕      : order=dm
    最多收藏      : order=stow

按天切分示例 4.17-4.19:
    pubtime_begin_s=1776355200 & pubtime_end_s=1776441599
    pubtime_begin_s=1776441600 & pubtime_end_s=1776527999
    pubtime_begin_s=1776528000 & pubtime_end_s=1776614399
"""
