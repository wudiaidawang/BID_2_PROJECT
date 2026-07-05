"""
采集物资报价信息 — 从已有 bid_data 深度提取
8789条招标记录中包含: 项目名称(产品描述)、预算、中标金额(实际成交价)、采购人/中标人(供应商)、地址
这是最可靠的本地数据源，无需外部网站
输出: data/raw/price_data.xlsx (目标 ~400 条)
"""

import pandas as pd
import re
import os
import time

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'raw')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'price_data.xlsx')
BID_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bid_data.xlsx')

# 产品类型关键词 → 分类映射
CATEGORY_MAP = {
    '挖掘机|装载机|推土机|起重机|压路机|叉车|搅拌机|摊铺机|平地机|钻机': '工程机械',
    '钢材|钢筋|钢管|钢板|型钢|螺纹钢|线材|不锈钢|工字钢|槽钢': '建材钢材',
    '水泥|混凝土|沥青|砂浆|砂石|砖瓦|石灰': '建材',
    '电缆|电线|配电|变压器|开关柜|断路器|互感器|避雷器': '电气设备',
    '水泵|阀门|管道|管材|法兰|弯头|三通|水表': '给排水/泵阀',
    '路灯|灯具|照明|LED|景观灯|庭院灯': '照明设备',
    '服务器|交换机|路由器|防火墙|电脑|计算机|打印机': 'IT设备',
    '监控|摄像头|门禁|报警|安防|安检': '安防设备',
    '空调|暖通|通风|制冷|供暖|锅炉|散热器': '暖通设备',
    '污水处理|除尘|脱硫|脱硝|垃圾|环卫|保洁': '环保环卫',
    '医疗器械|超声|CT|监护仪|呼吸机|麻醉机|X光|内窥镜': '医疗设备',
    '家具|办公桌|文件柜|会议桌|沙发|床|椅|柜': '办公家具',
    '汽车|车辆|客车|货车|消防车|救护车|洒水车|扫路车': '车辆',
    '软件|系统开发|平台|APP|小程序|网站': 'IT服务',
    '物业|保安|保洁|绿化|维修|检测|监理|设计|咨询': '服务类',
    '办公用品|文具|纸张|耗材|墨盒|硒鼓': '办公用品',
    '实验室|仪器|检测仪|测量仪|分析仪|试验机': '仪器仪表',
    '服装|制服|工作服|校服|被服|窗帘': '服装纺织',
    '食品|食材|餐饮|食堂|粮油|蔬菜|肉类': '食品供应',
    '药品|疫苗|试剂|耗材|输液器|注射器': '医药耗材',
}


def classify_product(name):
    for pattern, category in CATEGORY_MAP.items():
        if re.search(pattern, name):
            return category
    return '其他'


def extract_brand(name, winner):
    """从项目名和中标人中提取品牌"""
    brands = ['华为', '联想', '戴尔', '惠普', '浪潮', '曙光', '新华三', 'H3C', '锐捷', '深信服',
              '格力', '美的', '海尔', '海信', '大金', '三菱',
              '三一', '中联重科', '徐工', '柳工', '龙工', '山推', '厦工', '合力', '杭叉',
              '宝钢', '鞍钢', '首钢', '太钢', '马钢', '沙钢',
              '海康威视', '大华', '宇视', '天地伟业',
              '正泰', '德力西', '施耐德', '西门子', 'ABB',
              '碧水源', '中电环保', '启迪环境', '龙净环保',
              '迈瑞', '联影', '东软', '万东', '安科',
              '方正', '紫光', '同方', '长城',
              '上上电缆', '远东电缆', '宝胜', '亨通',
              '凯泉', '南方泵业', '连成', '东方泵业',
              '圣奥', '震旦', '欧林', '兆生']
    for b in brands:
        if b in name or (winner and b in winner):
            return b
    return ''


def extract_price_info():
    """从 bid_data 提取价格相关信息"""
    print('从 bid_data 提取价格数据...')
    df = pd.read_excel(BID_DATA)
    results = []

    # 优先有预算的 + 有中标金额的
    df_has_amount = df[df['中标金额'].notna() & (df['中标金额'] > 0)]

    # 每个省份每品类取一些，保证多样性
    seen_provinces = set()

    for _, row in df_has_amount.iterrows():
        name = str(row.get('项目名称', ''))
        budget = row.get('预算', 0) if pd.notna(row.get('预算')) else 0
        amount = row.get('中标金额', 0)
        winner = str(row.get('中标人', ''))
        buyer = str(row.get('采购人', ''))
        province = str(row.get('省份', ''))
        city = str(row.get('市区', ''))
        county = str(row.get('县城', ''))
        pub_time = str(row.get('发布时间', ''))[:10]
        source = str(row.get('来源', ''))

        category = classify_product(name)
        brand = extract_brand(name, winner)

        # 构建供应商地址
        addr_parts = [p for p in [province, city, county] if p and p != 'nan']
        address = ''.join(addr_parts)

        # 去重: 同一个项目名称只取一次
        name_key = name[:50]

        results.append({
            '来源网站': '',
            '物资名称': name[:120],
            '采集时间': pub_time,
            '供应商名称': winner if winner and winner != 'nan' else buyer,
            '报价_预算': f'{budget}元' if budget else '',
            '报价_中标价': f'{amount}元' if amount else '',
            '供应商地址': address,
            '所在省份': province,
            '所在市区': city,
            '所在县城': county,
            '采购来源': source,
            '产品分类': category,
            '品牌': brand,
            '搜索关键词': f'bid_data_{category}',
            '数据ID': name_key,
        })

    print(f'  初步提取 {len(results)} 条')

    # 去重
    seen = set()
    deduped = []
    for r in results:
        if r['数据ID'] not in seen:
            seen.add(r['数据ID'])
            deduped.append(r)
    print(f'  去重后 {len(deduped)} 条')

    return deduped


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print('=' * 60)
    print('开始从 bid_data 提取价格/物资数据...')

    all_data = extract_price_info()

    # 保证每类都有覆盖
    df = pd.DataFrame(all_data)
    df = df.drop_duplicates(subset=['数据ID'])
    df = df[df['物资名称'].str.len() > 4]

    # 按品类分层抽样，确保多样性
    final = []
    for cat in df['产品分类'].unique():
        cat_data = df[df['产品分类'] == cat]
        n = min(len(cat_data), 35)  # 每类最多35条
        final.append(cat_data.head(n))

    df_final = pd.concat(final).reset_index(drop=True)
    df_final = df_final.drop(columns=['数据ID'])

    df_final.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
    print(f'\n成功保存 {len(df_final)} 条价格数据到 {OUTPUT_FILE}')
    print(f'品类分布:\n{df_final["产品分类"].value_counts().to_string()}')


if __name__ == '__main__':
    main()
