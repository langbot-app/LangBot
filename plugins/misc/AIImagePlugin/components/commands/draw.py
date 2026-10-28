from __future__ import annotations

from typing import AsyncGenerator

from langbot_plugin.api.definition.components.command.command import Command
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext, CommandReturn


class Draw(Command):
    
    async def _execute(self, context: ExecuteContext) -> AsyncGenerator[CommandReturn, None]:
        """覆盖 _execute 方法，绕过子命令匹配系统"""
        
        # 使用 params 获取所有参数
        if not context.params:
            yield CommandReturn(
                text="用法: !draw <描述>\n示例: !draw a cat sitting on a rainbow"
            )
            return
        
        # 组合描述 - 所有参数都是提示词
        description = " ".join(context.params)
        
        # 发送处理中提示
        yield CommandReturn(
            text=f"🎨 正在生成图片...\n描述: {description}"
        )
        
        # 读取本次调用自己的配置（共享运行时下一个进程服务多个安装）
        config = self.get_plugin_config()
        size = config.get('image_size', '1024x1024')
        model = config.get('model_name', 'qh-draw-x1-pro')
        
        # 每次调用按当前配置创建客户端，用完即关，避免一个租户的凭据被其他租户复用
        try:
            client = self.plugin.create_client()
        except Exception as e:
            yield CommandReturn(
                text=f"❌ 初始化 OpenAI 客户端失败: {str(e)}"
            )
            return
        
        if client is None:
            yield CommandReturn(
                text="❌ 未配置 API Key，请先在插件设置中配置"
            )
            return
        
        try:
            # 调用图片生成 API
            response = await client.images.generate(
                model=model,
                prompt=description,
                size=size,
                n=1,
            )
            
            # 获取结果
            image_url = response.data[0].url
            
            yield CommandReturn(
                text=f"✅ 图片生成成功！",
                image_url=image_url
            )
            
        except Exception as e:
            yield CommandReturn(
                text=f"❌ 生成图片失败: {str(e)}"
            )
        finally:
            try:
                await client.close()
            except Exception:
                pass
