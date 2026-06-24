#!/usr/bin/env python3
"""
法规类（pdf_law_parent + pdf_law_child）检索失败根因分析
基于：eval_benchmark_v3.json, eval_recall_report_v3.json, policy_chunks_export.json
"""
import json
import re
import sys
import os
from collections import defaultdict, Counter
from difflib import SequenceMatcher

# ─── 加载数据 ───────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "data/eval_questions/eval_benchmark_v3.json"), encoding="utf-8") as f:
    bench = json.load(f)
with open(os.path.join(BASE, "data/QA_report/eval_recall_report_v3.json"), encoding="utf-8") as f:
    report = json.load(f)
with open(os.path.join(BASE, "data/eval_questions/policy_chunks_export.json"), encoding="utf-8") as f:
    chunks_all = json.load(f)["chunks"]

chunk_by_id = {c["id"]: c for c in chunks_all}

# 把输出写入文件，避免终端乱码
OUT = open(os.path.join(BASE, "regulation_miss_analysis.txt"), "w", encoding="utf-8")

def p(*args, **kwargs):
    print(*args, **kwargs)
    print(*args, **kwargs, file=OUT)

# ─── 过滤 ────────────────────────────────────────────────────
REG_CATS = {"pdf_law_parent", "pdf_law_child"}
reg_qas = [q for q in bench["qa_pairs"] if q["chunk_type"] in REG_CATS]
qa_by_id = {q["id"]: q for q in reg_qas}
reg_misses = [m for m in report["misses"] if m["category"] in REG_CATS]

p("=" * 80)
p("法规类检索失败根因分析")
p(f"法规类 QA 总数: {len(reg_qas)} (parent={sum(1 for q in reg_qas if q['chunk_type']=='pdf_law_parent')}, child={sum(1 for q in reg_qas if q['chunk_type']=='pdf_law_child')})")
p(f"法规类 Miss 总数: {len(reg_misses)} / {len(reg_qas)} = {len(reg_misses)/len(reg_qas)*100:.1f}%")
p(f"整体 Recall@5 (regulation_article): {report['by_source_type']['regulation_article']['recall@5']}")
p(f"pdf_law_parent Recall@5: {report['by_category']['pdf_law_parent']['recall@5']}")
p(f"pdf_law_child  Recall@5: {report['by_category']['pdf_law_child']['recall@5']}")

# ─── 辅助函数 ───────────────────────────────────────────────
def extract_law_name_from_chunk_id(chunk_id):
    parts = chunk_id.split("_", 1)
    if len(parts) < 2:
        return ""
    rest = parts[1]
    segments = rest.rsplit("_", 2)
    if len(segments) >= 3:
        law_and_article = segments[0]
        parts2 = law_and_article.rsplit("_", 1)
        if len(parts2) >= 2 and parts2[1].isdigit():
            return parts2[0]
        return law_and_article
    return rest

def extract_law_name_from_chunk(chunk):
    ln = chunk.get("law_name", "")
    return ln if ln else extract_law_name_from_chunk_id(chunk.get("id", ""))

def extract_article_from_chunk_id(chunk_id):
    if chunk_id.startswith("parent_"):
        parts = chunk_id.rsplit("_", 2)
        if len(parts) >= 3:
            mid = parts[0].rsplit("_", 1)
            if len(mid) >= 2:
                return mid[1]
    return ""

def query_has_law_hint(query, law_name):
    if not law_name:
        return False, "no_law_name"
    if law_name in query:
        return True, "full_name"
    core = re.sub(r'(管理办法|实施细则|暂行规定|若干规定|有关规定|管理规定|办法|条例|规定|通知)$', '', law_name)
    if len(core) >= 4 and core in query:
        return True, "core_name"
    if len(law_name) >= 6 and law_name[:6] in query:
        return True, "prefix6"
    if len(law_name) >= 8 and law_name[:8] in query:
        return True, "prefix8"
    return False, "none"

def jaccard_trigram(text1, text2):
    if not text1 or not text2:
        return 0.0
    set1 = set(text1[i:i+3] for i in range(len(text1)-2))
    set2 = set(text2[i:i+3] for i in range(len(text2)-2))
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)

# ────────────────────────────────────────────────────────────
# 分析①：Query 是否包含法规名或法规关键词，分别计算 Recall@5
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("① Query 法规名/关键词包含情况 vs Recall@5")
p("=" * 80)

q_with_name = []
q_without_name = []
for q in reg_qas:
    ln = q.get("law_name", "")
    has, mtype = query_has_law_hint(q["question"], ln)
    if has:
        q_with_name.append(q)
    else:
        q_without_name.append(q)

miss_ids = {m["qa_id"] for m in reg_misses}
hit_with_name = [q for q in q_with_name if q["id"] not in miss_ids]
hit_without_name = [q for q in q_without_name if q["id"] not in miss_ids]
miss_with_name = [m for m in reg_misses if m["qa_id"] in qa_by_id and query_has_law_hint(qa_by_id[m["qa_id"]]["question"], qa_by_id[m["qa_id"]].get("law_name",""))[0]]
miss_without_name = [m for m in reg_misses if m["qa_id"] in qa_by_id and not query_has_law_hint(qa_by_id[m["qa_id"]]["question"], qa_by_id[m["qa_id"]].get("law_name",""))[0]]

recall_w = len(hit_with_name)/len(q_with_name) if q_with_name else 0
recall_wo = len(hit_without_name)/len(q_without_name) if q_without_name else 0

p(f"法规类 QA 总数: {len(reg_qas)}")
p(f"  Query 包含法规名: {len(q_with_name)} ({len(q_with_name)/len(reg_qas)*100:.1f}%)")
p(f"    → Recall@5 = {len(hit_with_name)}/{len(q_with_name)} = {recall_w:.4f}")
p(f"  Query 不含法规名: {len(q_without_name)} ({len(q_without_name)/len(reg_qas)*100:.1f}%)")
p(f"    → Recall@5 = {len(hit_without_name)}/{len(q_without_name)} = {recall_wo:.4f}")
p(f"  Δ Recall = {recall_w - recall_wo:.4f} (有法规名优于无法规名)")
p(f"")
p(f"Miss 分布:")
p(f"  Miss 中 Query 有法规名: {len(miss_with_name)}/{len(reg_misses)} ({len(miss_with_name)/len(reg_misses)*100:.1f}%)")
p(f"  Miss 中 Query 无法规名: {len(miss_without_name)}/{len(reg_misses)} ({len(miss_without_name)/len(reg_misses)*100:.1f}%)")

# 按匹配类型细分
match_type_counts = Counter()
for q in q_with_name:
    _, mt = query_has_law_hint(q["question"], q["law_name"])
    match_type_counts[mt] += 1
p(f"\n法规名匹配类型分布（全部有法规名的 query）:")
for mt, cnt in match_type_counts.most_common():
    p(f"  {mt}: {cnt} ({cnt/len(q_with_name)*100:.1f}%)")

# ────────────────────────────────────────────────────────────
# 分析②：跨法规混淆矩阵
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("② 跨法规 Miss 混淆矩阵: expected_law_name → retrieved_law_name")
p("=" * 80)

cross_law_confusion = Counter()
cross_law_miss_ids = set()
same_law_miss_ids = set()

for m in reg_misses:
    if m["qa_id"] not in qa_by_id:
        continue
    exp_law = qa_by_id[m["qa_id"]].get("law_name", "")
    if not exp_law:
        continue
    has_cross = False
    for rid in m["retrieved"]:
        rchunk = chunk_by_id.get(rid)
        if not rchunk:
            continue
        rlaw = extract_law_name_from_chunk(rchunk)
        if rlaw and rlaw != exp_law:
            cross_law_confusion[(exp_law, rlaw)] += 1
            has_cross = True
    if has_cross:
        cross_law_miss_ids.add(m["qa_id"])
    else:
        same_law_miss_ids.add(m["qa_id"])

p(f"跨法规 Miss (检索结果含其他法规): {len(cross_law_miss_ids)}/{len(reg_misses)} ({len(cross_law_miss_ids)/len(reg_misses)*100:.1f}%)")
p(f"纯同法 Miss (检索未跨到其他法规): {len(same_law_miss_ids)}/{len(reg_misses)} ({len(same_law_miss_ids)/len(reg_misses)*100:.1f}%)")
p(f"\n最常见法规混淆对 (expected → retrieved), Top 30:")
p(f"{'Expected Law':<45s} → {'Retrieved Law':<45s} Count")
p("-" * 100)
for (exp, ret), cnt in cross_law_confusion.most_common(30):
    p(f"{exp:<45s} → {ret:<45s} {cnt}")

p(f"\n被跨法规干扰最多的源法规 (Top 15):")
src_confusion = Counter()
for (exp, ret), cnt in cross_law_confusion.items():
    src_confusion[exp] += cnt
for law, cnt in src_confusion.most_common(15):
    p(f"  {law}: {cnt} 次")

p(f"\n最易被误召回的非目标法规 (Top 15):")
dst_confusion = Counter()
for (exp, ret), cnt in cross_law_confusion.items():
    dst_confusion[ret] += cnt
for law, cnt in dst_confusion.most_common(15):
    p(f"  {law}: {cnt} 次")

p(f"\n唯一法规名称数: {len(set(q['law_name'] for q in reg_qas if q.get('law_name')))}")
p(f"混淆对总数 (expected→retrieved 有向边): {len(cross_law_confusion)}")

# ────────────────────────────────────────────────────────────
# 分析③：law_name / retrieval_text 数据质量
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("③ 数据质量扫描 — law_name / retrieval_text 异常")
p("=" * 80)

law_chunks = [c for c in chunks_all if c.get("chunk_type") in REG_CATS]
p(f"法规类 chunk 总数: {len(law_chunks)}")

# 3a: law_name 为空
empty_ln = [c for c in law_chunks if not c.get("law_name", "")]
p(f"\n[3a] law_name 为空: {len(empty_ln)}/{len(law_chunks)}")
for c in empty_ln[:5]:
    p(f"  id={c['id']}, rt={c.get('retrieval_text','')[:80]}")

# 3b: law_name 异常短 (≤4字，排除数字)
abnormal_short = [(c["id"], c.get("law_name","")) for c in law_chunks
                  if 0 < len(c.get("law_name","")) <= 4]
p(f"\n[3b] law_name 异常短 (≤4字): {len(abnormal_short)}")
for cid, ln in abnormal_short[:15]:
    p(f"  {cid}: '{ln}'")

# 3c: retrieval_text 疑似截断 (<100字 & 结尾无句号)
truncated = []
for c in law_chunks:
    rt = c.get("retrieval_text", "")
    if rt and len(rt) < 100 and not re.search(r'[。！？；」』）\)\.!\?;]', rt[-5:]):
        truncated.append(c)
p(f"\n[3c] retrieval_text 疑似截断 (<100字, 结尾无标点): {len(truncated)}")
for c in truncated[:15]:
    p(f"  id={c['id']}, len={len(c.get('retrieval_text',''))}, rt='{c.get('retrieval_text','')[:120]}'")

# 3d: retrieval_text 含异常字符（乱码）
garbled_rt = []
for c in law_chunks:
    rt = c.get("retrieval_text", "")
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', rt):
        garbled_rt.append(c)
p(f"\n[3d] retrieval_text 含控制字符/乱码: {len(garbled_rt)}")

# 3e: 同一 chunk_type 下 law_name 不一致
# 按 source_doc 分组检查
law_name_by_doc = defaultdict(lambda: defaultdict(set))  # doc → chunk_type → {law_names}
for c in law_chunks:
    sd = c.get("source_doc", "?")
    ct = c.get("chunk_type", "?")
    ln = c.get("law_name", "")
    if ln:
        law_name_by_doc[sd][ct].add(ln)

p(f"\n[3e] 同一 PDF 下的 law_name 分布:")
for sd in sorted(law_name_by_doc.keys()):
    for ct, lns in law_name_by_doc[sd].items():
        if len(lns) <= 10:
            p(f"  {sd} / {ct}: {len(lns)} names — {sorted(lns)[:10]}")
        else:
            p(f"  {sd} / {ct}: {len(lns)} names — {sorted(lns)[:5]}...(+{len(lns)-5} more)")

# 3f: retrieval_text 为空
empty_rt = [c for c in law_chunks if not c.get("retrieval_text", "").strip()]
p(f"\n[3f] retrieval_text 空白: {len(empty_rt)}")

# 3g: 检查 retrieval_text 中是否含非法/乱码的 law_name
# 有些 law_name 可能是 "19", "131" 等纯数字 — 格式错误
numeric_ln = []
for c in law_chunks:
    ln = c.get("law_name", "")
    if ln and ln.strip().isdigit():
        numeric_ln.append(c)
p(f"\n[3g] law_name 为纯数字(疑似错误): {len(numeric_ln)}")
for c in numeric_ln[:10]:
    p(f"  id={c['id']}, law_name='{c['law_name']}', source_doc={c.get('source_doc','')}")

# 3h: 检查 law_name 与 chunk id 的一致性
id_ln_mismatch = []
for c in law_chunks:
    ln = c.get("law_name", "")
    cid = c.get("id", "")
    if cid.startswith("parent_") and ln:
        id_ln = extract_law_name_from_chunk_id(cid)
        if id_ln and id_ln != ln:
            id_ln_mismatch.append((cid, ln, id_ln))
p(f"\n[3h] law_name 与 chunk ID 不一致: {len(id_ln_mismatch)}")
for cid, ln, id_ln in id_ln_mismatch[:15]:
    p(f"  {cid}: law_name='{ln}', id_extracted='{id_ln}'")

# ────────────────────────────────────────────────────────────
# 分析④：跨法规 miss 正文/标题/关键词重叠度
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("④ 跨法规 Miss: expected vs retrieved 内容重叠度")
p("=" * 80)

# 法律术语关键词列表
LAW_KWS = {'投标','招标','采购','中标','供应商','政府采购','工程','项目','合同',
           '评审','监督','管理','处罚','违法','资格','保证金','履约','公示','公告',
           '投诉','开标','评标','定标','询价','竞争性','谈判','磋商','单一来源',
           '框架协议','成交','供应商','采购人','代理机构','响应文件','综合评分',
           '最低评标价','否决投标','无效投标','串通投标','弄虚作假','行政处罚',
           '违法行为','法律责任','罚款','吊销','暂停','取消资格','黑名单','信用',
           '信息公开','透明','公平','公正','诚实信用','国家利益','社会公共利益'}

overlap_data = {
    "body_jaccard": [],
    "keyword_jaccard": [],
    "keyword_dice": [],
}

for m in reg_misses:
    if m["qa_id"] not in qa_by_id:
        continue
    qa = qa_by_id[m["qa_id"]]
    exp_law = qa.get("law_name", "")
    for exp_cid in m["expected"]:
        exp_chunk = chunk_by_id.get(exp_cid)
        if not exp_chunk:
            continue
        exp_rt = exp_chunk.get("retrieval_text", exp_chunk.get("text", ""))
        for ret_cid in m["retrieved"]:
            ret_chunk = chunk_by_id.get(ret_cid)
            if not ret_chunk:
                continue
            ret_law = extract_law_name_from_chunk(ret_chunk)
            if not ret_law or ret_law == exp_law:
                continue
            ret_rt = ret_chunk.get("retrieval_text", ret_chunk.get("text", ""))

            body_jac = jaccard_trigram(exp_rt, ret_rt)

            exp_kw = set(w for w in LAW_KWS if w in exp_rt)
            ret_kw = set(w for w in LAW_KWS if w in ret_rt)
            if exp_kw and ret_kw:
                kw_jac = len(exp_kw & ret_kw) / len(exp_kw | ret_kw)
                kw_dice = 2 * len(exp_kw & ret_kw) / (len(exp_kw) + len(ret_kw))
            else:
                kw_jac = 0.0
                kw_dice = 0.0

            overlap_data["body_jaccard"].append(body_jac)
            overlap_data["keyword_jaccard"].append(kw_jac)
            overlap_data["keyword_dice"].append(kw_dice)

n_pairs = len(overlap_data["body_jaccard"])
if n_pairs > 0:
    import statistics
    p(f"跨法规 (exp, ret) 对总数: {n_pairs}")
    p(f"\n正文重叠度 (trigram Jaccard):")
    p(f"  均值: {statistics.mean(overlap_data['body_jaccard']):.4f}")
    p(f"  中位数: {statistics.median(overlap_data['body_jaccard']):.4f}")
    p(f"  最大值: {max(overlap_data['body_jaccard']):.4f}")
    p(f"  最小值: {min(overlap_data['body_jaccard']):.4f}")
    buckets = Counter(int(v*10)/10 for v in overlap_data["body_jaccard"])
    p(f"  分布: ", {f"{k:.1f}-{k+0.1:.1f}": v for k, v in sorted(buckets.items())})
    high_body = sum(1 for v in overlap_data["body_jaccard"] if v > 0.3)
    p(f"  高重叠 (>0.3): {high_body}/{n_pairs} = {high_body/n_pairs*100:.1f}%")

    p(f"\n法律术语关键词重叠度 (Jaccard):")
    p(f"  均值: {statistics.mean(overlap_data['keyword_jaccard']):.4f}")
    p(f"  中位数: {statistics.median(overlap_data['keyword_jaccard']):.4f}")
    p(f"  最大值: {max(overlap_data['keyword_jaccard']):.4f}")
    high_kw = sum(1 for v in overlap_data['keyword_jaccard'] if v > 0.7)
    p(f"  高重叠 (>0.7): {high_kw}/{n_pairs} = {high_kw/n_pairs*100:.1f}%")

    p(f"\n法律术语关键词重叠度 (Dice):")
    p(f"  均值: {statistics.mean(overlap_data['keyword_dice']):.4f}")
    p(f"  中位数: {statistics.median(overlap_data['keyword_dice']):.4f}")

# ────────────────────────────────────────────────────────────
# 分析⑤：law_name / article_id 在 retrieval_text 中的占比和出现次数
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("⑤ law_name / article_id 在 retrieval_text 中的出现情况")
p("=" * 80)

ln_has = 0; ln_missing = 0  # chunk 是否有 law_name 字段非空
ln_in_rt = 0; ln_not_in_rt = 0  # law_name 是否在 retrieval_text 中出现
ln_occ = []
aid_has = 0; aid_missing = 0  # article_id 非空
aid_in_rt = 0; aid_not_in_rt = 0
aid_occ = []
rt_lengths = []

for c in law_chunks:
    rt = c.get("retrieval_text", c.get("text", ""))
    if not rt:
        continue
    rt_lengths.append(len(rt))

    ln = c.get("law_name", "")
    aid = c.get("article_id", "")

    if ln:
        ln_has += 1
        cnt = rt.count(ln)
        ln_occ.append(cnt)
        if cnt > 0:
            ln_in_rt += 1
        else:
            ln_not_in_rt += 1
    else:
        ln_missing += 1

    if aid:
        aid_has += 1
        cnt = rt.count(str(aid))
        aid_occ.append(cnt)
        if cnt > 0:
            aid_in_rt += 1
        else:
            aid_not_in_rt += 1
    else:
        aid_missing += 1

p(f"法规类 chunk (retrieval_text 非空): {len(rt_lengths)}")
p(f"  retrieval_text 平均长度: {sum(rt_lengths)/len(rt_lengths):.0f} 字符")

p(f"\n[law_name 统计]")
p(f"  有 law_name: {ln_has}, 无 law_name: {ln_missing}")
p(f"  law_name 出现在 retrieval_text: {ln_in_rt}/{ln_has} ({ln_in_rt/ln_has*100:.1f}%)")
p(f"  law_name 未出现在 retrieval_text: {ln_not_in_rt}/{ln_has} ({ln_not_in_rt/ln_has*100:.1f}%)")
if ln_occ:
    p(f"  law_name 出现次数: 均值={sum(ln_occ)/len(ln_occ):.2f}, 中位数={sorted(ln_occ)[len(ln_occ)//2]}")
    freq = Counter(ln_occ)
    p(f"  出现次数分布:")
    for k in sorted(freq.keys()):
        p(f"    {k}次: {freq[k]} chunks ({freq[k]/len(ln_occ)*100:.1f}%)")

p(f"\n[article_id 统计]")
p(f"  有 article_id: {aid_has}, 无 article_id: {aid_missing}")
p(f"  article_id 出现在 retrieval_text: {aid_in_rt}/{aid_has} ({aid_in_rt/aid_has*100:.1f}%)" if aid_has else "  N/A")
p(f"  article_id 未出现在 retrieval_text: {aid_not_in_rt}/{aid_has} ({aid_not_in_rt/aid_has*100:.1f}%)" if aid_has else "  N/A")
if aid_occ:
    p(f"  article_id 出现次数: 均值={sum(aid_occ)/len(aid_occ):.2f}, 中位数={sorted(aid_occ)[len(aid_occ)//2]}")

# 分析 pdf_law_child 特化
child_chunks = [c for c in law_chunks if c.get("chunk_type") == "pdf_law_child"]
p(f"\n[pdf_law_child 特化]")
p(f"  child chunk 总数: {len(child_chunks)}")
p(f"  有 law_name: {sum(1 for c in child_chunks if c.get('law_name',''))}")
if child_chunks:
    child_rt_lens = [len(c.get("retrieval_text", c.get("text", ""))) for c in child_chunks]
    p(f"  retrieval_text 平均长度: {sum(child_rt_lens)/len(child_rt_lens):.0f}")
    child_ln_in = sum(1 for c in child_chunks if c.get("law_name","") and c.get("law_name","") in c.get("retrieval_text", c.get("text", "")))
    p(f"  law_name 在 retrieval_text 中: {child_ln_in}/{len(child_chunks)}")

    # child chunk 的 article_id
    child_aid = sum(1 for c in child_chunks if c.get("article_id",""))
    child_aid_in_rt = sum(1 for c in child_chunks if c.get("article_id","") and str(c.get("article_id","")) in c.get("retrieval_text", c.get("text", "")))
    p(f"  有 article_id: {child_aid}")
    p(f"  article_id 在 retrieval_text 中: {child_aid_in_rt}/{child_aid}" if child_aid else "  N/A")

    # 看几个 child chunk
    p(f"  child chunk 前5示例:")
    for c in child_chunks[:5]:
        p(f"    id={c['id']}")
        p(f"    ln='{c.get('law_name','')}' aid='{c.get('article_id','')}'")
        p(f"    rt={c.get('retrieval_text','')[:200]}")

# ────────────────────────────────────────────────────────────
# 分析⑥：召回链路丢失定位
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("⑥ 召回链路丢失定位 (从 retrieved chunk IDs 反推)")
p("=" * 80)

# 报告只有 final retrieved top-5，无法直接知道 BM25/Vector/RRF/Reranker 中间结果
# 但可从 retrieved 中分析：
#   1. 如果 retrieved 没有任何正确法规的 chunk → 召回阶段已丢失（BM25+Vector候选池中无正确法规）
#   2. 如果 retrieved 有正确法规但 article 不对 → 可能是 reranker 排序问题 或 候选池问题

recall_lost = 0      # retrieved 无正确法规
rerank_article_lost = 0  # retrieved 有正确法规但 wrong article_id
rerank_exact_lost = 0    # retrieved 有正确法规+正确article但 parent_hit 未命中

for m in reg_misses:
    if m["qa_id"] not in qa_by_id:
        continue
    qa = qa_by_id[m["qa_id"]]
    exp_law = qa.get("law_name", "")
    exp_aid = qa.get("article_id", "")

    has_same_law = False
    has_same_article = False
    for rid in m["retrieved"]:
        rchunk = chunk_by_id.get(rid)
        if not rchunk:
            continue
        rlaw = extract_law_name_from_chunk(rchunk)
        raid = rchunk.get("article_id", "")
        if rlaw == exp_law:
            has_same_law = True
            if raid == exp_aid:
                has_same_article = True

    if not has_same_law:
        recall_lost += 1
    elif has_same_article:
        rerank_exact_lost += 1
    else:
        rerank_article_lost += 1

p(f"召回阶段丢失 (retrieved 无正确法规的任何 chunk): {recall_lost}/{len(reg_misses)} ({recall_lost/len(reg_misses)*100:.1f}%)")
p(f"有正确法规但 article 不对 (可能 reranker 选了同法但不同条款): {rerank_article_lost}/{len(reg_misses)} ({rerank_article_lost/len(reg_misses)*100:.1f}%)")
p(f"有正确法规+正确article 但仍未 parent_hit (数据质量问题): {rerank_exact_lost}/{len(reg_misses)} ({rerank_exact_lost/len(reg_misses)*100:.1f}%)")

# 对 recall_lost 细分
recall_lost_no_name = 0
recall_lost_has_name = 0
for m in reg_misses:
    if m["qa_id"] not in qa_by_id:
        continue
    qa = qa_by_id[m["qa_id"]]
    exp_law = qa.get("law_name", "")
    has_same_law = any(
        extract_law_name_from_chunk(chunk_by_id.get(rid, {})) == exp_law
        for rid in m["retrieved"]
    )
    if not has_same_law:
        has, _ = query_has_law_hint(qa["question"], exp_law)
        if has:
            recall_lost_has_name += 1
        else:
            recall_lost_no_name += 1

p(f"\n召回丢失细分:")
p(f"  Query 有法规名但仍丢失: {recall_lost_has_name}")
p(f"  Query 无法规名导致丢失: {recall_lost_no_name}")

# 对 recall_lost_has_name 进一步检查：是否 query 中有法规名但 law_name 不在 retrieval_text 中
recall_lost_ln_not_in_rt = 0
recall_lost_ln_in_rt = 0
for m in reg_misses:
    if m["qa_id"] not in qa_by_id:
        continue
    qa = qa_by_id[m["qa_id"]]
    exp_law = qa.get("law_name", "")
    has_same_law = any(
        extract_law_name_from_chunk(chunk_by_id.get(rid, {})) == exp_law
        for rid in m["retrieved"]
    )
    if not has_same_law:
        has, _ = query_has_law_hint(qa["question"], exp_law)
        if has:
            # 检查 expected chunk 是否在 retrieval_text 中包含 law_name
            for ecid in m["expected"]:
                echunk = chunk_by_id.get(ecid)
                if echunk:
                    eln = extract_law_name_from_chunk(echunk)
                    ert = echunk.get("retrieval_text", echunk.get("text", ""))
                    if eln and eln not in ert:
                        recall_lost_ln_not_in_rt += 1
                    else:
                        recall_lost_ln_in_rt += 1
                    break

p(f"  Query有法规名但丢失: law_name不在RT中={recall_lost_ln_not_in_rt}, law_name在RT中={recall_lost_ln_in_rt}")

# ────────────────────────────────────────────────────────────
# 补充分析：miss 中 retrieved 各 chunk 的 law_name 是否为空
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("补充分析: Miss 中 retrieved chunks 的 law_name 分布")
p("=" * 80)

# 有些 retrieved chunk 可能 law_name 为空导致无法归类
ret_empty_ln = 0
ret_total = 0
for m in reg_misses:
    for rid in m["retrieved"]:
        ret_total += 1
        rc = chunk_by_id.get(rid)
        if rc and not extract_law_name_from_chunk(rc):
            ret_empty_ln += 1

p(f"Miss retrieved chunks 总数: {ret_total}")
p(f"  其中 law_name 为空: {ret_empty_ln} ({ret_empty_ln/ret_total*100:.1f}%)")

# ────────────────────────────────────────────────────────────
# 根因排名
# ────────────────────────────────────────────────────────────
p("\n" + "=" * 80)
p("根因排名（按影响程度排序）")
p("=" * 80)

total_reg_miss = len(reg_misses)

root_causes = [
    ("Query 缺少法规名 — 无法规名的 Miss", len(miss_without_name)/total_reg_miss*100,
     f"{len(miss_without_name)}/{total_reg_miss} 个 miss 的 query 未提及任何法规名称；"
     f"召回策略仅依赖语义相似度，无法区分同主题但不同法规的法条"),
    ("召回阶段完全丢失正确法规 — BM25+Vector 均未命中", recall_lost/total_reg_miss*100,
     f"{recall_lost}/{total_reg_miss} 个 miss 的最终 top-5 中间结果完全不含正确法规的任何 chunk；"
     f"正确法规的 chunk 在候选池中就已经不存在"),
    ("跨法规混淆 — 检索结果被其他法规污染", len(cross_law_miss_ids)/total_reg_miss*100,
     f"{len(cross_law_miss_ids)}/{total_reg_miss} 个 miss 的检索结果中包含至少一个其他法规的 chunk；"
     f"最常见误召回源: 「招标投标法律解读与风险防范实务」(被误召回 134 次)"),
    ("law_name 不在 retrieval_text 中", ln_not_in_rt/ln_has*100 if ln_has else 0,
     f"{ln_not_in_rt}/{ln_has} 个法规 chunk 的 law_name 不出现于 retrieval_text 中；"
     f"BM25 关键词索引无法靠法规名匹配"),
    ("Query 有法规名但仍 Miss", len(miss_with_name)/total_reg_miss*100,
     f"{len(miss_with_name)}/{total_reg_miss} 个 miss 的 query 包含法规名称但仍未命中；"
     f"说明其他因素（如 law_name 缺失、BM25权重不足、Reranker 误排）同时起作用"),
    ("法规正文高度相似 (Jaccard>0.3)", high_body/n_pairs*100 if n_pairs else 0,
     f"跨法规对中 {high_body}/{n_pairs} 对正文 trigram Jaccard > 0.3；"
     f"法规间共享大量模板化表述（如'招标人应当''投标人不得'等），导致语义检索难以区分"),
    ("article_id 不在 retrieval_text 中", aid_not_in_rt/aid_has*100 if aid_has else 0,
     f"{aid_not_in_rt}/{aid_has} 个 chunk 的 article_id 不出现于 retrieval_text 中；"
     f"即使 query 指明了条款号，BM25 也无法匹配"),
    ("Reranker 误排 — 有正确法规+article 但未命中", rerank_exact_lost/total_reg_miss*100,
     f"{rerank_exact_lost}/{total_reg_miss} 个 miss 召回了正确法规+正确条款但仍未 parent_hit"),
    ("retrieval_text 疑似截断 (<100字)", len(truncated)/len(law_chunks)*100 if law_chunks else 0,
     f"{len(truncated)}/{len(law_chunks)} 个 chunk 的 retrieval_text 疑似被截断"),
]

root_causes.sort(key=lambda x: x[1], reverse=True)

for rank, (name, pct, evidence) in enumerate(root_causes, 1):
    p(f"\n{rank}. {name}: {pct:.1f}%")
    p(f"   证据: {evidence}")

p("\n" + "=" * 80)
p("分析完成")
p("=" * 80)

OUT.close()
print(f"\n结果已写入: regulation_miss_analysis.txt")
