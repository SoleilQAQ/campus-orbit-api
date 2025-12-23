"""
天气配置工具函数

提供字段路径解析等功能
"""

import re
from typing import Any


def parse_field_path(data: dict, path: str) -> Any:
    """
    解析字段路径，支持点号分隔和数组索引
    
    示例：
    - "main.temp" -> data["main"]["temp"]
    - "weather[0].description" -> data["weather"][0]["description"]
    - "wind.speed" -> data["wind"]["speed"]
    
    Args:
        data: 原始数据字典
        path: 字段路径
        
    Returns:
        解析后的值，如果路径无效返回 None
    """
    if not data or not path:
        return None
    
    current = data
    
    # 分割路径，处理数组索引
    # 例如 "weather[0].description" -> ["weather", "[0]", "description"]
    parts = re.split(r'\.', path)
    
    for part in parts:
        if current is None:
            return None
        
        # 检查是否包含数组索引，如 "weather[0]"
        array_match = re.match(r'^(\w+)\[(\d+)\]$', part)
        
        if array_match:
            # 有数组索引
            key = array_match.group(1)
            index = int(array_match.group(2))
            
            if key:
                # 先获取键值
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            
            # 再获取数组元素
            if isinstance(current, list) and 0 <= index < len(current):
                current = current[index]
            else:
                return None
        else:
            # 普通键
            # 检查是否只有数组索引，如 "[0]"
            index_only_match = re.match(r'^\[(\d+)\]$', part)
            if index_only_match:
                index = int(index_only_match.group(1))
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
    
    return current


def map_weather_response(raw_data: dict, field_mapping: dict) -> dict:
    """
    根据字段映射将原始天气数据转换为标准格式
    
    Args:
        raw_data: 原始 API 返回数据
        field_mapping: 字段映射配置
        
    Returns:
        映射后的标准数据
    """
    result = {}
    
    for standard_field, path in field_mapping.items():
        value = parse_field_path(raw_data, path)
        result[standard_field] = value
    
    return result
