from pkg.plugin.models import Plugin, PersonMessage, GroupMessage, register
from pkg.plugin.host import EventContext


@register(name="ExamplePlugin", description="用于展示QChatGPT插件支持功能的插件", version="0.0.1", author="RockChinQ")
class ExamplePlugin(Plugin):

    def __init__(self):
        pass

    @Plugin.on(PersonMessage)
    def person_message(self, event: EventContext, **kwargs):
        print("person_message", kwargs)
        event.prevent_default()

    @Plugin.on(GroupMessage)
    def group_message(self, **kwargs):
        print("group_message", kwargs)
        self.host.notify_admin("group_message")

    def __del__(self):
        pass
