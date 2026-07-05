"""
补充招标信息 — 从CCGP最新公告采集，不与已有8789条重合
解析公告详情页获取联系人、联系方式等缺失字段
主源: ccgp.gov.cn/cggg/zygg/zbgg
Fallback: ggzy.hefei.gov.cn (安徽交易平台)
输出: data/raw/bidding_supplement.xlsx (目标 ~200 条)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'bidding_supplement.xlsx')
BID_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bid_data.xlsx')

CCGP_BASE = 'https://www.ccgp.gov.cn'

# 创建带重试的 session
def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    return s


session = make_session()


def load_existing_titles():
    try:
        df = pd.read_excel(BID_DATA)
        return set(str(t)[:25] for t in df['项目名称'].dropna())
    except:
        return set()


def parse_detail_fields(url):
    """轻度解析详情页，提取额外字段。失败返回基本字段"""
    info = {
        '来源网站': url,
        '项目名称': '',
        '项目阶段': '中标公告',
        '发布时间': '',
        '招标人': '',
        '招标人联系人': '', '招标人联系方式': '',
        '招标代理机构': '', '招标代理机构联系人': '', '招标代理机构联系方式': '',
        '中标人': '', '中标金额': '',
        '项目地点': '',
        '招标文件': '',
    }
    try:
        r = session.get(url, timeout=(8, 20), verify=False)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text()

        # 标题
        for h in soup.find_all(['h1', 'h2', 'h3', 'title']):
            t = h.get_text(strip=True)
            if len(t) > 8 and 'ccgp' not in t.lower() and '中国政府采购' not in t:
                info['项目名称'] = t
                break

        # 发布时间
        pt = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', text[:400])
        if pt: info['发布时间'] = pt.group(1).replace('年', '-').replace('月', '-')

        # 采购人
        buyer = re.search(r'(?:采购人|招标人)[：:]\s*([^\n]{4,35})', text)
        if buyer: info['招标人'] = buyer.group(1).strip()

        # 代理机构
        agency = re.search(r'(?:代理机构|采购代理机构)[：:]\s*([^\n]{4,35})', text)
        if agency: info['招标代理机构'] = agency.group(1).strip()

        # 中标人
        winner = re.search(r'(?:中标人|中标供应商|成交供应商)[：:]\s*([^\n]{4,40})', text)
        if winner: info['中标人'] = winner.group(1).strip()

        # 金额
        amount = re.search(r'(?:中标金额|成交金额)[：:]\s*([^\n]{2,30})', text)
        if amount: info['中标金额'] = amount.group(1).strip()

        # 项目地点
        loc = re.search(r'(?:项目地点|建设地点|实施地点)[：:]\s*([^\n]{3,50})', text)
        if loc: info['项目地点'] = loc.group(1).strip()

        # 联系人/电话
        contact = re.search(r'(?:项目联系人|联系人)[：:]\s*([^\n]{2,15})', text)
        if contact: info['招标代理机构联系人'] = contact.group(1).strip()
        phone = re.search(r'(?:联系电话|电话|联系方式)[：:]\s*([\d\-]{7,18})', text)
        if phone: info['招标代理机构联系方式'] = phone.group(1).strip()

        # PDF附件
        pdfs = [a.get('href', '') for a in soup.find_all('a', href=True) if '.pdf' in a.get('href', '').lower()]
        info['招标文件'] = '; '.join(pdfs[:3])

    except Exception:
        pass  # 返回基本结构

    return info


def scrape_ccgp(max_results=200, existing_titles=None):
    """从CCGP中标公告列表采集"""
    print('[CCGP] 采集最新中标公告 (列表+可选详情)...')
    existing = existing_titles or set()
    all_data = []
    session2 = make_session()

    for page_no in range(0, 35):
        if len(all_data) >= max_results:
            break

        if page_no == 0:
            url = f'{CCGP_BASE}/cggg/zygg/zbgg/index.htm'
        else:
            url = f'{CCGP_BASE}/cggg/zygg/zbgg/index_{page_no}.htm'

        try:
            r = session2.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')

            detail_urls = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '').strip()
                title = a.get_text(strip=True)
                if re.search(r'/\d{6}/t\d{8}_\d+\.htm', href) and len(title) > 5:
                    if not href.startswith('http'):
                        href = CCGP_BASE + href
                    detail_urls.append((title, href))

            if not detail_urls:
                print(f'  第{page_no+1}页无数据，停止')
                break

            print(f'  第{page_no+1}页: {len(detail_urls)} 条', end='')

            new_count = 0
            for title, href in detail_urls:
                if len(all_data) >= max_results:
                    break
                tkey = title[:25]
                if tkey in existing:
                    continue
                existing.add(tkey)

                # 从列表页已能获得: 标题, URL, 列表页时间等
                info = parse_detail_fields(href)
                info['项目名称'] = info['项目名称'] or title
                all_data.append(info)
                new_count += 1
                time.sleep(0.3)  # 减少请求频率避免SSL错误

            print(f' → +{new_count} (累计 {len(all_data)})')

        except Exception as e:
            print(f'  第{page_no+1}页失败: {type(e).__name__}')
            continue

    return all_data


def scrape_anhui_fallback(max_results=200, existing_titles=None):
    """安徽交易平台兜底"""
    print('[FALLBACK] 安徽省公共资源交易平台...')
    existing = existing_titles or set()
    all_data = []

    for page in range(1, 15):
        if len(all_data) >= max_results:
            break
        try:
            url = f'https://ggzy.hefei.gov.cn/jyxx/013003/013003001/moreinfo.html?pageNo={page}'
            r = session.get(url, timeout=15, verify=False)
            r.encoding = 'utf-8'
            soup = BeautifulSoup(r.text, 'html.parser')

            count = 0
            for a in soup.find_all('a', href=True):
                title = a.get_text(strip=True)
                href = a.get('href', '')
                if not title or len(title) < 6:
                    continue
                tkey = title[:25]
                if tkey in existing:
                    continue
                existing.add(tkey)

                if not href.startswith('http'):
                    href = 'https://ggzy.hefei.gov.cn' + '/' + href.lstrip('./')

                info = {
                    '来源网站': href,
                    '项目名称': title,
                    '项目阶段': '中标公告',
                    '发布时间': '',
                    '招标人': '', '招标人联系人': '', '招标人联系方式': '',
                    '招标代理机构': '', '招标代理机构联系人': '', '招标代理机构联系方式': '',
                    '中标人': '', '中标金额': '',
                    '项目地点': '', '招标文件': '',
                }
                all_data.append(info)
                count += 1
                if len(all_data) >= max_results:
                    break

            print(f'  第{page}页 +{count} (累计 {len(all_data)})')
            time.sleep(0.8)

        except Exception as e:
            print(f'  第{page}页失败: {e}')

    return all_data


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    import urllib3
    urllib3.disable_warnings()

    print('=' * 60)
    print('开始采集招标补充信息...')
    existing = load_existing_titles()
    print(f'已有 {len(existing)} 条项目标题，将跳过重复')

    data = scrape_ccgp(max_results=200, existing_titles=existing)

    if len(data) < 100:
        fb = scrape_anhui_fallback(max_results=200 - len(data), existing_titles=existing)
        data.extend(fb)

    if data:
        df = pd.DataFrame(data)
        df = df.drop_duplicates(subset=['项目名称'])
        df = df[df['项目名称'].str.len() > 4]
        df = df.reset_index(drop=True)
        df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f'\n成功保存 {len(df)} 条招标补充数据到 {OUTPUT_FILE}')
    else:
        print('\n未获取到招标补充数据')


if __name__ == '__main__':
    main()
