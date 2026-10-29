import os
from pathlib import Path
import time
from ruamel.yaml import YAML
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

yaml = YAML()
yaml.preserve_quotes = True

langs = {
    "zh_Hant": "zh-TW",
    "ja_JP": "ja",
    "vi_VN": "vi",
    "th_TH": "th",
    "es_ES": "es"
}

def translate_text(text, target_lang):
    if not text.strip(): return text
    
    gt = GoogleTranslator(source='auto', target=target_lang)
    
    lines = text.split('\n')
    translated_lines = []
    
    in_code_block = False
    buffer = []
    
    def flush_buffer():
        if not buffer: return
        t = '\n'.join(buffer)
        for _ in range(3):
            try:
                res = gt.translate(t)
                if res:
                    res = res.replace('] (', '](').replace('** ', '**').replace(' **', '**').replace('` ', '`').replace(' `', '`')
                    translated_lines.append(res)
                    break
            except Exception as e:
                time.sleep(1)
        else:
            translated_lines.append(t)
        buffer.clear()
        
    for line in lines:
        if line.strip().startswith('```'):
            flush_buffer()
            in_code_block = not in_code_block
            translated_lines.append(line)
            continue
            
        if in_code_block:
            translated_lines.append(line)
            continue
            
        if line.strip().startswith('http') or (not any(c.isalpha() for c in line) and len(line) < 10):
            flush_buffer()
            translated_lines.append(line)
            continue
            
        buffer.append(line)
        if len(buffer) >= 10:
            flush_buffer()
            
    flush_buffer()
    return '\n'.join(translated_lines)

def bump_version(ver):
    parts = ver.split('.')
    parts[-1] = str(int(parts[-1]) + 1)
    return '.'.join(parts)

plugins = [
    "AgenticRAG", "AIImagePlugin", "AutoTranslate", "DifyDatasetsConnector", 
    "EssentialCommands", "FastGPTConnector", "GeneralParsers", "GoogleSearch", 
    "GroupChatSummary", "HelloPlugin", "KeywordAlert", "LangRAG", "LongTermMemory", 
    "QWeather", "RAGFlowConnector", "ScheNotify", "SysStatPlugin", "TavilySearch", 
    "URLSummary", "WebSearch"
]

repo_root = Path(__file__).resolve().parent
plugins = [str(path.parent) for category in ("Runner", "KnowledgeEngine", "misc")
           for path in sorted((repo_root / category).glob("*/manifest.yaml"))
           if path.parent.name in plugins]

def translate_file(plugin, l_key, l_code, readme_text):
    out_file = os.path.join(plugin, "readme", f"README_{l_key}.md")
    if os.path.exists(out_file):
        return
    print(f"Translating {plugin} README to {l_key}...", flush=True)
    translated = translate_text(readme_text, l_code)
    with open(out_file, 'w', encoding='utf-8') as fout:
        fout.write(translated)
    print(f"Done {plugin} README to {l_key}!", flush=True)

with ThreadPoolExecutor(max_workers=10) as executor:
    for plugin in plugins:
        manifest_path = os.path.join(plugin, "manifest.yaml")
        if not os.path.exists(manifest_path):
            continue
            
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = yaml.load(f)
            
        en_desc = data['metadata'].get('description', {}).get('en_US', '')
        en_label = data['metadata'].get('label', {}).get('en_US', '')
        
        old_v = str(data['metadata'].get('version', '0.1.0'))
        data['metadata']['version'] = bump_version(old_v)
        
        for l_key, l_code in langs.items():
            if l_key not in data['metadata'].get('description', {}):
                if 'description' not in data['metadata']:
                    data['metadata']['description'] = {}
                if en_desc:
                    data['metadata']['description'][l_key] = translate_text(en_desc, l_code)
                    
            if l_key not in data['metadata'].get('label', {}):
                if 'label' not in data['metadata']:
                    data['metadata']['label'] = {}
                if en_label:
                    data['metadata']['label'][l_key] = en_label
                    
        with open(manifest_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
            
        readme_base = os.path.join(plugin, "README.md")
        readme_dir = os.path.join(plugin, "readme")
        os.makedirs(readme_dir, exist_ok=True)
        
        if os.path.exists(readme_base):
            with open(readme_base, 'r', encoding='utf-8') as f:
                readme_text = f.read()
                
            for l_key, l_code in langs.items():
                executor.submit(translate_file, plugin, l_key, l_code, readme_text)

print("All done!", flush=True)
