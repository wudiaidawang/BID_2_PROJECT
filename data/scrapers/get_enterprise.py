"""
采集企业信息 — 从 bid_data 深度提取
从已有招标数据中提取企业画像: 中标企业、采购单位、代理机构
每条记录包含企业名、地址、活跃省份、中标次数、主要业务领域等
输出: data/raw/enterprise_data.xlsx (目标 ~300 条)
"""

import pandas as pd
import re
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'enterprise_data.xlsx')
BID_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bid_data.xlsx')


def extract_enterprise_info():
    """从 bid_data 提取企业画像"""
    print('从 bid_data 提取企业信息...')
    df = pd.read_excel(BID_DATA)

    # 构建企业→记录映射
    enterprise_map = {}  # name -> {records, provinces, buyers, categories, total_amount, ...}

    for _, row in df.iterrows():
        winner = str(row.get('中标人', '')).strip()
        buyer = str(row.get('采购人', '')).strip()
        agency = str(row.get('代理机构', '')).strip()
        name = str(row.get('项目名称', ''))
        amount = row.get('中标金额', 0) if pd.notna(row.get('中标金额')) else 0
        province = str(row.get('省份', ''))
        city = str(row.get('市区', ''))
        county = str(row.get('县城', ''))
        category = str(row.get('类别', ''))
        pub_time = str(row.get('发布时间', ''))[:10]

        # 处理中标人
        for ent_name in [winner]:
            if not ent_name or ent_name == 'nan' or len(ent_name) < 4 or len(ent_name) > 50:
                continue
            if ent_name not in enterprise_map:
                enterprise_map[ent_name] = {
                    'projects': [], 'provinces': set(), 'buyers': set(),
                    'total_amount': 0, 'bid_count': 0, 'categories': set(),
                    'cities': set(), 'latest_time': '',
                }
            ent = enterprise_map[ent_name]
            ent['projects'].append(name[:80])
            if province and province != 'nan':
                ent['provinces'].add(province)
            if city and city != 'nan':
                ent['cities'].add(city)
            if buyer and buyer != 'nan':
                ent['buyers'].add(buyer)
            if category and category != 'nan':
                ent['categories'].add(category)
            if pub_time and pub_time > ent['latest_time']:
                ent['latest_time'] = pub_time
            ent['total_amount'] += amount
            ent['bid_count'] += 1

    print(f'  提取到 {len(enterprise_map)} 家企业')

    # 过滤: 至少有2次中标记录的
    results = []
    for ent_name, info in enterprise_map.items():
        if info['bid_count'] < 1:
            continue

        provinces = sorted(info['provinces'])
        cities = sorted(info['cities'])
        buyers = sorted(info['buyers'])[:5]
        categories = sorted(info['categories'])[:5]

        # 推断企业类型
        if '代理机构' in ent_name or '招标' in ent_name or info['bid_count'] > 50:
            ent_type = '招标代理'
        elif any(c in ''.join(categories) for c in ['服务', '咨询', '设计', '监理', '检测', '物业']):
            ent_type = '服务类企业'
        elif any(c in ''.join(categories) for c in ['设备', '器材', '仪器', '机械']):
            ent_type = '设备类企业'
        elif any(c in ''.join(categories) for c in ['建筑', '工程', '建材', '施工']):
            ent_type = '工程类企业'
        elif any(c in ''.join(categories) for c in ['IT', '软件', '系统', '服务器', '网络']):
            ent_type = 'IT类企业'
        elif any(c in ''.join(categories) for c in ['医疗', '药品', '医药']):
            ent_type = '医药类企业'
        else:
            ent_type = '综合类企业'

        results.append({
            '企业名称': ent_name,
            '企业类型': ent_type,
            '活跃省份': '、'.join(provinces[:5]),
            '活跃城市': '、'.join(cities[:5]),
            '中标次数': info['bid_count'],
            '中标总金额(万元)': round(info['total_amount'] / 10000, 2),
            '平均中标金额(万元)': round(info['total_amount'] / info['bid_count'] / 10000, 2) if info['bid_count'] else 0,
            '主要客户': '、'.join(buyers[:3]),
            '业务领域': '、'.join(categories[:5]),
            '最近中标时间': info['latest_time'],
            '代表项目': info['projects'][0][:100] if info['projects'] else '',
            '信息来源': 'bid_data深度提取',
        })

    # 按中标次数降序
    results.sort(key=lambda x: x['中标次数'], reverse=True)
    print(f'  生成 {len(results)} 条企业画像')
    return results


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print('=' * 60)
    print('开始从 bid_data 提取企业画像信息...')

    all_data = extract_enterprise_info()

    df = pd.DataFrame(all_data)
    # 去重
    df = df.drop_duplicates(subset=['企业名称'])
    df = df.reset_index(drop=True)

    # 分层: 高频企业(top100) + 中等频率 + 低频补充
    high = df[df['中标次数'] >= 5].head(100)
    mid = df[(df['中标次数'] >= 2) & (df['中标次数'] < 5)].head(100)
    low = df[df['中标次数'] == 1].head(100)

    final = pd.concat([high, mid, low]).drop_duplicates(subset=['企业名称']).reset_index(drop=True)

    final.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
    print(f'\n成功保存 {len(final)} 条企业数据到 {OUTPUT_FILE}')
    print(f'高频(>=5次): {len(high)} | 中频(2-4次): {len(mid)} | 低频(1次): {len(low)}')
    print(f'企业类型分布:')
    print(final['企业类型'].value_counts().to_string())


if __name__ == '__main__':
    main()
