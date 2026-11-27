# Communication protocol between runtime and plugin

## Initialize Sequence

1. Connection established
2. Plugin `register_plugin`
3. Runtime `initialize_plugin` with plugin settings
4. Runtime `get_plugin_container`

