import requests
import random
import json
import logging
from datetime import datetime
import string
import io
from urllib.parse import urlparse

log_id = "full_crapi"
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"fuzz_log_{log_id}_{timestamp}.jsonl"

logging.basicConfig(
    filename=log_filename,
    filemode="a",
    level=logging.INFO,
    format='%(message)s'
)

#API_URL = "http://localhost:8888" # crAPI
API_URL = "http://localhost:8080/api/v3" # petstore
# API_URL = "http://localhost:8010/v2" # languagetool

def extract_path(url):
    try:
        return urlparse(url).path
    except Exception:
        return None
    
def generate_fuzzed_file_payload(payload: str) -> dict:
    file_content = payload.encode("utf-8")
    file_obj = io.BytesIO(file_content)
    file_obj.name = "fuzzed_file.txt"
    return {
        "file": (file_obj.name, file_obj, "text/plain")
    }

class APIFuzzEnv:
    def __init__(self, templates_path="./input_templates_petstore_new.json", use_auth=True, log_file_path = None, use_endpoint_scores=False):
        with open(templates_path, "r", encoding="utf-8") as f:
            self.templates = json.load(f)
        self.use_endpoint_scores = use_endpoint_scores
        self.current_template = None
        self.current_run = 0
        self.current_episode = 0
        self.current_step = 0
        self.log_file_path = log_file_path
        self.logger = logging.getLogger(f"FuzzLog_{log_file_path}")
        if log_file_path:
            handler = logging.FileHandler(log_file_path)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.endpoint_scores = {}
        self.mutation_actions = [
            self.mutate_string,
            self.remove_field,
            self.duplicate_field,
            self.set_large_value,
            self.inject_sql_payload,
            self.type_flip,
            self.set_empty_values,
            self.mutate_headers,
            self.mutate_query_params,
            self.mutate_url_path,
            self.flip_boolean_flags,
            self.fuzz_ids,
            self.mutate_template_injection,
            self.mutate_method,
            self.mutate_content_type_vs_body,
            self.mutate_query_values,
            self.mutate_path_ids
        ]
        self.mutator_types = {
            "mutate_string": "semantic",
            "inject_sql_payload": "semantic",
            "mutate_template_injection": "semantic",
            "mutate_query_values": "semantic",
            "remove_field": "structural",
            "duplicate_field": "structural",
            "type_flip": "structural",
            "flip_boolean_flags": "structural",
            "set_empty_values": "structural",
            "set_large_value": "boundary",
            "fuzz_ids": "boundary",
            "mutate_path_ids": "boundary",
            "mutate_method": "protocol",
            "mutate_content_type_vs_body": "protocol",
            "mutate_headers": "header",
            "mutate_query_params": "path/query",
            "mutate_url_path": "path/query"
        }

        self.load_all_payloads()
        
        if use_auth:
            self.token = "tested API token" # fill if you need an Authorization

        for template in self.templates:
            url = template["url"]
            endpoint = template.get("endpoint", url)
            if url.startswith("/"):
                template["url"] = f"{API_URL}{url}"
            elif url.startswith("api.example.com"):
                template["url"] = f"https://{url}"
            elif url.startswith("https://api.example.com"):
                template["url"] = url.replace("https://api.example.com", API_URL)

            if self.token:
                headers = template.setdefault("headers", {})
                headers["Authorization"] = f"Bearer {self.token}"


            self.endpoint_scores[endpoint] = 1
            
    def load_all_payloads(self):
        self.sql_payloads = self._load_payloads("../PayloadsAllTheThings/SQL Injection/Intruder/Generic_Fuzz.txt")
        self.xss_payloads = self._load_payloads("../PayloadsAllTheThings/XSS Injection/Intruders/XSS_Polyglots.txt")
        self.ssti_payloads = self._load_payloads("..PayloadsAllTheThings/Server Side Template Injection/Intruder/ssti.fuzz")

    def _load_payloads(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Failed to load payloads from {path}: {e}")
            return []
        
    def reset(self):
        if self.use_endpoint_scores and self.endpoint_scores:
            weights = [self.endpoint_scores.get(t.get("endpoint", t["url"]), 1) for t in self.templates]
            self.current_template = random.choices(self.templates, weights=weights, k=1)[0]
        else:
            self.current_template = random.choice(self.templates)
        return self.current_template

    def step(self, action_index):
        
        if random.random() < 0.3:
            mutated = self.apply_multiple_mutations(self.current_template, count=random.randint(2, 3))
        else:
            mutated = self.apply_mutation(self.current_template, action_index)
        original_response = self.send_request(self.current_template)
        mutated_response = self.send_request(mutated)
        if self.use_endpoint_scores and mutated_response.status_code >= 500:    # for heurtisitc endpoint scores
            endpoint = self.current_template.get("endpoint", self.current_template["url"])
            if self.endpoint_scores and endpoint in self.endpoint_scores:
                self.endpoint_scores[endpoint] += 1
        #reward = self.calculate_reward(original_response, mutated_response)
        reward = self.calculate_reward_rl(mutated_response)

        status = mutated_response.status_code if mutated_response.status_code is not None else 0
        done = status >= 500 or status == 404
        mutated_request_enriched = mutated.copy()
        mutated_request_enriched["method"] = mutated.get("method", self.current_template.get("method", "GET"))
        mutated_request_enriched["path"] = extract_path(mutated.get("url", ""))
        mutated_request_enriched["endpoint"] = mutated.get("endpoint", extract_path(mutated.get("url", "")))
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "original_request": self.current_template,
            "mutated_request": mutated_request_enriched,
            "action_index": action_index,
            "action_name": self.mutation_actions[action_index].__name__,
            "mutation_type": self.mutator_types.get(self.mutation_actions[action_index].__name__, "unknown"),
            "status_code": mutated_response.status_code,
            "reward": reward,
            "mutation_applied": self.is_mutated(self.current_template, mutated),
            "response_diff": original_response.text != mutated_response.text,
            "response_text": mutated_response.text,
            "response_headers": dict(mutated_response.headers),
            "run": self.current_run,
            "episode": self.current_episode,
            "step": self.current_step
        }
        self.logger.info(json.dumps(log_data))
        print(f"Action {action_index} ({log_data['action_name']}), Reward: {reward}, Code: {mutated_response.status_code}")

        return mutated, reward, done, {"status_code": mutated_response.status_code}

    def apply_mutation(self, template, action_index):
        mutated = json.loads(json.dumps(template))
        mutation = self.mutation_actions[action_index]
        method = template.get("method", "GET").upper()
        body = template.get("body", None)
        body_mutators = {
            "mutate_string",
            "remove_field",
            "duplicate_field",
            "set_large_value",
            "inject_sql_payload",
            "type_flip",
            "set_empty_values",
            "flip_boolean_flags",
            "fuzz_ids",
            "mutate_template_injection",
            "mutate_content_type_vs_body"
        }
        if mutation.__name__ in body_mutators and (body is None or method == "GET"):
            return mutated
        mutation(mutated)
        return mutated

    def is_mutated(self, original, mutated):
        return (
            original.get("url") != mutated.get("url") or
            original.get("body") != mutated.get("body") or
            original.get("headers") != mutated.get("headers") or
            original.get("method") != mutated.get("method")
        )

    def calculate_reward_rl(self, mutated_response):
        status = mutated_response.status_code or 0
        if 500 <= status < 600:
            return 1
        elif 200 <= status < 300:
            return -1
        return 0
    
    def send_request(self, request_data):
        try:
            method = request_data.get("method", "GET").upper()
            url = request_data.get("url")
            headers = request_data.get("headers", {}) or {}
            body = request_data.get("body", None)
            if headers.get("Content-Type", "").strip() in ["application/", ""]:
                headers["Content-Type"] = "application/json"
            if self.token:
                if "Authorization" not in headers or "YOUR_ACCESS_TOKEN" in headers.get("Authorization", ""):
                    headers["Authorization"] = f"Bearer {self.token}"
            if method == "GET":
                return requests.get(url, headers=headers)
            elif method == "POST":
                if headers.get("Content-Type") == "multipart/form-data":
                    files = generate_fuzzed_file_payload(str(body.get("file", "FUZZ")))
                    clean_headers = {k: v for k, v in headers.items() if k != "Content-Type"}
                    return requests.post(url, headers=clean_headers, files=files)
                else:
                    return requests.post(url, headers=headers, json=body)
            elif method == "PUT":
                return requests.put(url, headers=headers, json=body)
            elif method == "DELETE":
                return requests.delete(url, headers=headers)
            else:
                response = requests.Response()
                response.status_code = 405
                response._content = b"Unsupported HTTP method"
                return response
        except Exception as e:
            print(f"Request failed: {e}")
            response = requests.Response()
            response.status_code = 0
            response._content = str(e).encode()
            return response
### MUTATIONS
    def mutate_string(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, str) and val:
                    d[key] = random.choice(self.xss_payloads)
                    break
        self._mutate_body(req, mutate)

    def inject_sql_payload(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, str):
                    d[key] = random.choice(self.sql_payloads)
                    break
        self._mutate_body(req, mutate)

    def mutate_template_injection(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, str):
                    d[key] = random.choice(self.ssti_payloads)
                    break
        self._mutate_body(req, mutate)

    def remove_field(self, req):
        def mutate(d):
            if d:
                del d[random.choice(list(d.keys()))]
        self._mutate_body(req, mutate)

    def duplicate_field(self, req):
        def mutate(d):
            key = random.choice(list(d.keys()))
            d[key + "_copy"] = d[key]
        self._mutate_body(req, mutate)

    def set_large_value(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, (int, float)):
                    d[key] = 10 ** random.randint(6, 12)
                    break
        self._mutate_body(req, mutate)

    def type_flip(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, bool):
                    d[key] = not val
                    break
                elif isinstance(val, int):
                    d[key] = str(val)
                    break
                elif isinstance(val, str):
                    try:
                        d[key] = int(val)
                        break
                    except:
                        continue
        self._mutate_body(req, mutate)

    def set_empty_values(self, req):
        empty_vals = ["", {}, [], None]
        def mutate(d):
            for key in d:
                d[key] = random.choice(empty_vals)
                break
        self._mutate_body(req, mutate)

    def mutate_headers(self, req):
        headers = req.get("headers", {})
        if headers:
            key = random.choice(list(headers.keys()))
            headers[key + "_fuzz"] = headers[key]

    def mutate_query_params(self, req):
        url = req.get("url", "")
        parsed = urlparse(url)
        query = parsed.query
        fuzz_param = f"fuzzed_param_{random.randint(1, 1000)}=FUZZED"
        new_query = f"{query}&{fuzz_param}" if query else fuzz_param
        new_url = parsed._replace(query=new_query).geturl()
        req["url"] = new_url

    def mutate_url_path(self, req):
        url = req.get("url", "")
        parts = url.split("/")
        if len(parts) > 3:
            idx = random.randint(3, len(parts) - 1)
            parts[idx] = parts[idx] + "_fuzz"
            req["url"] = "/".join(parts)

    def flip_boolean_flags(self, req):
        def mutate(d):
            for key, val in d.items():
                if isinstance(val, bool):
                    d[key] = not val
                    break
        self._mutate_body(req, mutate)

    def fuzz_ids(self, req):
        common_ids = ["id", "userId", "vehicleId", "video_id", "order_id", "postId"]
        fuzz_values = [-1, 0, 999999999, "abc", "0'*", "../../../etc/passwd", "", " "]
        def mutate(d):
            for key in d:
                if key in common_ids:
                    d[key] = random.choice(fuzz_values)
                    break
        self._mutate_body(req, mutate)

    def _mutate_body(self, req, mutate_fn):
        body = req.get("body")
        if isinstance(body, dict): mutate_fn(body)
        elif isinstance(body, list):
            for item in body:
                if isinstance(item, dict):
                    mutate_fn(item)

    def mutate_method(self, req):
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        current_method = req.get("method", "GET")
        req["method"] = random.choice([m for m in methods if m != current_method])


    def mutate_content_type_vs_body(self, req):
        if isinstance(req.get("body"), dict):
            req["headers"]["Content-Type"] = "text/plain"
            req["body"] = json.dumps(req["body"]) 

    def apply_multiple_mutations(self, template, count=2):
        mutated = json.loads(json.dumps(template))
        actions = random.sample(self.mutation_actions, count)
        for action in actions:
            try:
                action(mutated)
            except Exception as e:
                print(f"⚠️ Mutation {action.__name__} failed: {e}")
        return mutated 
    
    def mutate_query_values(self, req):
        url = req.get("url", "")
        if "?" not in url:
            return
        base, query_string = url.split("?", 1)
        query_pairs = query_string.split("&")
        new_pairs = []
        for pair in query_pairs:
            if "=" not in pair:
                new_pairs.append(pair)
                continue
            key, val = pair.split("=", 1)
            if isinstance(val, str) and val:
                fuzzed_val = random.choice(self.xss_payloads)
                new_pairs.append(f"{key}={fuzzed_val}")
            else:
                new_pairs.append(pair)
        req["url"] = f"{base}?{'&'.join(new_pairs)}"
        
    def mutate_path_ids(self, req):
        url = req.get("url", "")
        parts = url.split("/")
        for i, part in enumerate(parts):
            if part.isdigit():
                parts[i] = random.choice([
                    "999999999999999999999",
                    "-1",
                    "0",
                    "abc",
                    "' OR 1=1 --",
                    "../../../etc/passwd",
                    "",
                    " " * 10,
                    str(random.randint(10**10, 10**12))
                ])
                break
        req["url"] = "/".join(parts)