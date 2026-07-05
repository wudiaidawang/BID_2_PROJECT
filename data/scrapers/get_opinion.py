"""
采集招投标相关舆情/新闻数据 v3
策略: 快速抓取CCGP各栏目列表页标题 (不入详情页) + 修复曝光台
CCGP招标公告页面本身就是最丰富的招投标舆情信息源
输出: data/raw/opinion_data.xlsx (目标 ~500 条)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'opinion_data.xlsx')


def scrape_list_page(url, source_label, max_pages=30, min_title_len=8):
    """快速抓取列表页所有链接标题 (不进入详情页)"""
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page_no in range(0, max_pages):
        if page_no == 0:
            page_url = url
        else:
            if url.endswith('/'):
                if 'index.htm' in url:
                    page_url = url.replace('/index.htm', f'/index_{page_no}.htm')
                else:
                    page_url = f'{url}index_{page_no}.htm'
            elif 'index.htm' in url:
                page_url = url.replace('index.htm', f'index_{page_no}.htm')
            else:
                page_url = f'{url}index_{page_no}.htm'

        try:
            r = session.get(page_url, timeout=15)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')

            found = 0
            for a in soup.find_all('a', href=True):
                title = a.get_text(strip=True)
                href = a.get('href', '').strip()
                if not title or len(title) < min_title_len:
                    continue
                skip_kw = ['首页', '上一页', '下一页', '尾页', '设为首页', '加入收藏',
                           '联系我们', '网站地图', '无障碍', '长者', 'English', '简体', '繁体']
                if any(k in title for k in skip_kw):
                    continue
                if '.htm' in href and not href.startswith('javascript'):
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            href = 'https://www.ccgp.gov.cn' + href
                        elif href.startswith('./'):
                            href = 'https://www.ccgp.gov.cn' + href[1:]
                        else:
                            href = 'https://www.ccgp.gov.cn/' + href

                    results.append({
                        '来源网站': href,
                        '舆情标题': title,
                        '发布时间': '',
                        '舆情内容': '',
                        '新闻来源': source_label,
                        '搜索关键词': source_label.split('-')[-1] if '-' in source_label else source_label,
                    })
                    found += 1

            if found == 0:
                break
            print(f'  {source_label} 第{page_no+1}页: {found}条')
            time.sleep(0.3)

        except Exception as e:
            print(f'  [SKIP] {source_label} 第{page_no+1}页: {type(e).__name__}')
            break

    return results


def scrape_exposure_fixed(max_results=200):
    """修复版曝光台抓取 - URL构造修正"""
    results = []
    base_urls = [
        'https://www.ccgp.gov.cn/lljgg/',
        'https://www.ccgp.gov.cn/cggg/zygg/lljgg/',
    ]

    for base in base_urls:
        if len(results) >= max_results:
            break
        for page_no in range(0, 20):
            if len(results) >= max_results:
                break
            if page_no == 0:
                url = base
            else:
                if base.endswith('/'):
                    url = f'{base}index_{page_no}.htm'
                else:
                    url = f'{base}/index_{page_no}.htm'

            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                r.encoding = 'utf-8'
                soup = BeautifulSoup(r.text, 'html.parser')

                found = 0
                for a in soup.find_all('a', href=True):
                    title = a.get_text(strip=True)
                    href = a.get('href', '').strip()
                    if not title or len(title) < 6:
                        continue
                    if '.htm' in href and not href.startswith('javascript'):
                        if not href.startswith('http'):
                            if href.startswith('/'):
                                href = 'https://www.ccgp.gov.cn' + href
                            else:
                                href = 'https://www.ccgp.gov.cn/' + href
                        results.append({
                            '来源网站': href,
                            '舆情标题': title,
                            '发布时间': '',
                            '舆情内容': '',
                            '新闻来源': '中国政府采购网-曝光台',
                            '搜索关键词': '违法失信',
                        })
                        found += 1
                        if len(results) >= max_results:
                            break

                if found == 0:
                    break
                print(f'  曝光台 第{page_no+1}页: {found}条')
                time.sleep(0.5)

            except Exception as e:
                print(f'  [SKIP] 曝光台 第{page_no+1}页: {type(e).__name__}')
                break

    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print('=' * 60)
    print('开始采集舆情/新闻数据 v3 (快速列表抓取)...')
    all_data = []
    seen_titles = set()

    def add_results(results, label=''):
        new = 0
        for r in results:
            t = re.sub(r'\s+', '', r['舆情标题'])[:40]
            if t not in seen_titles:
                seen_titles.add(t)
                all_data.append(r)
                new += 1
        if label:
            print(f'  [{label}] +{new} (累计{len(all_data)})')
        return new

    # ==== CCGP公告栏目 (大量招标公告 = 招投标舆情) ====
    print('\n--- CCGP公告栏目 ---')
    ccgp_sections = [
        ('https://www.ccgp.gov.cn/cggg/zygg/zbgg/index.htm', '中国政府采购网-中标公告', 30),
        ('https://www.ccgp.gov.cn/cggg/zygg/jzxcs/index.htm', '中国政府采购网-竞争性磋商', 15),
        ('https://www.ccgp.gov.cn/cggg/dfgg/zbgg/index.htm', '中国政府采购网-地方中标公告', 15),
        ('https://www.ccgp.gov.cn/cggg/dfgg/gkzb/index.htm', '中国政府采购网-公开招标', 15),
        ('https://www.ccgp.gov.cn/cggg/zygg/gkzb/index.htm', '中国政府采购网-中央公开招标', 15),
    ]
    for url, label, pages in ccgp_sections:
        results = scrape_list_page(url, label, max_pages=pages)
        add_results(results, label)

    # ==== CCGP政策法规栏目 ====
    print('\n--- CCGP政策法规栏目 ---')
    policy_sections = [
        ('https://www.ccgp.gov.cn/zcfg/index.htm', '中国政府采购网-政策法规', 20),
        ('https://www.ccgp.gov.cn/zcfg/gjfg/index.htm', '中国政府采购网-国家法规', 15),
        ('https://www.ccgp.gov.cn/zcfg/dffg/index.htm', '中国政府采购网-地方法规', 15),
        ('https://www.ccgp.gov.cn/gpsr/index.htm', '中国政府采购网-采购动态', 20),
        ('https://www.ccgp.gov.cn/gpsr/zcdx/index.htm', '中国政府采购网-政策动向', 15),
        ('https://www.ccgp.gov.cn/gpsr/dfdt/index.htm', '中国政府采购网-地方动态', 15),
        ('https://www.ccgp.gov.cn/gpsr/zcfgjd/index.htm', '中国政府采购网-政策解读', 10),
    ]
    for url, label, pages in policy_sections:
        results = scrape_list_page(url, label, max_pages=pages)
        add_results(results, label)

    # ==== 曝光台 (修复版) ====
    print('\n--- 曝光台 ---')
    fb = scrape_exposure_fixed(max_results=200)
    add_results(fb, '曝光台')

    # ==== CTBA ====
    print('\n--- CTBA ---')
    ctba_sections = [
        ('https://www.ctba.org.cn/list_1.jsp', 'CTBA-行业新闻'),
        ('https://www.ctba.org.cn/list_3.jsp', 'CTBA-政策法规'),
        ('https://www.ctba.org.cn/list_4.jsp', 'CTBA-招标公告'),
        ('https://www.ctba.org.cn/list_5.jsp', 'CTBA-中标公告'),
    ]
    for url, label in ctba_sections:
        results = scrape_list_page(url, label, max_pages=5, min_title_len=6)
        add_results(results, label)

    # ==== 保存 ====
    if all_data:
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset=['舆情标题'])
        df = df[df['舆情标题'].str.len() > 6]
        df = df.reset_index(drop=True)

        df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f'\n{"=" * 60}')
        print(f'成功保存 {len(df)} 条舆情数据到 {OUTPUT_FILE}')
        src_counts = df['新闻来源'].value_counts()
        for src, cnt in src_counts.items():
            print(f'  {src}: {cnt}')
    else:
        print('\n未获取到舆情数据')


if __name__ == '__main__':
    main()
