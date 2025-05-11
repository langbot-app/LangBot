/**
 * @see https://prettier.io/docs/configuration
 * @type {import("prettier").Config}
 */
const config = {
  // 单行长度
  printWidth: 80,
  // 缩进
  tabWidth: 2,
  // 使用空格代替tab缩进
  useTabs: false,
  // 句末使用分号
  semi: true,
  // 使用单引号
  singleQuote: true,
  // 大括号前后空格
  bracketSpacing: true,
  attributeVerticalAlignment: 'auto',
  trailingComma: 'all',
};

export default config;
