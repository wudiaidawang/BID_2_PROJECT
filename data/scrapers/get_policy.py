"""
采集政策法规结构化数据
主源: 上海市公共资源交易平台 (shggzy.com) - 政策法规栏目 (4个分类)
Fallback: 中国政府采购网 (ccgp.gov.cn) - 法规栏目
输出: data/raw/policy_data.xlsx (目标 ~200 条)
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
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'policy_data.xlsx')

SHGGZY_BASE = 'https://www.shggzy.com'
# 四个分类栏目: (路径前缀, 分类名)
SHGGZY_CATEGORIES = [
    ('zcfgzhfg', '综合法律法规'),
    ('gjzcfg', '国家政策法规'),
    ('shzchb', '上海政策汇编'),
    ('zxzdgz', '中心制度规则'),
]

CCGP_BASE = 'https://www.ccgp.gov.cn'
CCGP_POLICY_URLS = [
    ('https://www.ccgp.gov.cn/zcfg/', '法规'),
    ('https://www.ccgp.gov.cn/zcfg/gjfg/', '国家法规'),
    ('https://www.ccgp.gov.cn/zcfg/dffg/', '地方法规'),
]


def parse_shggzy_detail(url):
    """解析 shggzy.com 详情页"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text()

        # 面包屑标记之后的区域有真正的标题
        breadcrumb_marker = '/详情信息'
        bc_idx = text.find(breadcrumb_marker)
        if bc_idx > 0:
            detail_text = text[bc_idx + len(breadcrumb_marker):bc_idx + 1500]
        else:
            detail_text = text

        # 标题 — 面包屑后第一段有意义的文字
        title = ''
        lines = [l.strip() for l in detail_text.splitlines() if l.strip() and len(l.strip()) > 8]
        # 过滤掉导航/菜单文本
        skip_words = ['首页', '政策法规', '综合法律法规', '国家政策法规', '上海政策汇编',
                       '中心制度规则', '上海公共资源交易平台', '欢迎您', '登录', '注册',
                       '交易公告', '交易指南', '信用信息', '关于我们', '信息公开', '返回',
                       '搜索', '发布', '访问', 'CA证书', '电子营业执照', '扫码']
        for line in lines:
            if not any(w in line for w in skip_words) and len(line) > 10:
                title = line
                break

        # 发布时间
        time_match = re.search(r'发布时间[：:]\s*([\d-]+\s*[\d:]+)', detail_text)
        publish_time = time_match.group(1).strip() if time_match else ''

        # 信息来源
        source_match = re.search(r'信息来源[：:]\s*([^\s\n]+)', detail_text)
        info_source = source_match.group(1).strip() if source_match else ''

        # 施行时间
        eff_pat = r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日[起实]?施[行施]'
        eff_match = re.search(eff_pat, text)
        effective_time = ''
        if eff_match:
            effective_time = f"{eff_match.group(1)}-{int(eff_match.group(2)):02d}-{int(eff_match.group(3)):02d}"

        # 发布机构
        issuer = ''
        issuer_pat = r'([一-龥]{4,20}(?:部|委|局|厅|办|中心|监管局|人民政府|国务院))\s*(?:印发|发布|颁布|制定|通过|令|第)'
        m = re.search(issuer_pat, detail_text[:500])
        if m:
            issuer = m.group(1).strip()

        # 正文
        body = text[bc_idx + len(breadcrumb_marker) + 200:bc_idx + len(breadcrumb_marker) + 1500] if bc_idx > 0 else text[500:1500]
        body_lines = [l.strip() for l in body.splitlines() if len(l.strip()) > 10]
        body_text = ' '.join(body_lines[:15])

        # 法规分类 — 从面包屑提取
        category = ''
        bc_match = re.search(r'/综合法律法规\s*/\s*(\S+)', text[:bc_idx + 200] if bc_idx > 0 else text[:500])
        if bc_match:
            category = bc_match.group(1)

        return {
            '来源网站': url,
            '政策标题': title,
            '发布日期': publish_time[:10] if publish_time else '',
            '施行日期': effective_time,
            '发布机构': issuer,
            '信息来源': info_source,
            '法规分类': category,
            '正文摘要': body_text[:500],
        }
    except Exception as e:
        print(f'  [ERROR] 解析详情失败 {url}: {e}')
        return None


def scrape_shggzy(max_per_category=55):
    """从上海公共资源交易平台采集政策法规 (4个分类)"""
    all_data = []
    seen_urls = set()

    for path_prefix, cat_name in SHGGZY_CATEGORIES:
        print(f'\n[SHGGZY] 采集分类: {cat_name} ({path_prefix})')
        cat_count = 0
        prev_ids = set()

        for page_no in range(1, 20):
            if cat_count >= max_per_category:
                break

            if page_no == 1:
                list_url = f'{SHGGZY_BASE}/{path_prefix}.jhtml'
            else:
                list_url = f'{SHGGZY_BASE}/{path_prefix}_{page_no}.jhtml'

            try:
                r = requests.get(list_url, headers=HEADERS, timeout=15)
                r.encoding = 'utf-8'
                soup = BeautifulSoup(r.text, 'html.parser')

                # 提取所有 onclick 中的详情URL
                detail_paths = set()
                for tag in soup.find_all(attrs={'onclick': True}):
                    onclick = tag.get('onclick', '')
                    for m in re.finditer(r"window\.open\('(/[\w/]+\d+)'\)", onclick):
                        p = m.group(1)
                        if any(p.startswith(prefix) for prefix in
                               ['/zhfgwj', '/zhfgfg', '/gjzcfg', '/shzchb', '/zxzdgz']):
                            detail_paths.add(p)

                if not detail_paths or detail_paths == prev_ids:
                    print(f'  第{page_no}页无新数据，该分类结束')
                    break
                prev_ids = detail_paths.copy()

                print(f'  第{page_no}页发现 {len(detail_paths)} 条')

                for detail_path in detail_paths:
                    detail_url = SHGGZY_BASE + detail_path
                    if detail_url in seen_urls:
                        continue
                    seen_urls.add(detail_url)

                    info = parse_shggzy_detail(detail_url)
                    if info and info['政策标题'] and len(info['政策标题']) > 5:
                        all_data.append(info)
                        cat_count += 1
                        if cat_count >= max_per_category:
                            break

                    time.sleep(0.6)

                time.sleep(1.0)

            except Exception as e:
                print(f'  [ERROR] 列表页失败 {list_url}: {e}')
                break

        print(f'  分类 "{cat_name}" 采集完成: {cat_count} 条')

    return all_data


def scrape_ccgp(max_total=200):
    """Fallback: 中国政府采购网"""
    print('\n[CCGP] Fallback采集...')
    all_data = []
    seen_urls = set()

    for list_url, cat_name in CCGP_POLICY_URLS:
        if len(all_data) >= max_total:
            break
        print(f'  抓取: {cat_name} ({list_url})')
        try:
            r = requests.get(list_url, headers=HEADERS, timeout=15)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')

            links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').strip()
                title = a.get_text(strip=True)
                if not title or len(title) < 8:
                    continue
                if '.' not in href and '/' not in href:
                    continue
                links.append((title, href))

            print(f'    发现 {len(links)} 个链接')

            for title, href in links[:60]:
                if len(all_data) >= max_total:
                    break
                if not href.startswith('http'):
                    href = CCGP_BASE.rstrip('/') + '/' + href.lstrip('./')
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                try:
                    r2 = requests.get(href, headers=HEADERS, timeout=15)
                    r2.encoding = 'utf-8' if r2.apparent_encoding else 'gbk'
                    s2 = BeautifulSoup(r2.text, 'html.parser')
                    detail_text = s2.get_text()

                    info = {
                        '来源网站': href,
                        '政策标题': title,
                        '发布日期': '',
                        '施行日期': '',
                        '发布机构': '',
                        '信息来源': '中国政府采购网',
                        '法规分类': cat_name,
                        '正文摘要': detail_text[200:700] if len(detail_text) > 200 else detail_text,
                    }
                    tm = re.search(r'(\d{4}[-/年]\d{2}[-/月]\d{2})', detail_text[:500])
                    if tm:
                        info['发布日期'] = tm.group(1).replace('年', '-').replace('月', '-').replace('/', '-')

                    all_data.append(info)
                    time.sleep(0.6)
                except Exception:
                    continue

        except Exception as e:
            print(f'  [ERROR] {list_url}: {e}')

    return all_data


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print('=' * 60)
    print('开始采集政策法规数据...')

    data = scrape_shggzy(max_per_category=55)

    if len(data) < 150:
        print(f'\n主源仅采集到 {len(data)} 条 (目标≥200)，启动 fallback...')
        fallback_data = scrape_ccgp(max_total=250 - len(data))
        data.extend(fallback_data)

    if data:
        df = pd.DataFrame(data)
        df = df.drop_duplicates(subset=['政策标题'])
        df = df[df['政策标题'].str.len() > 6]
        # 过滤掉明显是菜单/导航的
        bad_words = ['上海公共资源', '欢迎您', '登录/注册', '首页', '交易公告']
        df = df[~df['政策标题'].str.contains('|'.join(bad_words))]
        df = df.reset_index(drop=True)

        df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f'\n{"=" * 60}')
        print(f'成功保存 {len(df)} 条政策法规到 {OUTPUT_FILE}')
        print(f'各分类数量: {df["法规分类"].value_counts().to_dict() if "法规分类" in df.columns else "N/A"}')
    else:
        print('\n未获取到任何政策法规数据')


if __name__ == '__main__':
    main()
