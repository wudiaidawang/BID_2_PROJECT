"""
采集商品详细信息 — 从 bid_data 深度提取品牌/型号/参数
项目名称中常含具体产品规格 (如 "3.0T MRI"、"DN300球墨铸铁管"、"YJV22-8.7/15kV电缆")
输出: data/raw/product_data.xlsx (目标 ~300 条)
"""

import pandas as pd
import re
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'product_data.xlsx')
BID_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bid_data.xlsx')


def extract_product_specs():
    """从 bid_data 提取商品详细信息"""
    print('从 bid_data 提取商品数据...')
    df = pd.read_excel(BID_DATA)
    results = []

    # 取有中标金额且有具体产品描述的
    df_valid = df[df['中标金额'].notna() & (df['中标金额'] > 0)]

    for _, row in df_valid.iterrows():
        name = str(row.get('项目名称', ''))
        amount = row.get('中标金额', 0)
        budget = row.get('预算', 0) if pd.notna(row.get('预算')) else 0
        winner = str(row.get('中标人', ''))
        buyer = str(row.get('采购人', ''))
        province = str(row.get('省份', ''))
        city = str(row.get('市区', ''))
        county = str(row.get('县城', ''))
        pub_time = str(row.get('发布时间', ''))[:10]

        # 提取品牌
        brand = ''
        brand_patterns = [
            r'([一-龥]{2,4}(?:重工|集团|股份))',
            r'(华为|浪潮|曙光|联想|戴尔|惠普|格力|美的|海尔|海信|三一|中联|徐工|柳工|' +
            r'龙工|宝钢|太钢|正泰|德力西|海康|大华|迈瑞|联影|碧水源|凯泉|佛照|欧普|雷士|' +
            r'圣奥|震旦|方太|老板|华帝|万家乐|万和|苏泊尔|九阳|TCL|创维|长虹|康佳)',
        ]
        for pat in brand_patterns:
            m = re.search(pat, name)
            if m:
                brand = m.group(1)
                break
        if not brand:
            for pat in brand_patterns:
                m = re.search(pat, winner)
                if m:
                    brand = m.group(1)
                    break

        # 提取产品类型
        prod_type = ''
        type_patterns = [
            (r'(大型|中型|小型|微型|超大型)', '规格类型'),
            (r'(电动|手动|液压|柴油|汽油|电力|气动)', '驱动类型'),
            (r'(国产|进口)', '来源类型'),
            (r'(工程机械|医疗设备|IT设备|办公家具|消防车辆|环卫设备|' +
             r'实验室仪器|安防监控|暖通空调|给排水|电气设备|建材|绿化)', '产品大类'),
        ]
        for pat, label in type_patterns:
            m = re.search(pat, name)
            if m:
                prod_type = m.group(1)
                break

        # 提取产品参数（规格型号等）
        params = {}
        # 尺寸参数
        dim_match = re.search(r'(\d+\.?\d*)\s*[×xX*]\s*(\d+\.?\d*)\s*(?:[×xX*]\s*(\d+\.?\d*))?\s*(mm|cm|m|米|毫米|厘米)', name)
        if dim_match:
            params['规格尺寸'] = dim_match.group(0)

        # 重量/容量
        weight_match = re.search(r'(\d+\.?\d*)\s*(?:吨|t|kg|公斤|千克|升|L|m³|立方米)', name)
        if weight_match:
            params['重量/容量'] = weight_match.group(0)

        # 功率
        power_match = re.search(r'(\d+\.?\d*)\s*(?:kW|kw|KW|千瓦|W|瓦|匹|HP)', name)
        if power_match:
            params['功率'] = power_match.group(0)

        # 电压等级
        voltage_match = re.search(r'(\d+\.?\d*)\s*(?:kV|kv|KV|V|伏)', name)
        if voltage_match:
            params['电压等级'] = voltage_match.group(0)

        # 直径/管径
        dia_match = re.search(r'DN(\d+)|[φΦ](\d+\.?\d*)', name)
        if dia_match:
            params['管径/直径'] = dia_match.group(0)

        # 面积
        area_match = re.search(r'(\d+\.?\d*)\s*(?:㎡|平方米|亩|公顷)', name)
        if area_match:
            params['面积'] = area_match.group(0)

        # 参数文本
        param_text = '; '.join([f'{k}:{v}' for k, v in params.items()])

        # 构建供应商地址
        addr_parts = [p for p in [province, city, county] if p and p != 'nan']
        address = ''.join(addr_parts)

        results.append({
            '来源网站': '',
            '物资名称': name[:120],
            '采集时间': pub_time,
            '供应商名称': winner if winner != 'nan' else buyer,
            '报价': f'{amount}元',
            '预算参考': f'{budget}元' if budget else '',
            '供应商地址': address,
            '所在省份': province,
            '所在市区': city,
            '所在县城': county,
            '品牌': brand,
            '产品类型': prod_type,
            '产品参数': param_text[:500],
            '搜索关键词': 'bid_data',
            '数据ID': name[:50],
        })

    print(f'  提取 {len(results)} 条')

    # 去重 + 过滤无意义的记录
    seen = set()
    deduped = []
    for r in results:
        if r['数据ID'] not in seen and len(r['物资名称']) > 4:
            seen.add(r['数据ID'])
            if r['品牌'] or r['产品参数'] or r['产品类型']:
                deduped.append(r)

    print(f'  去重后 {len(deduped)} 条 (含品牌/参数/类型)')
    return deduped


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print('=' * 60)
    print('开始从 bid_data 提取商品详细信息...')

    all_data = extract_product_specs()

    df = pd.DataFrame(all_data)
    df = df.drop(columns=['数据ID'])

    # 有品牌 + 有参数的优先
    with_brand = df[df['品牌'] != '']
    with_params = df[df['产品参数'] != '']
    others = df[(df['品牌'] == '') & (df['产品参数'] == '')]

    # 合并: 有品牌的 + 有参数的 + 其余的补齐
    final = pd.concat([
        with_brand.head(150),
        with_params.head(100),
        others.head(50),
    ]).drop_duplicates(subset=['物资名称']).reset_index(drop=True)

    final.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
    print(f'\n成功保存 {len(final)} 条商品数据到 {OUTPUT_FILE}')
    print(f'有品牌: {final["品牌"].astype(bool).sum()} | 有参数: {final["产品参数"].astype(bool).sum()}')


if __name__ == '__main__':
    main()
