import json
from typing import List
from openai import OpenAI

CLIENT = OpenAI(api_key="gpt api token here")
OPENAPI_FILE = "language_tool.json"
OUTPUT_FILE = "input_templates_language_tool.json"
MODEL = "gpt-4o"

def call_gpt(prompt: str) -> str:
    response = CLIENT.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are an expert in generating test input templates for REST APIs."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def validate_template(template: dict) -> List[str]:
    errors = []

    if template.get("method") not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
        errors.append("Invalid or missing HTTP method")

    endpoint = template.get("endpoint", "")
    url = template.get("url", "")
    if not endpoint or not endpoint.startswith("/"):
        errors.append("Missing or malformed endpoint")
    if not url or not url.startswith("/"):
        errors.append("Missing or malformed url")
    if "{" in endpoint and not any(p in url for p in ["123", "abc", "1"]):
        errors.append("Endpoint has path param but URL lacks concrete value")

    method = template.get("method")
    body = template.get("body")
    if method in {"GET", "DELETE"} and body not in [None, {}]:
        errors.append(f"{method} should not have a body")
    if method in {"POST", "PUT", "PATCH"} and body is None:
        errors.append(f"{method} typically requires a body")

    return errors

def generate_templates():
    with open(OPENAPI_FILE, "r", encoding="utf-8") as f:
        spec = json.load(f)

    paths = spec.get("paths", {})
    print(f"\n📄 Loaded {len(paths)} paths from OpenAPI spec.")
    generated_templates = []
    method_counter = {}

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue

            method_upper = method.upper()
            method_counter[method_upper] = method_counter.get(method_upper, 0) + 1

            print(f"\n🔍 Processing {method_upper} {path}...")

            short_operation = {
                "method": method_upper,
                "path": path,
                "parameters": operation.get("parameters", []),
                "requestBody": operation.get("requestBody", {}),
                "summary": operation.get("summary", "")
            }

            gen_prompt = f'''
You are an API test case generator. Your job is to produce a correct input_template for fuzz testing the following endpoint.

Include:
- method: HTTP verb (GET, POST, etc.)
- endpoint: Template path (e.g. /user/{{username}})
- url: Concrete path with values (e.g. /user/johndoe)
- headers: include "Content-Type": "application/json" for POST, PUT, PATCH. For GET/DELETE, omit Content-Type.
- body: realistic example or null if not needed

Only output valid JSON.

OpenAPI operation:
{json.dumps(short_operation, indent=2)}
'''
            try:
                gpt_output = call_gpt(gen_prompt)
                cleaned = gpt_output.strip().strip("```").replace("json", "").strip()
                parsed = json.loads(cleaned)
                errors = validate_template(parsed)

                if errors:
                    print(f"⚠️ Validation failed: {errors}")
                    fix_prompt = f'''
The following JSON template has issues. Fix them to ensure:
- valid HTTP method
- valid endpoint and url
- Content-Type must be "application/json" for methods with body, or omitted otherwise
- body rules depending on HTTP method

Return valid JSON only.

Broken template:
{json.dumps(parsed, indent=2)}
'''
                    corrected_response = call_gpt(fix_prompt)
                    try:
                        corrected = json.loads(corrected_response)
                        corrected_errors = validate_template(corrected)
                        if corrected_errors:
                            print(f"❌ Still invalid: {corrected_errors}")
                        else:
                            generated_templates.append(corrected)
                            print("✅ GPT corrected template.")
                    except json.JSONDecodeError:
                        print("❌ GPT correction not valid JSON.")
                else:
                    generated_templates.append(parsed)
                    print("✅ Template is valid.")
            except Exception as e:
                print(f"❌ GPT generation failed: {e}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(generated_templates, f, indent=2)
        print(f"\n📦 Saved {len(generated_templates)} valid templates to {OUTPUT_FILE}")

    print("\n📊 Distribution of methods in spec:")
    for m, count in method_counter.items():
        print(f"  {m}: {count}")

if __name__ == "__main__":
    generate_templates()