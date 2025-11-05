"""
Tests for environment variable override functionality in YAML config
"""

import os
import pytest
import tempfile
import yaml

from pkg.config.impls.yaml import _apply_env_overrides, YAMLConfigFile


class TestEnvOverrides:
    """Test environment variable override functionality"""
    
    def test_simple_string_override(self):
        """Test overriding a simple string value"""
        cfg = {
            'api': {
                'port': 5300
            }
        }
        
        # Set environment variable
        os.environ['API__PORT'] = '8080'
        
        result = _apply_env_overrides(cfg)
        
        assert result['api']['port'] == 8080
        
        # Cleanup
        del os.environ['API__PORT']
    
    def test_nested_key_override(self):
        """Test overriding nested keys with __ delimiter"""
        cfg = {
            'concurrency': {
                'pipeline': 20,
                'session': 1
            }
        }
        
        os.environ['CONCURRENCY__PIPELINE'] = '50'
        
        result = _apply_env_overrides(cfg)
        
        assert result['concurrency']['pipeline'] == 50
        assert result['concurrency']['session'] == 1  # Unchanged
        
        del os.environ['CONCURRENCY__PIPELINE']
    
    def test_deep_nested_override(self):
        """Test overriding deeply nested keys"""
        cfg = {
            'system': {
                'jwt': {
                    'expire': 604800,
                    'secret': ''
                }
            }
        }
        
        os.environ['SYSTEM__JWT__EXPIRE'] = '86400'
        os.environ['SYSTEM__JWT__SECRET'] = 'my_secret_key'
        
        result = _apply_env_overrides(cfg)
        
        assert result['system']['jwt']['expire'] == 86400
        assert result['system']['jwt']['secret'] == 'my_secret_key'
        
        del os.environ['SYSTEM__JWT__EXPIRE']
        del os.environ['SYSTEM__JWT__SECRET']
    
    def test_underscore_in_key(self):
        """Test keys with underscores like runtime_ws_url"""
        cfg = {
            'plugin': {
                'enable': True,
                'runtime_ws_url': 'ws://localhost:5400/control/ws'
            }
        }
        
        os.environ['PLUGIN__RUNTIME_WS_URL'] = 'ws://newhost:6000/ws'
        
        result = _apply_env_overrides(cfg)
        
        assert result['plugin']['runtime_ws_url'] == 'ws://newhost:6000/ws'
        
        del os.environ['PLUGIN__RUNTIME_WS_URL']
    
    def test_boolean_conversion(self):
        """Test boolean value conversion"""
        cfg = {
            'plugin': {
                'enable': True,
                'enable_marketplace': False
            }
        }
        
        os.environ['PLUGIN__ENABLE'] = 'false'
        os.environ['PLUGIN__ENABLE_MARKETPLACE'] = 'true'
        
        result = _apply_env_overrides(cfg)
        
        assert result['plugin']['enable'] is False
        assert result['plugin']['enable_marketplace'] is True
        
        del os.environ['PLUGIN__ENABLE']
        del os.environ['PLUGIN__ENABLE_MARKETPLACE']
    
    def test_ignore_dict_type(self):
        """Test that dict types are ignored"""
        cfg = {
            'database': {
                'use': 'sqlite',
                'sqlite': {
                    'path': 'data/langbot.db'
                }
            }
        }
        
        # Try to override a dict value - should be ignored
        os.environ['DATABASE__SQLITE'] = 'new_value'
        
        result = _apply_env_overrides(cfg)
        
        # Should remain a dict, not overridden
        assert isinstance(result['database']['sqlite'], dict)
        assert result['database']['sqlite']['path'] == 'data/langbot.db'
        
        del os.environ['DATABASE__SQLITE']
    
    def test_ignore_list_type(self):
        """Test that list/array types are ignored"""
        cfg = {
            'admins': ['admin1', 'admin2'],
            'command': {
                'enable': True,
                'prefix': ['!', '！']
            }
        }
        
        # Try to override list values - should be ignored
        os.environ['ADMINS'] = 'admin3'
        os.environ['COMMAND__PREFIX'] = '?'
        
        result = _apply_env_overrides(cfg)
        
        # Should remain lists, not overridden
        assert isinstance(result['admins'], list)
        assert result['admins'] == ['admin1', 'admin2']
        assert isinstance(result['command']['prefix'], list)
        assert result['command']['prefix'] == ['!', '！']
        
        del os.environ['ADMINS']
        del os.environ['COMMAND__PREFIX']
    
    def test_lowercase_env_var_ignored(self):
        """Test that lowercase environment variables are ignored"""
        cfg = {
            'api': {
                'port': 5300
            }
        }
        
        os.environ['api__port'] = '8080'
        
        result = _apply_env_overrides(cfg)
        
        # Should not be overridden
        assert result['api']['port'] == 5300
        
        del os.environ['api__port']
    
    def test_no_double_underscore_ignored(self):
        """Test that env vars without __ are ignored"""
        cfg = {
            'api': {
                'port': 5300
            }
        }
        
        os.environ['APIPORT'] = '8080'
        
        result = _apply_env_overrides(cfg)
        
        # Should not be overridden
        assert result['api']['port'] == 5300
        
        del os.environ['APIPORT']
    
    def test_nonexistent_key_ignored(self):
        """Test that env vars for non-existent keys are ignored"""
        cfg = {
            'api': {
                'port': 5300
            }
        }
        
        os.environ['API__NONEXISTENT'] = 'value'
        
        result = _apply_env_overrides(cfg)
        
        # Should not create new key
        assert 'nonexistent' not in result['api']
        
        del os.environ['API__NONEXISTENT']
    
    def test_integer_conversion(self):
        """Test integer value conversion"""
        cfg = {
            'concurrency': {
                'pipeline': 20
            }
        }
        
        os.environ['CONCURRENCY__PIPELINE'] = '100'
        
        result = _apply_env_overrides(cfg)
        
        assert result['concurrency']['pipeline'] == 100
        assert isinstance(result['concurrency']['pipeline'], int)
        
        del os.environ['CONCURRENCY__PIPELINE']
    
    def test_multiple_overrides(self):
        """Test multiple environment variable overrides at once"""
        cfg = {
            'api': {
                'port': 5300
            },
            'concurrency': {
                'pipeline': 20,
                'session': 1
            },
            'plugin': {
                'enable': False
            }
        }
        
        os.environ['API__PORT'] = '8080'
        os.environ['CONCURRENCY__PIPELINE'] = '50'
        os.environ['PLUGIN__ENABLE'] = 'true'
        
        result = _apply_env_overrides(cfg)
        
        assert result['api']['port'] == 8080
        assert result['concurrency']['pipeline'] == 50
        assert result['plugin']['enable'] is True
        
        del os.environ['API__PORT']
        del os.environ['CONCURRENCY__PIPELINE']
        del os.environ['PLUGIN__ENABLE']


@pytest.mark.asyncio
class TestYAMLConfigFileWithEnv:
    """Test YAMLConfigFile with environment variable overrides"""
    
    async def test_load_with_env_override(self):
        """Test that load() applies environment variable overrides"""
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            config_path = temp_file.name
            yaml.dump({
                'api': {'port': 5300},
                'concurrency': {'pipeline': 20}
            }, temp_file)
        
        try:
            # Set environment variable
            os.environ['API__PORT'] = '8080'
            
            # Create YAMLConfigFile instance and load
            yaml_file = YAMLConfigFile(config_path)
            cfg = await yaml_file.load(completion=False)
            
            # Check that env override was applied
            assert cfg['api']['port'] == 8080
            
        finally:
            # Cleanup
            if 'API__PORT' in os.environ:
                del os.environ['API__PORT']
            if os.path.exists(config_path):
                os.unlink(config_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
