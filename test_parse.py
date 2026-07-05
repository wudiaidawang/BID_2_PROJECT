import sys, json, re
sys.path.insert(0, '.')
from openai import OpenAI
from config import settings

api_key = settings.llm_api_key
api_url = settings.llm_api_url
base_url = api_url.replace('/chat/completions', '')
client = OpenAI(base_url=base_url, api_key=api_key)

resp = client.chat.completions.create(
    model='glm-4.5-air',
    messages=[
        {'role': 'system', 'content': '输出 JSON 数组。每项: question, expected_chunk_id, answer。直接输出 JSON，无任何其他文字。'},
        {'role': 'user', 'content': '生成 3 个中文问答，测试用。直接输出 JSON 数组。'},
    ],
    temperature=0.4,
    max_tokens=4096,
    timeout=60,
)
content = resp.choices[0].message.content
print('=== RAW OUTPUT (first 500) ===')
print(repr(content[:500]))
print()
print('=== RAW OUTPUT (last 200) ===')
print(repr(content[-200:]))
print()

# Try parse
print('=== TRY DIRECT PARSE ===')
try:
    result = json.loads(content)
    print(f'OK: {len(result)} items')
except json.JSONDecodeError as e:
    print(f'FAIL: {e}')

# Try bracket counting
print('=== TRY BRACKET COUNT ===')
for m in re.finditer(r'\[', content):
    depth = 0
    in_str = False
    escape = False
    start = m.start()
    for i in range(start, len(content)):
        c = content[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                try:
                    result = json.loads(content[start:i+1])
                    print(f'OK at [{start}:{i+1}]: {len(result)} items')
                except json.JSONDecodeError as e2:
                    print(f'FAIL at [{start}:{i+1}]: {e2}')
                    ctx_start = max(0, i-80)
                    ctx_end = min(len(content), i+80)
                    print(f'  Context: {repr(content[ctx_start:ctx_end])}')
                break
