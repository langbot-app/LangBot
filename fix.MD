## 底层模型请求器

- pkg/provider/modelmgr/requesters/...

给 invoke_llm 加个 stream: bool 参数，并允许 invoke_llm 返回两种参数：原来的 llm_entities.Message（非流式）和 返回 llm_entities.MessageChunk（流式，需要新增这个实体）的 AsyncGenerator

## Runner

- pkg/provider/runners/...

每个runner的run方法也允许传入stream: bool。

现在的run方法本身就是生成器（AsyncGenerator），因为agent是有多回合的，会生成多条Message。但现在需要支持文本消息可以分段。

现在run方法应该返回 AsyncGenerator[ Union[ Message, AsyncGenerator[MessageChunk] ] ]。

对于 local agent 的实现上，调用模型invoke_llm时，传入stream，当发现模型返回的是Message时，即按照现在的写法操作Message；当返回的是 AsyncGenerator 时，需要 yield MessageChunk 给上层，同时需要注意判断工具调用。

## 流水线

- pkg/pipeline/process/handlers/chat.py

之前这里就已经有一个生成器写法了，用于处理 AsyncGenerator[Message]，但现在需要加上一个判断，如果yield出来的是 Message 则按照现在的处理；如果yield出来的是 AsyncGenerator，那么就需要再 async for 一层；

因为流水线是基于责任链模式设计的，这里的生成结果只需要放入 Query 对象中，供下一层处理。

所以需要在 Query 对象中支持存入MessageChunk，现在只支持存 Message 到 resp_messages，这里得设计一下。

## 回复阶段

最终会在 pkg/pipeline/respback/respback.py 中检出 query 中的信息并发回，这里也要改成支持 MessagChunk 的。

这里应该判断适配器是否支持流式，若不支持，应该等待所有 MessageChunk 生成，拼接成 Message 再转换成 MessageChain 调用 send_message()；

若支持，则uuid生成一个message id，使用该message id调用适配器的 reply_message_chunk 方法。

## 机器人适配器

因为机器人可能会由于用户配置项不同而表现为对流式的支持性不同，比如飞书默认不支持流式，需要用户额外配置卡片。

所以需要新增一个方法 `is_stream_output_supported() -> bool`，这个让每个适配器来判断并返回是否支持流式；

在发送时，得加两个方法 `send_message_chunk(target_type: str, target_id: str, message_id: , message: MessageChain)`

message_id 确定同一条消息，由调用方生成；

`reply_message_chunk(message_source: MessageEvent, message: MessageChain)`