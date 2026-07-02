#!/usr/bin/env python3
"""Compare YAML node definitions with frontend node-configs."""

import yaml
import os
import re
import json

# 1. Parse YAML files
yaml_dir = 'src/langbot/templates/metadata/nodes'
yaml_nodes = {}

for filename in sorted(os.listdir(yaml_dir)):
    if filename.endswith('.yaml'):
        filepath = os.path.join(yaml_dir, filename)
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
            node_name = data.get('name', filename.replace('.yaml', ''))
            yaml_nodes[node_name] = {
                'category': data.get('category', ''),
                'inputs': [i['name'] for i in data.get('inputs', [])],
                'outputs': [o['name'] for o in data.get('outputs', [])],
                'config': [c['name'] for c in data.get('config', [])]
            }

# 2. Parse frontend node-configs TypeScript files
node_configs_dir = 'web/src/app/home/workflows/components/workflow-editor/node-configs'

frontend_nodes = {}

def parse_ts_file(filepath):
    """Parse a TypeScript file to extract node configurations."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find all node type definitions
    # Pattern: nodeType: 'xxx'
    node_type_pattern = r"nodeType:\s*'([^']+)'"
    node_types = re.findall(node_type_pattern, content)
    
    # For each node type, extract inputs, outputs, and config
    for node_type in node_types:
        # Find the config object for this node type
        # Look for the section between this nodeType and the next one or end of object
        pattern = rf"nodeType:\s*'({re.escape(node_type)})'.*?(?=nodeType:|export\s+(const|function)|$)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            section = match.group(0)
            
            # Extract inputs
            inputs = re.findall(r"createInput\('([^']+)'", section)
            
            # Extract outputs  
            outputs = re.findall(r"createOutput\('([^']+)'", section)
            
            # Extract config names
            config_names = re.findall(r"name:\s*'([^']+)'", section)
            # Remove duplicates while preserving order
            seen = set()
            unique_config = []
            for c in config_names:
                if c not in seen:
                    seen.add(c)
                    unique_config.append(c)
            
            frontend_nodes[node_type] = {
                'inputs': inputs,
                'outputs': outputs,
                'config': unique_config
            }

# Parse all config files
for filename in os.listdir(node_configs_dir):
    if filename.endswith('.ts') and filename != 'types.ts' and filename != 'index.ts':
        filepath = os.path.join(node_configs_dir, filename)
        parse_ts_file(filepath)

# 3. Compare and report differences
print("=" * 80)
print("WORKFLOW NODE COMPARISON REPORT: YAML vs Frontend")
print("=" * 80)

all_node_types = sorted(set(list(yaml_nodes.keys()) + list(frontend_nodes.keys())))

discrepancies = []

for node_type in all_node_types:
    yaml_def = yaml_nodes.get(node_type)
    frontend_def = frontend_nodes.get(node_type)
    
    node_discrepancies = []
    
    if not yaml_def:
        print(f"\n⚠️  {node_type}: ONLY in frontend (not in YAML)")
        continue
    if not frontend_def:
        print(f"\n⚠️  {node_type}: ONLY in YAML (not in frontend)")
        continue
    
    # Compare inputs
    yaml_inputs = set(yaml_def['inputs'])
    frontend_inputs = set(frontend_def['inputs'])
    if yaml_inputs != frontend_inputs:
        only_yaml = yaml_inputs - frontend_inputs
        only_frontend = frontend_inputs - yaml_inputs
        node_discrepancies.append({
            'type': 'inputs',
            'only_yaml': list(only_yaml),
            'only_frontend': list(only_frontend)
        })
    
    # Compare outputs
    yaml_outputs = set(yaml_def['outputs'])
    frontend_outputs = set(frontend_def['outputs'])
    if yaml_outputs != frontend_outputs:
        only_yaml = yaml_outputs - frontend_outputs
        only_frontend = frontend_outputs - yaml_outputs
        node_discrepancies.append({
            'type': 'outputs',
            'only_yaml': list(only_yaml),
            'only_frontend': list(only_frontend)
        })
    
    # Compare config
    yaml_config = set(yaml_def['config'])
    frontend_config = set(frontend_def['config'])
    if yaml_config != frontend_config:
        only_yaml = yaml_config - frontend_config
        only_frontend = frontend_config - yaml_config
        node_discrepancies.append({
            'type': 'config',
            'only_yaml': list(only_yaml),
            'only_frontend': list(only_frontend)
        })
    
    if node_discrepancies:
        print(f"\n❌ {node_type} ({yaml_def['category']}): HAS DISCREPANCIES")
        for d in node_discrepancies:
            print(f"   {d['type']}:")
            if d['only_yaml']:
                print(f"     Only in YAML: {d['only_yaml']}")
            if d['only_frontend']:
                print(f"     Only in Frontend: {d['only_frontend']}")
        discrepancies.append((node_type, node_discrepancies))
    else:
        print(f"\n✅ {node_type} ({yaml_def['category']}): OK")

print(f"\n{'=' * 80}")
print(f"SUMMARY: {len(discrepancies)} nodes with discrepancies out of {len(all_node_types)} total")
print(f"{'=' * 80}")

# Output as JSON for further processing
output = {
    'yaml_nodes': {k: v for k, v in yaml_nodes.items()},
    'frontend_nodes': {k: v for k, v in frontend_nodes.items()},
    'discrepancies': {k: v for k, v in discrepancies}
}

with open('node_comparison.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nDetailed comparison saved to node_comparison.json")
