"""
Terraform HCL Parser Utility
============================
A lightweight HCL parser for testing Terraform modules without requiring
terraform/tofu to be installed.
"""

import os
import re
from pathlib import Path
from typing import Any


class TerraformParser:
    """Parse Terraform HCL files into Python dictionaries."""

    def __init__(self, modules_base: str):
        self.modules_base = Path(modules_base)

    def find_module_dirs(self) -> list[Path]:
        """Find all module directories containing .tf files."""
        modules = []
        for root, dirs, files in os.walk(self.modules_base):
            if any(f.endswith(".tf") for f in files):
                modules.append(Path(root))
        return sorted(set(modules))

    def parse_module(self, module_path: str | Path) -> dict[str, Any]:
        """Parse all .tf files in a module directory."""
        module_path = Path(module_path)
        result = {
            "path": str(module_path),
            "name": module_path.name,
            "variables": {},
            "outputs": {},
            "resources": {},
            "data_sources": {},
            "locals": {},
            "module_calls": {},
            "providers": {},
            "terraform_config": {},
        }

        for tf_file in sorted(module_path.glob("*.tf")):
            content = tf_file.read_text()
            self._parse_content(content, result)

        return result

    def _parse_content(self, content: str, result: dict) -> None:
        """Parse HCL content and populate result dict."""
        # Remove comments (but not inside strings)
        content = self._remove_comments(content)

        # Parse terraform block
        self._parse_terraform_block(content, result)

        # Parse variable blocks
        self._parse_variables(content, result)

        # Parse output blocks
        self._parse_outputs(content, result)

        # Parse resource blocks
        self._parse_resources(content, result)

        # Parse data blocks
        self._parse_data_sources(content, result)

        # Parse locals
        self._parse_locals(content, result)

        # Parse module calls
        self._parse_module_calls(content, result)

        # Parse provider blocks
        self._parse_providers(content, result)

    def _remove_comments(self, content: str) -> str:
        """Remove comments while preserving strings."""
        result = []
        i = 0
        in_string = False
        string_char = None
        
        while i < len(content):
            char = content[i]
            
            if not in_string:
                if char == '"':
                    in_string = True
                    string_char = '"'
                    result.append(char)
                elif char == '#':
                    # Skip to end of line
                    while i < len(content) and content[i] != '\n':
                        i += 1
                    continue
                elif char == '/' and i + 1 < len(content) and content[i + 1] == '/':
                    # Skip to end of line
                    while i < len(content) and content[i] != '\n':
                        i += 1
                    continue
                else:
                    result.append(char)
            else:
                if char == '\\' and i + 1 < len(content):
                    result.append(char)
                    result.append(content[i + 1])
                    i += 2
                    continue
                elif char == string_char:
                    in_string = False
                    string_char = None
                    result.append(char)
                else:
                    result.append(char)
            
            i += 1
        
        return ''.join(result)

    def _find_matching_brace(self, content: str, start: int) -> int:
        """Find the position of the matching closing brace, handling strings."""
        brace_count = 1
        pos = start
        in_string = False
        string_char = None
        
        while pos < len(content) and brace_count > 0:
            char = content[pos]
            
            if in_string:
                if char == '\\':
                    pos += 2
                    continue
                elif char == string_char:
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                    string_char = '"'
                elif char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
            
            pos += 1
        
        return pos - 1

    def _parse_terraform_block(self, content: str, result: dict) -> None:
        """Parse terraform {} block."""
        match = re.search(r'terraform\s*\{', content)
        if match:
            start = match.end()
            end = self._find_matching_brace(content, start)
            block = content[start:end]

            # Extract required_version
            rv = re.search(r'required_version\s*=\s*"([^"]+)"', block)
            if rv:
                result["terraform_config"]["required_version"] = rv.group(1)

            # Extract required_providers - find the block
            rp_match = re.search(r'required_providers\s*\{', block)
            if rp_match:
                rp_start = rp_match.end()
                rp_end = self._find_matching_brace(block, rp_start)
                providers_text = block[rp_start:rp_end]

                # Parse each provider entry
                for pm in re.finditer(r'(\w+)\s*=\s*\{', providers_text):
                    provider_name = pm.group(1)
                    p_start = pm.end()
                    p_end = self._find_matching_brace(providers_text, p_start)
                    provider_body = providers_text[p_start:p_end]

                    source = re.search(r'source\s*=\s*"([^"]+)"', provider_body)
                    version = re.search(r'version\s*=\s*"([^"]+)"', provider_body)
                    result["terraform_config"].setdefault("required_providers", {})[provider_name] = {
                        "source": source.group(1) if source else None,
                        "version": version.group(1) if version else None,
                    }

    def _parse_variables(self, content: str, result: dict) -> None:
        """Parse variable blocks."""
        for match in re.finditer(r'variable\s+"([^"]+)"\s*\{', content):
            var_name = match.group(1)
            start = match.end()
            end = self._find_matching_brace(content, start)
            var_body = content[start:end]

            var_info = {"name": var_name}
            # Parse type
            type_match = re.search(r'type\s*=\s*(\w+)', var_body)
            if type_match:
                var_info["type"] = type_match.group(1)
            # Parse default
            default_match = re.search(r'default\s*=\s*([^}\n]+)', var_body)
            if default_match:
                var_info["default"] = default_match.group(1).strip()
            # Parse description
            desc_match = re.search(r'description\s*=\s*"([^"]*)"', var_body)
            if desc_match:
                var_info["description"] = desc_match.group(1)
            # Parse sensitive
            if re.search(r'sensitive\s*=\s*true', var_body):
                var_info["sensitive"] = True
            # Parse validation
            validation_match = re.search(r'validation\s*\{', var_body)
            if validation_match:
                v_start = validation_match.end()
                v_end = self._find_matching_brace(var_body, v_start)
                val_body = var_body[v_start:v_end]
                condition = re.search(r'condition\s*=\s*(.+)', val_body)
                error_msg = re.search(r'error_message\s*=\s*"([^"]*)"', val_body)
                var_info["validation"] = {
                    "condition": condition.group(1).strip() if condition else None,
                    "error_message": error_msg.group(1) if error_msg else None,
                }

            result["variables"][var_name] = var_info

    def _parse_outputs(self, content: str, result: dict) -> None:
        """Parse output blocks."""
        for match in re.finditer(r'output\s+"([^"]+)"\s*\{', content):
            out_name = match.group(1)
            start = match.end()
            end = self._find_matching_brace(content, start)
            out_body = content[start:end]

            out_info = {"name": out_name}
            value_match = re.search(r'value\s*=\s*(.+)', out_body)
            if value_match:
                out_info["value"] = value_match.group(1).strip()
            desc_match = re.search(r'description\s*=\s*"([^"]*)"', out_body)
            if desc_match:
                out_info["description"] = desc_match.group(1)
            if re.search(r'sensitive\s*=\s*true', out_body):
                out_info["sensitive"] = True

            result["outputs"][out_name] = out_info

    def _parse_resources(self, content: str, result: dict) -> None:
        """Parse resource blocks."""
        for match in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', content):
            resource_type = match.group(1)
            resource_name = match.group(2)
            start = match.end()
            end = self._find_matching_brace(content, start)
            resource_body = content[start:end]

            key = f"{resource_type}.{resource_name}"
            resource_info = {
                "type": resource_type,
                "name": resource_name,
                "body": resource_body,
            }

            # Check for count
            if re.search(r'count\s*=', resource_body):
                resource_info["count"] = True
            # Check for for_each
            if re.search(r'for_each\s*=', resource_body):
                resource_info["for_each"] = True
            # Check for depends_on
            if re.search(r'depends_on\s*=', resource_body):
                resource_info["depends_on"] = True
            # Check for lifecycle
            if re.search(r'lifecycle\s*\{', resource_body):
                resource_info["lifecycle"] = True
            # Check for prevent_destroy
            if re.search(r'prevent_destroy\s*=\s*true', resource_body):
                resource_info["prevent_destroy"] = True
            # Check for dynamic blocks
            if re.search(r'dynamic\s+"', resource_body):
                resource_info["dynamic"] = True
            # Check for tags
            if re.search(r'tags\s*=', resource_body):
                resource_info["tags"] = True
            # Check for sensitive values
            if re.search(r'sensitive\s*=\s*true', resource_body):
                resource_info["sensitive"] = True

            result["resources"][key] = resource_info

    def _parse_data_sources(self, content: str, result: dict) -> None:
        """Parse data blocks."""
        for match in re.finditer(r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{', content):
            data_type = match.group(1)
            data_name = match.group(2)
            start = match.end()
            end = self._find_matching_brace(content, start)
            data_body = content[start:end]

            key = f"{data_type}.{data_name}"
            result["data_sources"][key] = {
                "type": data_type,
                "name": data_name,
                "body": data_body,
            }

    def _parse_locals(self, content: str, result: dict) -> None:
        """Parse locals blocks."""
        for match in re.finditer(r'locals\s*\{', content):
            start = match.end()
            end = self._find_matching_brace(content, start)
            locals_body = content[start:end]

            for lm in re.finditer(r'(\w+)\s*=\s*([^\n]+)', locals_body):
                result["locals"][lm.group(1)] = lm.group(2).strip()

    def _parse_module_calls(self, content: str, result: dict) -> None:
        """Parse module blocks."""
        for match in re.finditer(r'module\s+"([^"]+)"\s*\{', content):
            mod_name = match.group(1)
            start = match.end()
            end = self._find_matching_brace(content, start)
            mod_body = content[start:end]

            mod_info = {"name": mod_name}
            source_match = re.search(r'source\s*=\s*"([^"]+)"', mod_body)
            if source_match:
                mod_info["source"] = source_match.group(1)

            result["module_calls"][mod_name] = mod_info

    def _parse_providers(self, content: str, result: dict) -> None:
        """Parse provider blocks."""
        for match in re.finditer(r'provider\s+"([^"]+)"\s*\{', content):
            prov_name = match.group(1)
            start = match.end()
            end = self._find_matching_brace(content, start)
            prov_body = content[start:end]

            result["providers"][prov_name] = {"body": prov_body}


def get_module_path(modules_base: str, *parts: str) -> str:
    """Get the path to a specific module."""
    return os.path.join(modules_base, *parts)


def read_tf_file(path: str) -> str:
    """Read a .tf file and return its content."""
    with open(path) as f:
        return f.read()
