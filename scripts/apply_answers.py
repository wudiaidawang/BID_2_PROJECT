"""Apply expected_answer from rag_answers.json to eval questions, plus fix the two broken SQL questions."""
import json

# Load answers mapping
with open('data/rag_answers.json', 'r', encoding='utf-8') as f:
    answers = json.load(f)

# Load eval set
with open('data/eval_questions/hybrid_test_cases.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Fix the two problematic SQL questions
for item in data:
    q = item['question']
    if '我们省' in q:
        item['question'] = '去年广东省所有中标项目的总金额累计到多少了？'
        item['expected_answer_contains'] = ['广东', '2025', '总金额', 'SUM']
        print(f'Fixed: 我们省 -> 广东省')
    if '某某' in q:
        item['question'] = '看下中铁建设集团有限公司在2025年一共拿了多少个标，总金额是多少？'
        item['expected_answer_contains'] = ['中铁建设集团', 'COUNT', 'SUM', '2025']
        print(f'Fixed: 某某建设集团 -> 中铁建设集团有限公司')

# Add expected_answer to RAG questions
added = 0
for item in data:
    if item.get('expected_type') == 'rag':
        q = item['question']
        if q in answers:
            item['expected_answer'] = answers[q]
            added += 1
        else:
            print(f'MISSING: {q[:80]}...')

# Save
with open('data/eval_questions/hybrid_test_cases.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Verify
with open('data/eval_questions/hybrid_test_cases.json', 'r', encoding='utf-8') as f:
    verify = json.load(f)

rag_total = sum(1 for c in verify if c['expected_type'] == 'rag')
rag_with = sum(1 for c in verify if c['expected_type'] == 'rag' and c.get('expected_answer'))
print(f'\nDone! RAG questions: {rag_total}, with expected_answer: {rag_with}')
print(f'Total: {len(verify)}')
