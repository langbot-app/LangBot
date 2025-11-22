"""
Tests for webhook_display_prefix configuration
"""

import os
import pytest
from typing import Any


def _apply_env_overrides_to_config(cfg: dict) -> dict:
    """Apply environment variable overrides to data/config.yaml
    
    Environment variables should be uppercase and use __ (double underscore) 
    to represent nested keys. For example:
    - CONCURRENCY__PIPELINE overrides concurrency.pipeline
    - PLUGIN__RUNTIME_WS_URL overrides plugin.runtime_ws_url
    
    Arrays and dict types are ignored.
    
    Args:
        cfg: Configuration dictionary
        
    Returns:
        Updated configuration dictionary
    """
    def convert_value(value: str, original_value: Any) -> Any:
        """Convert string value to appropriate type based on original value
        
        Args:
            value: String value from environment variable
            original_value: Original value to infer type from
            
        Returns:
            Converted value (falls back to string if conversion fails)
        """
        if isinstance(original_value, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(original_value, int):
            try:
                return int(value)
            except ValueError:
                # If conversion fails, keep as string (user error, but non-breaking)
                return value
        elif isinstance(original_value, float):
            try:
                return float(value)
            except ValueError:
                # If conversion fails, keep as string (user error, but non-breaking)
                return value
        else:
            return value
    
    # Process environment variables
    for env_key, env_value in os.environ.items():
        # Check if the environment variable is uppercase and contains __
        if not env_key.isupper():
            continue
        if '__' not in env_key:
            continue
            
        # Convert environment variable name to config path
        # e.g., CONCURRENCY__PIPELINE -> ['concurrency', 'pipeline']
        keys = [key.lower() for key in env_key.split('__')]
        
        # Navigate to the target value and validate the path
        current = cfg
        
        for i, key in enumerate(keys):
            if not isinstance(current, dict) or key not in current:
                break
            
            if i == len(keys) - 1:
                # At the final key - check if it's a scalar value
                if isinstance(current[key], (dict, list)):
                    # Skip dict and list types
                    pass
                else:
                    # Valid scalar value - convert and set it
                    converted_value = convert_value(env_value, current[key])
                    current[key] = converted_value
            else:
                # Navigate deeper
                current = current[key]
    
    return cfg


class TestWebhookDisplayPrefix:
    """Test webhook_display_prefix configuration functionality"""
    
    def test_default_webhook_display_prefix(self):
        """Test that the default webhook display prefix is correctly set"""
        cfg = {
            'api': {
                'port': 5300,
                'webhook_display_prefix': 'http://127.0.0.1:5300'
            }
        }
        
        # Should have the default value
        assert cfg['api']['webhook_display_prefix'] == 'http://127.0.0.1:5300'
    
    def test_webhook_display_prefix_env_override(self):
        """Test overriding webhook_display_prefix via environment variable"""
        cfg = {
            'api': {
                'port': 5300,
                'webhook_display_prefix': 'http://127.0.0.1:5300'
            }
        }
        
        # Set environment variable
        os.environ['API__WEBHOOK_DISPLAY_PREFIX'] = 'https://example.com:8080'
        
        result = _apply_env_overrides_to_config(cfg)
        
        assert result['api']['webhook_display_prefix'] == 'https://example.com:8080'
        
        # Cleanup
        del os.environ['API__WEBHOOK_DISPLAY_PREFIX']
    
    def test_webhook_display_prefix_with_custom_domain(self):
        """Test webhook_display_prefix with custom domain"""
        cfg = {
            'api': {
                'port': 5300,
                'webhook_display_prefix': 'http://127.0.0.1:5300'
            }
        }
        
        # Set to a custom domain
        os.environ['API__WEBHOOK_DISPLAY_PREFIX'] = 'https://bot.mycompany.com'
        
        result = _apply_env_overrides_to_config(cfg)
        
        assert result['api']['webhook_display_prefix'] == 'https://bot.mycompany.com'
        
        # Cleanup
        del os.environ['API__WEBHOOK_DISPLAY_PREFIX']
    
    def test_webhook_display_prefix_with_subdirectory(self):
        """Test webhook_display_prefix with subdirectory path"""
        cfg = {
            'api': {
                'port': 5300,
                'webhook_display_prefix': 'http://127.0.0.1:5300'
            }
        }
        
        # Set to a URL with subdirectory
        os.environ['API__WEBHOOK_DISPLAY_PREFIX'] = 'https://example.com/langbot'
        
        result = _apply_env_overrides_to_config(cfg)
        
        assert result['api']['webhook_display_prefix'] == 'https://example.com/langbot'
        
        # Cleanup
        del os.environ['API__WEBHOOK_DISPLAY_PREFIX']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
