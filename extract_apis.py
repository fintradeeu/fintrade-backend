import json
import re

def generate_markdown():
    with open('openapi.json', 'r', encoding='utf-8') as f:
        spec = json.load(f)

    paths = spec.get("paths", {})
    components = spec.get("components", {}).get("schemas", {})

    def resolve_ref(ref_str):
        if not ref_str: return None
        schema_name = ref_str.split("/")[-1]
        return components.get(schema_name)

    def get_schema_fields(schema):
        if not schema: return "None"
        if "properties" in schema:
            fields = []
            for k, v in schema["properties"].items():
                v_type = v.get("type", "any")
                if "$ref" in v:
                    v_type = v["$ref"].split("/")[-1]
                if v_type == "array" and "items" in v:
                    if "$ref" in v["items"]:
                        v_type = f"Array<{v['items']['$ref'].split('/')[-1]}>"
                    else:
                        v_type = f"Array<{v['items'].get('type', 'any')}>"
                fields.append(f"- **{k}** ({v_type})")
            return "\n".join(fields)
        return str(schema)

    def format_payload(content):
        if not content: return "None"
        json_content = content.get("application/json")
        if not json_content:
             multipart = content.get("multipart/form-data")
             if multipart: return "FormData (Multipart)"
             return "None"
             
        schema = json_content.get("schema", {})
        if "$ref" in schema:
            resolved = resolve_ref(schema["$ref"])
            return get_schema_fields(resolved)
        return get_schema_fields(schema)

    sections = {
        "Exams": [],
        "Assignments": [],
        "Lectures": [],
        "Landing Page & CMS": [],
    }

    for path, methods in paths.items():
        for method, details in methods.items():
            tags = details.get("tags", [])
            summary = details.get("summary", "")
            
            # Categorize
            category = None
            if "exam" in path.lower() or "exam" in summary.lower():
                category = "Exams"
            elif "assignment" in path.lower() or "assignment" in summary.lower():
                category = "Assignments"
            elif "lecture" in path.lower() or "lecture" in summary.lower():
                category = "Lectures"
            elif "blog" in path.lower() or "cms" in path.lower() or "landing" in path.lower() or ("courses" in path.lower() and method == "get"):
                category = "Landing Page & CMS"
                
            if category:
                request_body = format_payload(details.get("requestBody", {}).get("content"))
                
                response_200 = details.get("responses", {}).get("200", {}).get("content", {})
                response_201 = details.get("responses", {}).get("201", {}).get("content", {})
                res_content = response_200 or response_201
                response_body = format_payload(res_content)

                md = f"### `{method.upper()}` {path}\n"
                md += f"**Description:** {summary}\n\n"
                md += f"**Request Payload:**\n{request_body}\n\n"
                md += f"**Response Payload:**\n{response_body}\n\n"
                md += "---\n"
                sections[category].append(md)

    with open('../../../../../Users/eyush/.gemini/antigravity/brain/730c38f2-a449-4eea-a02d-455bfaf61ce2/api_documentation.md', 'w', encoding='utf-8') as out:
        out.write("# API Documentation\n\n")
        
        for section, endpoints in sections.items():
            out.write(f"## {section}\n\n")
            if not endpoints:
                out.write("No APIs found in this category.\n\n")
            else:
                for ep in endpoints:
                    out.write(ep)

generate_markdown()
