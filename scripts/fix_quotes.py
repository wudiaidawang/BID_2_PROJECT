"""Fix smart/curly quotes that broke JSON structure. Keep Chinese content quotes intact."""
import re

path = 'data/eval_questions/hybrid_test_cases.json'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The JSON field names that got corrupted - restore them
field_fixes = [
    ('"question":', '"question":'),
    ('"expected_type":', '"expected_type":'),
    ('"expected_answer":', '"expected_answer":'),
    ('"expected_answer_contains":', '"expected_answer_contains":'),
    ('"difficulty":', '"difficulty":'),
    ('"category":', '"category":'),
    ('"rag"', '"rag"'),
    ('"sql"', '"sql"'),
    ('"easy"', '"easy"'),
    ('"medium"', '"medium"'),
    ('"hard"', '"hard"'),
]

for old, new in field_fixes:
    old_curly = old.replace('"', '“').replace('"', '”')  # left "
    # Try various curly quote combinations
    for left in ['“', '”']:  # " "
        for right in ['“', '”']:  # " "
            variant = old.replace('"', left).replace('"', right)
            if variant in content:
                content = content.replace(variant, new)
                print(f'Fixed: {repr(variant)} -> {repr(new)}')
            else:
                pass  # not found

# Generic: replace any remaining "{key}": pattern where key has curly quotes
# This handles cases like {"question": ...}
for key in ['question', 'expected_type', 'expected_answer', 'expected_answer_contains',
            'difficulty', 'category']:
    for lq, rq in [('“', '”'), ('”', '“'), ('“', '“'), ('”', '”')]:
        pattern = lq + key + rq + lq + ':' + rq
        replacement = '"' + key + '":'
        count = content.count(pattern)
        if count > 0:
            content = content.replace(pattern, replacement)
            print(f'Generic fix: {pattern} -> {replacement} ({count}x)')

# Fix value curly quotes for "rag", "sql", "easy", "medium", "hard"
for val in ['rag', 'sql', 'easy', 'medium', 'hard']:
    for lq, rq in [('“', '”'), ('”', '“')]:
        pattern = lq + val + rq
        replacement = '"' + val + '"'
        count = content.count(pattern)
        if count > 0:
            content = content.replace(pattern, replacement)
            print(f'Fix value: {pattern} -> {replacement} ({count}x)')

# Fix array brackets that got curly-quoted
content = content.replace('“[', '"[')
content = content.replace(']”', ']"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('\nValidating JSON...')
import json
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rag_total = sum(1 for c in data if c.get('expected_type') == 'rag')
    rag_with_answer = sum(1 for c in data if c.get('expected_type') == 'rag' and c.get('expected_answer'))
    print(f'VALID! Total: {len(data)}, RAG: {rag_total}, RAG with expected_answer: {rag_with_answer}')
except json.JSONDecodeError as e:
    print(f'Still broken: {e}')
