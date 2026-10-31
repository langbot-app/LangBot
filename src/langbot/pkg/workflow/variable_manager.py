"""Variable management for workflow execution.

This module provides utilities for managing workflow variables, including:
- Reserved variable protection
- Variable namespace validation
- Variable inheritance between nodes
"""

from typing import Set, Dict, Any

# 保留变量列表 - 这些变量由系统管理，不能被用户覆盖
RESERVED_VARIABLES = {
    'workflow_id',
    'execution_id',
    'node_id',
    'timestamp',
    'launcher_type',
    'trigger_type',
    'message_id',
    'execution_status',
}


def get_reserved_variables() -> Set[str]:
    """获取保留变量列表
    
    Returns:
        保留变量名称的集合
    """
    return RESERVED_VARIABLES.copy()


def validate_variable_namespace(
    variables: Dict[str, Any],
    namespace: str = 'workflow'
) -> bool:
    """验证变量命名空间
    
    检查变量是否使用了保留的名称。允许不带前缀的变量，但建议使用命名空间前缀。
    
    Args:
        variables: 要验证的变量字典
        namespace: 命名空间前缀（可选）
        
    Returns:
        True 如果验证通过
        
    Raises:
        ValueError: 如果变量名称与保留变量冲突
    """
    reserved = get_reserved_variables()
    
    for var_name in variables.keys():
        if var_name in reserved:
            raise ValueError(
                f"Variable '{var_name}' is reserved and cannot be used. "
                f"Reserved variables: {', '.join(sorted(reserved))}"
            )
        
        # 检查命名空间前缀（可选建议）
        if namespace and not var_name.startswith(f"{namespace}_"):
            # 允许不带前缀的变量，但建议使用前缀
            pass
    
    return True


def inherit_variables(
    parent_variables: Dict[str, Any],
    child_namespace: str
) -> Dict[str, Any]:
    """继承父节点变量到子节点
    
    将父节点的变量继承到子节点，跳过保留变量，并添加命名空间前缀。
    
    Args:
        parent_variables: 父节点的变量字典
        child_namespace: 子节点的命名空间前缀
        
    Returns:
        带有命名空间前缀的继承变量字典
    """
    inherited = {}
    
    for key, value in parent_variables.items():
        # 跳过保留变量
        if key in RESERVED_VARIABLES:
            continue
        
        # 添加命名空间前缀
        namespaced_key = f"{child_namespace}_{key}"
        inherited[namespaced_key] = value
    
    return inherited


def merge_variables(
    base_variables: Dict[str, Any],
    override_variables: Dict[str, Any],
    allow_reserved: bool = False
) -> Dict[str, Any]:
    """合并变量字典
    
    将override_variables合并到base_variables中。
    
    Args:
        base_variables: 基础变量字典
        override_variables: 要合并的变量字典
        allow_reserved: 是否允许覆盖保留变量（默认False）
        
    Returns:
        合并后的变量字典
        
    Raises:
        ValueError: 如果尝试覆盖保留变量且allow_reserved=False
    """
    result = base_variables.copy()
    
    for key, value in override_variables.items():
        if key in RESERVED_VARIABLES and not allow_reserved:
            raise ValueError(
                f"Cannot override reserved variable '{key}'. "
                f"Set allow_reserved=True to override."
            )
        result[key] = value
    
    return result


def extract_namespace_variables(
    variables: Dict[str, Any],
    namespace: str
) -> Dict[str, Any]:
    """提取特定命名空间的变量
    
    从变量字典中提取具有特定命名空间前缀的变量。
    
    Args:
        variables: 变量字典
        namespace: 命名空间前缀
        
    Returns:
        提取的变量字典（不包含命名空间前缀）
    """
    prefix = f"{namespace}_"
    result = {}
    
    for key, value in variables.items():
        if key.startswith(prefix):
            # 移除命名空间前缀
            clean_key = key[len(prefix):]
            result[clean_key] = value
    
    return result


def sanitize_variables(
    variables: Dict[str, Any],
    allowed_keys: Set[str] | None = None
) -> Dict[str, Any]:
    """清理变量字典
    
    移除保留变量和不在允许列表中的变量。
    
    Args:
        variables: 要清理的变量字典
        allowed_keys: 允许的键集合（如果为None，则允许所有非保留键）
        
    Returns:
        清理后的变量字典
    """
    result = {}
    
    for key, value in variables.items():
        # 跳过保留变量
        if key in RESERVED_VARIABLES:
            continue
        
        # 检查允许列表
        if allowed_keys is not None and key not in allowed_keys:
            continue
        
        result[key] = value
    
    return result
