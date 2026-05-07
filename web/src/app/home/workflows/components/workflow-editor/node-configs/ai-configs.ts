/**
 * AI Node Configurations
 *
 * Defines configurations for all AI-related node types:
 * - llm_call: Call a large language model
 * - question_classifier: Classify user questions into categories
 * - parameter_extractor: Extract structured parameters from text
 * - knowledge_retrieval: Retrieve information from knowledge bases
 * - text_embedding: Generate text embeddings
 * - intent_recognition: Recognize user intent
 */

import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import { NodeConfigMeta, createInput, createOutput } from './types';

/**
 * LLM Call Node
 * Makes a call to a large language model
 */
export const llmCallConfig: NodeConfigMeta = {
  nodeType: 'llm_call',
  label: {
    en_US: 'LLM Call',
    zh_Hans: 'LLM 调用',
  },
  description: {
    en_US: 'Call a large language model to generate responses',
    zh_Hans: '调用大语言模型生成响应',
  },
  icon: 'Brain',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('input', 'string', {
      description: 'Input text to send to the model',
      label: { en_US: 'Input', zh_Hans: '输入' },
    }),
    createInput('context', 'object', {
      description: 'Additional context data',
      label: { en_US: 'Context', zh_Hans: '上下文' },
      required: false,
    }),
  ],
  outputs: [
    createOutput('response', 'string', {
      description: 'Model response text',
      label: { en_US: 'Response', zh_Hans: '响应' },
    }),
    createOutput('usage', 'object', {
      description: 'Token usage information',
      label: { en_US: 'Usage', zh_Hans: '使用量' },
    }),
    createOutput('parsed', 'object', {
      description: 'Parsed output (if output format is JSON)',
      label: { en_US: 'Parsed', zh_Hans: '解析结果' },
    }),
  ],
  configSchema: [
    {
      id: 'model',
      name: 'model',
      type: DynamicFormItemType.LLM_MODEL_SELECTOR,
      label: {
        en_US: 'Model',
        zh_Hans: '模型',
      },
      description: {
        en_US: 'Select the LLM model to use',
        zh_Hans: '选择要使用的 LLM 模型',
      },
      required: true,
      default: '',
    },
    {
      id: 'system_prompt',
      name: 'system_prompt',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'System Prompt',
        zh_Hans: '系统提示词',
      },
      description: {
        en_US:
          'System prompt to set the model behavior (supports variable interpolation with {{variable}})',
        zh_Hans:
          '设置模型行为的系统提示词（支持使用 {{variable}} 进行变量插值）',
      },
      required: false,
      default: '',
    },
    {
      id: 'user_prompt_template',
      name: 'user_prompt_template',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'User Prompt Template',
        zh_Hans: '用户提示词模板',
      },
      description: {
        en_US:
          'User prompt template with variable placeholders (e.g., {{input}}, {{context.key}})',
        zh_Hans:
          '带有变量占位符的用户提示词模板（例如 {{input}}、{{context.key}}）',
      },
      required: true,
      default: '{{input}}',
    },
    {
      id: 'temperature',
      name: 'temperature',
      type: DynamicFormItemType.FLOAT,
      label: {
        en_US: 'Temperature',
        zh_Hans: '温度',
      },
      description: {
        en_US:
          'Controls randomness in responses (0.0 = deterministic, 2.0 = very random)',
        zh_Hans: '控制响应的随机性（0.0 = 确定性，2.0 = 非常随机）',
      },
      required: false,
      default: 0.7,
    },
    {
      id: 'max_tokens',
      name: 'max_tokens',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Max Tokens',
        zh_Hans: '最大令牌数',
      },
      description: {
        en_US:
          'Maximum number of tokens to generate (leave 0 for model default)',
        zh_Hans: '生成的最大令牌数（设为 0 使用模型默认值）',
      },
      required: false,
      default: 0,
    },
    {
      id: 'output_format',
      name: 'output_format',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Output Format',
        zh_Hans: '输出格式',
      },
      description: {
        en_US: 'Expected format of the model output',
        zh_Hans: '模型输出的预期格式',
      },
      required: false,
      default: 'text',
      options: [
        { name: 'text', label: { en_US: 'Plain Text', zh_Hans: '纯文本' } },
        { name: 'json', label: { en_US: 'JSON', zh_Hans: 'JSON' } },
        {
          name: 'markdown',
          label: { en_US: 'Markdown', zh_Hans: 'Markdown 文本' },
        },
      ],
    },
    {
      id: 'json_schema',
      name: 'json_schema',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'JSON Schema',
        zh_Hans: 'JSON Schema',
      },
      description: {
        en_US: 'JSON schema for structured output validation (optional)',
        zh_Hans: '用于结构化输出验证的 JSON Schema（可选）',
      },
      required: false,
      default: '',
      show_if: {
        field: 'output_format',
        operator: 'eq',
        value: 'json',
      },
    },
    {
      id: 'enable_tools',
      name: 'enable_tools',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Enable Tools',
        zh_Hans: '启用工具',
      },
      description: {
        en_US: 'Allow the model to use function calling tools',
        zh_Hans: '允许模型使用函数调用工具',
      },
      required: false,
      default: false,
    },
    {
      id: 'tools',
      name: 'tools',
      type: DynamicFormItemType.TOOLS_SELECTOR,
      label: {
        en_US: 'Tools',
        zh_Hans: '工具',
      },
      description: {
        en_US: 'Select tools that the model can use',
        zh_Hans: '选择模型可以使用的工具',
      },
      required: false,
      default: [],
      show_if: {
        field: 'enable_tools',
        operator: 'eq',
        value: true,
      },
    },
  ],
  defaultConfig: {
    model: '',
    system_prompt: '',
    user_prompt_template: '{{input}}',
    temperature: 0.7,
    max_tokens: 0,
    output_format: 'text',
    json_schema: '',
    enable_tools: false,
    tools: [],
  },
};

/**
 * Question Classifier Node
 * Classifies user questions into predefined categories
 */
export const questionClassifierConfig: NodeConfigMeta = {
  nodeType: 'question_classifier',
  label: {
    en_US: 'Question Classifier',
    zh_Hans: '问题分类器',
  },
  description: {
    en_US: 'Classify user questions into predefined categories using AI',
    zh_Hans: '使用 AI 将用户问题分类到预定义的类别中',
  },
  icon: 'Tags',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('question', 'string', {
      description: 'The question to classify',
      label: { en_US: 'Question', zh_Hans: '问题' },
    }),
  ],
  outputs: [
    createOutput('category', 'string', {
      description: 'The classified category',
      label: { en_US: 'Category', zh_Hans: '分类' },
    }),
    createOutput('confidence', 'number', {
      description: 'Classification confidence score (0-1)',
      label: { en_US: 'Confidence', zh_Hans: '置信度' },
    }),
    createOutput('all_scores', 'object', {
      description: 'Scores for all categories',
      label: { en_US: 'All Scores', zh_Hans: '所有分数' },
    }),
  ],
  configSchema: [
    {
      id: 'model',
      name: 'model',
      type: DynamicFormItemType.LLM_MODEL_SELECTOR,
      label: {
        en_US: 'Classification Model',
        zh_Hans: '分类模型',
      },
      description: {
        en_US: 'Select the model to use for classification',
        zh_Hans: '选择用于分类的模型',
      },
      required: true,
      default: '',
    },
    {
      id: 'categories',
      name: 'categories',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Categories Definition',
        zh_Hans: '分类定义',
      },
      description: {
        en_US:
          'Define categories in JSON format: [{"name": "category1", "description": "...", "examples": ["..."]}]',
        zh_Hans:
          '使用 JSON 格式定义分类: [{"name": "分类1", "description": "...", "examples": ["..."]}]',
      },
      required: true,
      default: '[]',
    },
    {
      id: 'confidence_threshold',
      name: 'confidence_threshold',
      type: DynamicFormItemType.FLOAT,
      label: {
        en_US: 'Confidence Threshold',
        zh_Hans: '置信度阈值',
      },
      description: {
        en_US: 'Minimum confidence score required (0.0-1.0)',
        zh_Hans: '所需的最小置信度分数（0.0-1.0）',
      },
      required: false,
      default: 0.7,
    },
    {
      id: 'fallback_category',
      name: 'fallback_category',
      type: DynamicFormItemType.STRING,
      label: {
        en_US: 'Fallback Category',
        zh_Hans: '默认分类',
      },
      description: {
        en_US: 'Category to use when confidence is below threshold',
        zh_Hans: '当置信度低于阈值时使用的分类',
      },
      required: false,
      default: 'other',
    },
  ],
  defaultConfig: {
    model: '',
    categories: '[]',
    confidence_threshold: 0.7,
    fallback_category: 'other',
  },
};

/**
 * Parameter Extractor Node
 * Extracts structured parameters from natural language
 */
export const parameterExtractorConfig: NodeConfigMeta = {
  nodeType: 'parameter_extractor',
  label: {
    en_US: 'Parameter Extractor',
    zh_Hans: '参数提取器',
  },
  description: {
    en_US: 'Extract structured parameters from natural language text using AI',
    zh_Hans: '使用 AI 从自然语言文本中提取结构化参数',
  },
  icon: 'FileSearch',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('text', 'string', {
      description: 'Text to extract parameters from',
      label: { en_US: 'Text', zh_Hans: '文本' },
    }),
  ],
  outputs: [
    createOutput('parameters', 'object', {
      description: 'Extracted parameters as key-value pairs',
      label: { en_US: 'Parameters', zh_Hans: '参数' },
    }),
    createOutput('missing', 'array', {
      description: 'List of required parameters that could not be extracted',
      label: { en_US: 'Missing', zh_Hans: '缺失项' },
    }),
    createOutput('success', 'boolean', {
      description: 'Whether all required parameters were extracted',
      label: { en_US: 'Success', zh_Hans: '成功' },
    }),
  ],
  configSchema: [
    {
      id: 'model',
      name: 'model',
      type: DynamicFormItemType.LLM_MODEL_SELECTOR,
      label: {
        en_US: 'Extraction Model',
        zh_Hans: '提取模型',
      },
      description: {
        en_US: 'Select the model to use for parameter extraction',
        zh_Hans: '选择用于参数提取的模型',
      },
      required: true,
      default: '',
    },
    {
      id: 'parameters',
      name: 'parameters',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Parameters Schema',
        zh_Hans: '参数架构',
      },
      description: {
        en_US:
          'JSON array defining expected parameters: [{"name": "date", "type": "string", "description": "Meeting date", "required": true}]',
        zh_Hans:
          '定义期望参数的 JSON 数组: [{"name": "日期", "type": "string", "description": "会议日期", "required": true}]',
      },
      required: true,
      default: '[]',
    },
    {
      id: 'extraction_prompt',
      name: 'extraction_prompt',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Extraction Prompt',
        zh_Hans: '提取提示',
      },
      description: {
        en_US: 'Additional instructions for the extraction model',
        zh_Hans: '提取模型的额外指令',
      },
      required: false,
      default: '',
    },
    {
      id: 'strict_mode',
      name: 'strict_mode',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Strict Mode',
        zh_Hans: '严格模式',
      },
      description: {
        en_US: 'Fail if any required parameter cannot be extracted',
        zh_Hans: '如果任何必需参数无法提取则失败',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    model: '',
    parameters_definition: '[]',
    extraction_prompt: '',
    strict_mode: true,
  },
};

/**
 * Knowledge Retrieval Node
 * Retrieves relevant information from knowledge bases
 */
export const knowledgeRetrievalConfig: NodeConfigMeta = {
  nodeType: 'knowledge_retrieval',
  label: {
    en_US: 'Knowledge Retrieval',
    zh_Hans: '知识检索',
  },
  description: {
    en_US:
      'Retrieve relevant information from knowledge bases using semantic search',
    zh_Hans: '使用语义搜索从知识库中检索相关信息',
  },
  icon: 'BookOpen',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('query', 'string', {
      description: 'Query text to search for',
      label: { en_US: 'Query', zh_Hans: '查询' },
    }),
  ],
  outputs: [
    createOutput('results', 'array', {
      description: 'Retrieved documents/chunks',
      label: { en_US: 'Results', zh_Hans: '结果' },
    }),
    createOutput('context', 'string', {
      description: 'Concatenated text from all results',
      label: { en_US: 'Context', zh_Hans: '上下文' },
    }),
    createOutput('scores', 'array', {
      description: 'Similarity scores for each result',
      label: { en_US: 'Scores', zh_Hans: '分数' },
    }),
  ],
  configSchema: [
    {
      id: 'knowledge_bases',
      name: 'knowledge_bases',
      type: DynamicFormItemType.KNOWLEDGE_BASE_MULTI_SELECTOR,
      label: {
        en_US: 'Knowledge Bases',
        zh_Hans: '知识库',
      },
      description: {
        en_US: 'Select knowledge bases to search',
        zh_Hans: '选择要搜索的知识库',
      },
      required: true,
      default: [],
    },
    {
      id: 'top_k',
      name: 'top_k',
      type: DynamicFormItemType.INT,
      label: {
        en_US: 'Top K Results',
        zh_Hans: '返回数量 (Top K)',
      },
      description: {
        en_US: 'Number of top results to retrieve',
        zh_Hans: '返回的最相关结果数量',
      },
      required: false,
      default: 5,
    },
    {
      id: 'similarity_threshold',
      name: 'similarity_threshold',
      type: DynamicFormItemType.FLOAT,
      label: {
        en_US: 'Similarity Threshold',
        zh_Hans: '相似度阈值',
      },
      description: {
        en_US: 'Minimum similarity score (0.0-1.0) for results to be included',
        zh_Hans: '结果被包含的最小相似度分数（0.0-1.0）',
      },
      required: false,
      default: 0.5,
    },
    {
      id: 'retrieval_mode',
      name: 'retrieval_mode',
      type: DynamicFormItemType.SELECT,
      label: {
        en_US: 'Retrieval Mode',
        zh_Hans: '检索模式',
      },
      description: {
        en_US: 'Method used for retrieving documents',
        zh_Hans: '用于检索文档的方法',
      },
      required: false,
      default: 'vector',
      options: [
        {
          name: 'vector',
          label: { en_US: 'Vector Search', zh_Hans: '向量检索' },
        },
        {
          name: 'hybrid',
          label: { en_US: 'Hybrid Search', zh_Hans: '混合检索' },
        },
        {
          name: 'keyword',
          label: { en_US: 'Keyword Search', zh_Hans: '关键词检索' },
        },
      ],
    },
    {
      id: 'rerank_enabled',
      name: 'rerank_enabled',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Enable Reranking',
        zh_Hans: '启用重排序',
      },
      description: {
        en_US: 'Use a reranking model to improve result relevance',
        zh_Hans: '使用重排序模型提高结果相关性',
      },
      required: false,
      default: false,
    },
    {
      id: 'rerank_model',
      name: 'rerank_model',
      type: DynamicFormItemType.RERANK_MODEL_SELECTOR,
      label: {
        en_US: 'Rerank Model',
        zh_Hans: '重排序模型',
      },
      description: {
        en_US: 'Model to use for reranking results',
        zh_Hans: '用于结果重排序的模型',
      },
      required: false,
      default: '',
      show_if: {
        field: 'rerank_enabled',
        operator: 'eq',
        value: true,
      },
    },
  ],
  defaultConfig: {
    knowledge_bases: [],
    top_k: 5,
    similarity_threshold: 0.5,
    retrieval_mode: 'vector',
    rerank_enabled: false,
    rerank_model: '',
  },
};

/**
 * Text Embedding Node
 * Generates vector embeddings for text
 */
export const textEmbeddingConfig: NodeConfigMeta = {
  nodeType: 'text_embedding',
  label: {
    en_US: 'Text Embedding',
    zh_Hans: '文本嵌入',
  },
  description: {
    en_US: 'Generate vector embeddings for text using an embedding model',
    zh_Hans: '使用嵌入模型为文本生成向量嵌入',
  },
  icon: 'Binary',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('text', 'string', {
      description: 'Text to embed',
      label: { en_US: 'Text', zh_Hans: '文本' },
    }),
  ],
  outputs: [
    createOutput('embedding', 'array', {
      description: 'Vector embedding array',
      label: { en_US: 'Embedding', zh_Hans: '嵌入向量' },
    }),
    createOutput('dimensions', 'number', {
      description: 'Number of dimensions in the embedding',
      label: { en_US: 'Dimensions', zh_Hans: '维度数' },
    }),
  ],
  configSchema: [
    {
      id: 'model',
      name: 'model',
      type: DynamicFormItemType.EMBEDDING_MODEL_SELECTOR,
      label: {
        en_US: 'Embedding Model',
        zh_Hans: '嵌入模型',
      },
      description: {
        en_US: 'Select the embedding model to use',
        zh_Hans: '选择要使用的嵌入模型',
      },
      required: true,
      default: '',
    },
  ],
  defaultConfig: {
    model: '',
  },
};

/**
 * Intent Recognition Node
 * Recognizes user intent from natural language
 */
export const intentRecognitionConfig: NodeConfigMeta = {
  nodeType: 'intent_recognition',
  label: {
    en_US: 'Intent Recognition',
    zh_Hans: '意图识别',
  },
  description: {
    en_US: 'Recognize user intent from natural language using AI',
    zh_Hans: '使用 AI 从自然语言中识别用户意图',
  },
  icon: 'Target',
  category: 'process',
  color: '#8b5cf6',
  inputs: [
    createInput('text', 'string', {
      description: 'Text to analyze',
      label: { en_US: 'Text', zh_Hans: '文本' },
    }),
  ],
  outputs: [
    createOutput('intent', 'string', {
      description: 'Recognized intent',
      label: { en_US: 'Intent', zh_Hans: '意图' },
    }),
    createOutput('confidence', 'number', {
      description: 'Recognition confidence score',
      label: { en_US: 'Confidence', zh_Hans: '置信度' },
    }),
    createOutput('entities', 'object', {
      description: 'Extracted entities from the text',
      label: { en_US: 'Entities', zh_Hans: '实体' },
    }),
  ],
  configSchema: [
    {
      id: 'model',
      name: 'model',
      type: DynamicFormItemType.LLM_MODEL_SELECTOR,
      label: {
        en_US: 'Recognition Model',
        zh_Hans: '识别模型',
      },
      description: {
        en_US: 'Select the model for intent recognition',
        zh_Hans: '选择用于意图识别的模型',
      },
      required: true,
      default: '',
    },
    {
      id: 'intents_definition',
      name: 'intents_definition',
      type: DynamicFormItemType.TEXT,
      label: {
        en_US: 'Intents Definition',
        zh_Hans: '意图定义',
      },
      description: {
        en_US:
          'Define intents in JSON format: [{"name": "intent1", "description": "...", "examples": ["..."]}]',
        zh_Hans:
          '使用 JSON 格式定义意图: [{"name": "意图1", "description": "...", "examples": ["..."]}]',
      },
      required: true,
      default: '[]',
    },
    {
      id: 'extract_entities',
      name: 'extract_entities',
      type: DynamicFormItemType.BOOLEAN,
      label: {
        en_US: 'Extract Entities',
        zh_Hans: '提取实体',
      },
      description: {
        en_US: 'Also extract named entities from the text',
        zh_Hans: '同时从文本中提取命名实体',
      },
      required: false,
      default: true,
    },
  ],
  defaultConfig: {
    model: '',
    intents_definition: '[]',
    extract_entities: true,
  },
};

/**
 * All AI node configurations
 */
export const aiConfigs: NodeConfigMeta[] = [
  llmCallConfig,
  questionClassifierConfig,
  parameterExtractorConfig,
  knowledgeRetrievalConfig,
  textEmbeddingConfig,
  intentRecognitionConfig,
];

/**
 * Get AI config by type
 */
export function getAIConfig(nodeType: string): NodeConfigMeta | undefined {
  return aiConfigs.find((config) => config.nodeType === nodeType);
}
