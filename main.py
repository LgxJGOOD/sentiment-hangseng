from playwright.sync_api import sync_playwright
import csv

base_url = "https://guba.eastmoney.com/list,600570,f_{}.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    all_data = []

    for i in range(1, 21):
        url = base_url.format(i)
        print(f"正在爬第 {i} 页: {url}")

        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("tbody.listbody tr.listitem")

        rows = page.query_selector_all("tbody.listbody tr.listitem")

        print(f"第{i}页帖子数量:", len(rows))

        for row in rows:
            title_el = row.query_selector("td:nth-child(3) a")
            author_el = row.query_selector("td:nth-child(4) a")
            read_el = row.query_selector("td:nth-child(1) .read")
            reply_el = row.query_selector("td:nth-child(2) .reply")
            time_el = row.query_selector("td:nth-child(5) .pub_time")

            if title_el:
                title = title_el.get_attribute("data-cntitle") or title_el.inner_text()
                href = title_el.get_attribute("href")

                all_data.append([
                    title,
                    "https://guba.eastmoney.com" + href if href.startswith("/") else href,
                    author_el.inner_text() if author_el else "",
                    read_el.inner_text() if read_el else "",
                    reply_el.inner_text() if reply_el else "",
                    time_el.inner_text() if time_el else ""
                ])

    browser.close()

# ====== 写入CSV ======
with open("guba_600570.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)

    # 表头
    writer.writerow(["title", "url", "author", "read", "reply", "time"])

    # 数据
    writer.writerows(all_data)

print("已保存CSV，共条数：", len(all_data))