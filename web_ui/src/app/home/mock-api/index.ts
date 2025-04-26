import {GetMetaDataResponse} from "@/app/infra/api/api-types/pipelines/GetMetaDataResponse";
import {ApiResponse} from "@/app/infra/api/api-types";

export async function fetchPipelineMetaData(): Promise<ApiResponse<GetMetaDataResponse>> {
    return {
        "code": 0,
        "data": {
            "configs": [
                {
                    "label": {
                        "en_US": "Trigger",
                        "zh_CN": "触发条件"
                    },
                    "name": "trigger",
                    "stages": [
                        {
                            "config": [
                                {
                                    "default": false,
                                    "description": {
                                        "en_US": "Whether to trigger when the message mentions the bot",
                                        "zh_CN": "是否在消息@机器人时触发"
                                    },
                                    "label": {
                                        "en_US": "At",
                                        "zh_CN": "@"
                                    },
                                    "name": "at",
                                    "required": true,
                                    "type": "boolean"
                                },
                                {
                                    "default": [],
                                    "description": {
                                        "en_US": "The prefix of the message",
                                        "zh_CN": "消息前缀"
                                    },
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Prefix",
                                        "zh_CN": "前缀"
                                    },
                                    "name": "prefix",
                                    "required": true,
                                    "type": "array"
                                },
                                {
                                    "default": [],
                                    "description": {
                                        "en_US": "The regexp of the message",
                                        "zh_CN": "消息正则表达式"
                                    },
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Regexp",
                                        "zh_CN": "正则表达式"
                                    },
                                    "name": "regexp",
                                    "required": true,
                                    "type": "array"
                                },
                                {
                                    "default": 0,
                                    "description": {
                                        "en_US": "The probability of the random response, range from 0.0 to 1.0",
                                        "zh_CN": "随机响应概率，范围为 0.0-1.0"
                                    },
                                    "label": {
                                        "en_US": "Random",
                                        "zh_CN": "随机"
                                    },
                                    "name": "random",
                                    "required": false,
                                    "type": "float"
                                }
                            ],
                            "description": {
                                "en_US": "The group respond rule of the pipeline",
                                "zh_CN": "群响应规则"
                            },
                            "label": {
                                "en_US": "Group Respond Rule",
                                "zh_CN": "群响应规则"
                            },
                            "name": "group-respond-rules"
                        },
                        {
                            "config": [
                                {
                                    "default": "blacklist",
                                    "description": {
                                        "en_US": "The mode of the access control",
                                        "zh_CN": "访问控制模式"
                                    },
                                    "label": {
                                        "en_US": "Mode",
                                        "zh_CN": "模式"
                                    },
                                    "name": "mode",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Blacklist",
                                                "zh_CN": "黑名单"
                                            },
                                            "name": "blacklist"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Whitelist",
                                                "zh_CN": "白名单"
                                            },
                                            "name": "whitelist"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                },
                                {
                                    "default": [],
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Blacklist",
                                        "zh_CN": "黑名单"
                                    },
                                    "name": "blacklist",
                                    "required": true,
                                    "type": "array"
                                },
                                {
                                    "default": [],
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Whitelist",
                                        "zh_CN": "白名单"
                                    },
                                    "name": "whitelist",
                                    "required": true,
                                    "type": "array"
                                }
                            ],
                            "label": {
                                "en_US": "Access Control",
                                "zh_CN": "访问控制"
                            },
                            "name": "access-control"
                        },
                        {
                            "config": [
                                {
                                    "default": [],
                                    "description": {
                                        "en_US": "The prefix of the message",
                                        "zh_CN": "消息前缀"
                                    },
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Prefix",
                                        "zh_CN": "前缀"
                                    },
                                    "name": "prefix",
                                    "required": true,
                                    "type": "array"
                                },
                                {
                                    "default": [],
                                    "description": {
                                        "en_US": "The regexp of the message",
                                        "zh_CN": "消息正则表达式"
                                    },
                                    "items": {
                                        "type": "string"
                                    },
                                    "label": {
                                        "en_US": "Regexp",
                                        "zh_CN": "正则表达式"
                                    },
                                    "name": "regexp",
                                    "required": true,
                                    "type": "array"
                                }
                            ],
                            "label": {
                                "en_US": "Ignore Rules",
                                "zh_CN": "消息忽略规则"
                            },
                            "name": "ignore-rules"
                        }
                    ]
                },
                {
                    "label": {
                        "en_US": "Safety Control",
                        "zh_CN": "安全控制"
                    },
                    "name": "safety",
                    "stages": [
                        {
                            "config": [
                                {
                                    "default": "all",
                                    "label": {
                                        "en_US": "Scope",
                                        "zh_CN": "检查范围"
                                    },
                                    "name": "scope",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "All",
                                                "zh_CN": "全部"
                                            },
                                            "name": "all"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Income Message",
                                                "zh_CN": "传入消息（用户消息）"
                                            },
                                            "name": "income-msg"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Output Message",
                                                "zh_CN": "传出消息（机器人消息）"
                                            },
                                            "name": "output-msg"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                },
                                {
                                    "default": false,
                                    "label": {
                                        "en_US": "Check Sensitive Words",
                                        "zh_CN": "检查敏感词"
                                    },
                                    "name": "check-sensitive-words",
                                    "required": true,
                                    "type": "boolean"
                                }
                            ],
                            "label": {
                                "en_US": "Content Filter",
                                "zh_CN": "内容过滤"
                            },
                            "name": "content-filter"
                        },
                        {
                            "config": [
                                {
                                    "default": 60,
                                    "label": {
                                        "en_US": "Window Length",
                                        "zh_CN": "窗口长度（秒）"
                                    },
                                    "name": "window-length",
                                    "required": true,
                                    "type": "integer"
                                },
                                {
                                    "default": 60,
                                    "label": {
                                        "en_US": "Limitation",
                                        "zh_CN": "限制次数"
                                    },
                                    "name": "limitation",
                                    "required": true,
                                    "type": "integer"
                                },
                                {
                                    "default": "drop",
                                    "label": {
                                        "en_US": "Strategy",
                                        "zh_CN": "策略"
                                    },
                                    "name": "strategy",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Drop",
                                                "zh_CN": "丢弃"
                                            },
                                            "name": "drop"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Wait",
                                                "zh_CN": "等待"
                                            },
                                            "name": "wait"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                }
                            ],
                            "label": {
                                "en_US": "Rate Limit",
                                "zh_CN": "速率限制"
                            },
                            "name": "rate-limit"
                        }
                    ]
                },
                {
                    "label": {
                        "en_US": "AI Feature",
                        "zh_CN": "AI 能力"
                    },
                    "name": "ai",
                    "stages": [
                        {
                            "config": [
                                {
                                    "default": "local-agent",
                                    "label": {
                                        "en_US": "Runner",
                                        "zh_CN": "运行器"
                                    },
                                    "name": "runner",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Embedded Agent",
                                                "zh_CN": "内置 Agent"
                                            },
                                            "name": "local-agent"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Dify Service API",
                                                "zh_CN": "Dify 服务 API"
                                            },
                                            "name": "dify-service-api"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Aliyun Dashscope App API",
                                                "zh_CN": "阿里云百炼平台 API"
                                            },
                                            "name": "dashscope-app-api"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                }
                            ],
                            "label": {
                                "en_US": "Runner",
                                "zh_CN": "运行方式"
                            },
                            "name": "runner"
                        },
                        {
                            "config": [
                                {
                                    "label": {
                                        "en_US": "Model",
                                        "zh_CN": "模型"
                                    },
                                    "name": "model",
                                    "required": true,
                                    "scope": "/provider/models/llm",
                                    "type": "select"
                                },
                                {
                                    "default": 10,
                                    "label": {
                                        "en_US": "Max Round",
                                        "zh_CN": "最大回合数"
                                    },
                                    "name": "max-round",
                                    "required": true,
                                    "type": "integer"
                                },
                                {
                                    "items": {
                                        "properties": {
                                            "content": {
                                                "type": "string"
                                            },
                                            "role": {
                                                "default": "user",
                                                "type": "string"
                                            }
                                        },
                                        "type": "object"
                                    },
                                    "label": {
                                        "en_US": "Prompt",
                                        "zh_CN": "提示词"
                                    },
                                    "name": "prompt",
                                    "required": true,
                                    "type": "array"
                                }
                            ],
                            "description": {
                                "en_US": "Configure the embedded agent of the pipeline",
                                "zh_CN": "配置内置 Agent"
                            },
                            "label": {
                                "en_US": "Embedded Agent",
                                "zh_CN": "内置 Agent"
                            },
                            "name": "local-agent"
                        },
                        {
                            "config": [
                                {
                                    "label": {
                                        "en_US": "Base URL",
                                        "zh_CN": "基础 URL"
                                    },
                                    "name": "base-url",
                                    "required": true,
                                    "type": "string"
                                },
                                {
                                    "default": "chat",
                                    "label": {
                                        "en_US": "App Type",
                                        "zh_CN": "应用类型"
                                    },
                                    "name": "app-type",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Chat",
                                                "zh_CN": "聊天（包括Chatflow）"
                                            },
                                            "name": "chat"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Agent",
                                                "zh_CN": "Agent"
                                            },
                                            "name": "agent"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Workflow",
                                                "zh_CN": "工作流"
                                            },
                                            "name": "workflow"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                },
                                {
                                    "label": {
                                        "en_US": "API Key",
                                        "zh_CN": "API 密钥"
                                    },
                                    "name": "api-key",
                                    "required": true,
                                    "type": "string"
                                },
                                {
                                    "default": "plain",
                                    "label": {
                                        "en_US": "CoT Convert",
                                        "zh_CN": "思维链转换策略"
                                    },
                                    "name": "thinking-convert",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Convert to <think>...</think>",
                                                "zh_CN": "转换成 <think>...</think>"
                                            },
                                            "name": "plain"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Original",
                                                "zh_CN": "原始"
                                            },
                                            "name": "original"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Remove",
                                                "zh_CN": "移除"
                                            },
                                            "name": "remove"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                }
                            ],
                            "description": {
                                "en_US": "Configure the Dify service API of the pipeline",
                                "zh_CN": "配置 Dify 服务 API"
                            },
                            "label": {
                                "en_US": "Dify Service API",
                                "zh_CN": "Dify 服务 API"
                            },
                            "name": "dify-service-api"
                        },
                        {
                            "config": [
                                {
                                    "default": "agent",
                                    "label": {
                                        "en_US": "App Type",
                                        "zh_CN": "应用类型"
                                    },
                                    "name": "app-type",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Agent",
                                                "zh_CN": "Agent"
                                            },
                                            "name": "agent"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Workflow",
                                                "zh_CN": "工作流"
                                            },
                                            "name": "workflow"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                },
                                {
                                    "label": {
                                        "en_US": "API Key",
                                        "zh_CN": "API 密钥"
                                    },
                                    "name": "api-key",
                                    "required": true,
                                    "type": "string"
                                },
                                {
                                    "label": {
                                        "en_US": "App ID",
                                        "zh_CN": "应用 ID"
                                    },
                                    "name": "app-id",
                                    "required": true,
                                    "type": "string"
                                },
                                {
                                    "default": "参考资料来自:",
                                    "label": {
                                        "en_US": "References Quote",
                                        "zh_CN": "引用文本"
                                    },
                                    "name": "references_quote",
                                    "required": false,
                                    "type": "string"
                                }
                            ],
                            "description": {
                                "en_US": "Configure the Aliyun Dashscope App API of the pipeline",
                                "zh_CN": "配置阿里云百炼平台 API"
                            },
                            "label": {
                                "en_US": "Aliyun Dashscope App API",
                                "zh_CN": "阿里云百炼平台 API"
                            },
                            "name": "dashscope-app-api"
                        }
                    ]
                },
                {
                    "label": {
                        "en_US": "Output Processing",
                        "zh_CN": "输出处理"
                    },
                    "name": "output",
                    "stages": [
                        {
                            "config": [
                                {
                                    "default": 1000,
                                    "label": {
                                        "en_US": "Threshold",
                                        "zh_CN": "阈值"
                                    },
                                    "name": "threshold",
                                    "required": true,
                                    "type": "integer"
                                },
                                {
                                    "default": "forward",
                                    "label": {
                                        "en_US": "Strategy",
                                        "zh_CN": "策略"
                                    },
                                    "name": "strategy",
                                    "options": [
                                        {
                                            "label": {
                                                "en_US": "Forward Message Component",
                                                "zh_CN": "转发消息组件"
                                            },
                                            "name": "forward"
                                        },
                                        {
                                            "label": {
                                                "en_US": "Convert to Image",
                                                "zh_CN": "转换为图片"
                                            },
                                            "name": "image"
                                        }
                                    ],
                                    "required": true,
                                    "type": "select"
                                },
                                {
                                    "default": "",
                                    "label": {
                                        "en_US": "Font Path",
                                        "zh_CN": "字体路径"
                                    },
                                    "name": "font-path",
                                    "required": true,
                                    "type": "string"
                                }
                            ],
                            "label": {
                                "en_US": "Long Text Processing",
                                "zh_CN": "长文本处理"
                            },
                            "name": "long-text-processing"
                        },
                        {
                            "config": [
                                {
                                    "default": 0,
                                    "label": {
                                        "en_US": "Min",
                                        "zh_CN": "最小秒数"
                                    },
                                    "name": "min",
                                    "required": true,
                                    "type": "integer"
                                },
                                {
                                    "default": 0,
                                    "label": {
                                        "en_US": "Max",
                                        "zh_CN": "最大秒数"
                                    },
                                    "name": "max",
                                    "required": true,
                                    "type": "integer"
                                }
                            ],
                            "label": {
                                "en_US": "Force Delay",
                                "zh_CN": "强制延迟"
                            },
                            "name": "force-delay"
                        },
                        {
                            "config": [
                                {
                                    "default": true,
                                    "label": {
                                        "en_US": "Hide Exception",
                                        "zh_CN": "不输出异常信息给用户"
                                    },
                                    "name": "hide-exception",
                                    "required": true,
                                    "type": "boolean"
                                },
                                {
                                    "default": true,
                                    "label": {
                                        "en_US": "At Sender",
                                        "zh_CN": "在回复中@发送者"
                                    },
                                    "name": "at-sender",
                                    "required": true,
                                    "type": "boolean"
                                },
                                {
                                    "default": false,
                                    "label": {
                                        "en_US": "Quote Origin",
                                        "zh_CN": "引用原文"
                                    },
                                    "name": "quote-origin",
                                    "required": true,
                                    "type": "boolean"
                                },
                                {
                                    "default": true,
                                    "label": {
                                        "en_US": "Track Function Calls",
                                        "zh_CN": "跟踪函数调用"
                                    },
                                    "name": "track-function-calls",
                                    "required": true,
                                    "type": "boolean"
                                }
                            ],
                            "label": {
                                "en_US": "Misc",
                                "zh_CN": "杂项"
                            },
                            "name": "misc"
                        }
                    ]
                }
            ]
        },
        "msg": "ok"
    }
}

