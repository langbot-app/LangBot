## 多个对话接口有何区别？

出于对稳定性的高要求，本项目主线接入的是GPT-3模型接口，此接口由OpenAI官方开放，稳定性强。  
目前支持通过加载[插件](https://github.com/RockChinQ/revLibs)的方式接入ChatGPT网页版，使用的是acheong08/ChatGPT的逆向工程库，但文本生成质量更高。  
同时，程序主线已支持ChatGPT API，并作为默认接口 [#195](https://github.com/RockChinQ/QChatGPT/issues/195)

|官方接口|ChatGPT网页版|ChatGPT API
|---|---|---|
|官方开放，稳定性高 | 由[acheong08](https://github.com/acheong08)破解网页版协议接入| 由OpenAI官方开放
|一次性回复，响应速度较快| 流式回复，响应速度较慢|响应速度较快|
|收费，0.02美元/千字|免费|收费，0.002美元/千字|
|GPT-3模型|GPT-3.5模型|GPT-3.5模型|
|任何地区主机均可使用(疑似受到GFW影响)|ChatGPT限制访问的区域使用有难度|任何地区主机均可使用(疑似受到GFW影响)|

